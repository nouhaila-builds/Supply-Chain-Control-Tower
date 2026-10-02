"""Inventory position and cost-versus-service comparisons."""

from __future__ import annotations

import pandas as pd

from app.analytics.common import num
from app.analytics.filters import Selection, filter_orders, filter_shipments, slice_delivered


def _snapshot(inventory: pd.DataFrame, orders: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    part = inventory[inventory["week_end"] <= as_of]
    if not orders.empty:
        part = part[part["warehouse_id"].isin(orders["warehouse_id"].unique()) & part["sku"].isin(orders["sku"].unique())]
    if part.empty:
        return part
    return part.sort_values("week_end").groupby(["warehouse_id", "sku"], sort=False).tail(1)


def inventory_view(
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    inventory: pd.DataFrame,
    products: pd.DataFrame,
    warehouses: pd.DataFrame,
    sel: Selection,
) -> dict:
    current_orders = filter_orders(orders, sel, shipments)
    snap = _snapshot(inventory, current_orders if not current_orders.empty else orders.iloc[0:0], sel.end)
    if snap.empty:
        return {"total_value": 0, "by_warehouse": [], "by_category": [], "by_region": [], "series": []}
    snap = snap.merge(products[["sku", "category", "product_name"]], on="sku", how="left")
    names = warehouses.set_index("warehouse_id")["warehouse_name"]
    by_warehouse = (
        snap.groupby("warehouse_id")
        .agg(value=("inventory_value", "sum"), units=("on_hand", "sum"))
        .sort_values("value", ascending=False)
    )
    by_category = snap.groupby("category")["inventory_value"].sum().sort_values(ascending=False)
    shares = (
        current_orders.groupby(["warehouse_id", "region"])["quantity"].sum()
        if not current_orders.empty
        else pd.Series(dtype=float)
    )
    region_value: dict[str, float] = {}
    if not shares.empty:
        for warehouse_id, part in shares.groupby(level=0):
            total_qty = float(part.sum()) or 1.0
            wh_value = float(by_warehouse["value"].get(warehouse_id, 0.0))
            for (_, region), qty in part.items():
                region_value[region] = region_value.get(region, 0.0) + wh_value * (float(qty) / total_qty)
    series = []
    history = inventory[(inventory["week_end"] >= sel.start) & (inventory["week_end"] <= sel.end + pd.Timedelta(days=1))]
    if not current_orders.empty:
        history = history[history["warehouse_id"].isin(current_orders["warehouse_id"].unique())]
    if not history.empty:
        grouped = history.groupby("week_end")["inventory_value"].sum()
        series = [{"week": pd.Timestamp(week).date().isoformat(), "value": num(value, 2)} for week, value in grouped.items()]
    return {
        "total_value": num(snap["inventory_value"].sum(), 2),
        "total_units": num(snap["on_hand"].sum(), 1),
        "by_warehouse": [
            {
                "id": str(key),
                "label": f"{key} · {names.get(key, key)}",
                "value": num(row["value"], 2),
                "units": num(row["units"], 1),
            }
            for key, row in by_warehouse.iterrows()
        ],
        "by_category": [{"id": str(key), "label": str(key), "value": num(value, 2)} for key, value in by_category.items()],
        "by_region": [
            {"id": key, "label": key, "value": num(value, 2)}
            for key, value in sorted(region_value.items(), key=lambda item: -item[1])
        ],
        "series": series,
    }


def cost_service(
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    sel: Selection,
    names: dict[str, pd.Series],
) -> dict:
    current_orders = filter_orders(orders, sel, shipments)
    current_shipments = filter_shipments(shipments, sel)
    done = slice_delivered(current_orders)
    supplier_names = names.get("supplier", pd.Series(dtype=str))

    def points_for(frame_orders: pd.DataFrame, key: str) -> list[dict]:
        if frame_orders.empty or current_shipments.empty:
            return []
        cost = current_shipments.groupby(key)["shipping_cost"].sum()
        ship_n = current_shipments.groupby(key).size()
        otd = frame_orders.groupby(key)["status"].apply(lambda s: float((s == "on_time").mean()))
        volume = frame_orders.groupby(key).size()
        rows = []
        for entity_id in volume.index:
            shipments_n = int(ship_n.get(entity_id, 0))
            if shipments_n < 8 or int(volume.get(entity_id, 0)) < 8:
                continue
            label_name = supplier_names.get(entity_id, entity_id) if key == "supplier_id" else entity_id
            rows.append(
                {
                    "id": str(entity_id),
                    "label": f"{entity_id} · {label_name}" if key == "supplier_id" else str(entity_id),
                    "cost": num(float(cost.get(entity_id, 0)), 2),
                    "cost_per_shipment": num(float(cost.get(entity_id, 0)) / shipments_n, 2),
                    "otd": num(float(otd.get(entity_id)), 4) if entity_id in otd.index else None,
                    "volume": int(volume.get(entity_id, 0)),
                }
            )
        return rows

    routed = current_shipments.copy()
    if not routed.empty:
        routed["route"] = routed["origin_id"].astype(str) + "→" + routed["dest_id"].astype(str)
    route_orders = current_orders.copy()
    if not route_orders.empty and not routed.empty:
        route_of_order = routed.groupby("order_id")["route"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0])
        route_orders = route_orders.merge(route_of_order.rename("route"), left_on="order_id", right_index=True, how="inner")
        route_ship = routed
    else:
        route_orders = current_orders.iloc[0:0]
        route_ship = routed

    supplier_points = points_for(done, "supplier_id")
    route_points = []
    if not route_orders.empty:
        # Reuse the helper against a shipments frame that uses the route column.
        saved = current_shipments
        current_shipments = route_ship
        route_points = points_for(route_orders, "route")
        current_shipments = saved

    def medians(points: list[dict]) -> dict:
        if not points:
            return {"cost": None, "otd": None}
        costs = sorted(point["cost_per_shipment"] for point in points if point["cost_per_shipment"] is not None)
        otds = sorted(point["otd"] for point in points if point["otd"] is not None)
        def mid(values: list[float]) -> float | None:
            if not values:
                return None
            return values[len(values) // 2]
        return {"cost": mid(costs), "otd": mid(otds)}

    return {
        "suppliers": supplier_points,
        "routes": route_points,
        "supplier_median": medians(supplier_points),
        "route_median": medians(route_points),
        "question": "Which suppliers or lanes cost more than the median while delivering worse than the median on-time rate?",
    }
