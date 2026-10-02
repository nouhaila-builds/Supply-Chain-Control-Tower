"""Order journey: expected versus actual, and where a delay started."""

from __future__ import annotations

import pandas as pd

from app.analytics.common import iso, num

STAGE_SPECS = (
    ("supplier_dispatch", "Supplier", 0, "move"),
    ("production", "Production", 0, "dwell_after"),
    ("inbound_warehouse", "Warehouse", 1, "move"),
    ("outbound_hub", "Shipment", 2, "move"),
    ("distribution", "Distribution", 2, "dwell_after"),
    ("customer_delivery", "Customer", 3, "move"),
)


def search_orders(orders: pd.DataFrame, query: str, limit: int = 15) -> list[dict]:
    text = query.strip().lower()
    if len(text) < 2:
        return []
    mask = (
        orders["order_id"].str.lower().str.contains(text, regex=False)
        | orders["customer_name"].str.lower().str.contains(text, regex=False)
        | orders["sku"].str.lower().str.contains(text, regex=False)
        | orders["product_name"].str.lower().str.contains(text, regex=False)
        | orders["supplier_id"].str.lower().str.contains(text, regex=False)
        | orders["warehouse_id"].str.lower().str.contains(text, regex=False)
    )
    found = orders.loc[mask].sort_values("order_date", ascending=False).head(limit)
    return [
        {
            "order_id": row.order_id,
            "sku": row.sku,
            "product_name": row.product_name,
            "customer_name": row.customer_name,
            "status": row.status,
            "order_date": iso(row.order_date),
            "region": row.region,
            "warehouse_id": row.warehouse_id,
        }
        for row in found.itertuples(index=False)
    ]


def _hours(start, end) -> float | None:
    if pd.isna(start) or pd.isna(end):
        return None
    return (pd.Timestamp(end) - pd.Timestamp(start)).total_seconds() / 3600


def _stage_from_move(key: str, label: str, leg: pd.Series) -> dict:
    expected_start = leg["expected_departure"]
    expected_end = leg["expected_arrival"]
    actual_start = leg["actual_departure"]
    actual_end = leg["actual_arrival"]
    return _pack(
        key,
        label,
        f"{leg['origin_name']} → {leg['dest_name']}",
        str(leg["dest_id"]),
        expected_start,
        expected_end,
        actual_start,
        actual_end,
        float(leg["dest_lat"]),
        float(leg["dest_lon"]),
    )


def _stage_dwell(key: str, label: str, left: pd.Series, right: pd.Series) -> dict:
    return _pack(
        key,
        label,
        str(left["dest_name"]),
        str(left["dest_id"]),
        left["expected_arrival"],
        right["expected_departure"],
        left["actual_arrival"],
        right["actual_departure"],
        float(left["dest_lat"]),
        float(left["dest_lon"]),
    )


def _pack(key, label, location, entity_id, expected_start, expected_end, actual_start, actual_end, lat, lon) -> dict:
    expected_hours = _hours(expected_start, expected_end)
    actual_hours = _hours(actual_start, actual_end)
    own = None if expected_hours is None or actual_hours is None else actual_hours - expected_hours
    late = _hours(expected_end, actual_end)
    delay = None if late is None else max(0.0, late)
    if pd.isna(actual_end):
        status = "pending"
    elif delay is not None and delay > 1:
        status = "late"
    else:
        status = "on_time"
    return {
        "key": key,
        "label": label,
        "location": location,
        "entity_id": entity_id,
        "expected_start": iso(expected_start),
        "expected_end": iso(expected_end),
        "actual_start": iso(actual_start),
        "actual_end": iso(actual_end),
        "delay_hours": num(delay, 2),
        "own_delay_hours": num(own, 2),
        "status": status,
        "origin": False,
        "propagated": False,
        "added": False,
        "lat": lat,
        "lon": lon,
    }


def _mark_origin(stages: list[dict], order_status: str) -> str | None:
    origin_index = None
    for index, stage in enumerate(stages):
        own = stage["own_delay_hours"]
        if own is not None and own > 8:
            origin_index = index
            break
    if origin_index is None and order_status == "delayed":
        scored = [(index, stage["own_delay_hours"] or -1e9) for index, stage in enumerate(stages)]
        origin_index = max(scored, key=lambda item: item[1])[0]
        if stages[origin_index]["own_delay_hours"] is None:
            origin_index = None
    if origin_index is None:
        return None
    stages[origin_index]["origin"] = True
    for stage in stages[origin_index + 1 :]:
        delay = stage["delay_hours"] or 0
        own = stage["own_delay_hours"] or 0
        if own > 8:
            stage["added"] = True
        elif delay > 2:
            stage["propagated"] = True
    return stages[origin_index]["label"]


def _narrative(stages: list[dict], order_status: str, origin: str | None, total_delay: float | None) -> str:
    if order_status == "cancelled":
        return "This order was cancelled. Timestamps show how far it progressed before cancellation."
    if order_status == "in_transit" and origin is None:
        return "This order is still open. Stages without an actual timestamp have not been observed yet."
    if origin is None:
        variance = max(stages, key=lambda stage: abs(stage["own_delay_hours"] or 0))
        hours = variance["own_delay_hours"]
        if order_status == "on_time":
            return (
                f"This order met the planned delivery. The largest stage variance was "
                f"{hours:.1f} hours at {variance['label']}."
                if hours is not None
                else "This order met the planned delivery."
            )
        return "The order is late, but no single stage ran materially longer than its own plan."
    origin_stage = next(stage for stage in stages if stage["origin"])
    origin_index = stages.index(origin_stage)
    own = origin_stage["own_delay_hours"] or 0
    later = [stage for stage in stages[origin_index + 1 :] if (stage["own_delay_hours"] or 0) > 8]
    later_own = sum(stage["own_delay_hours"] or 0 for stage in later)
    inherited = max(0.0, (total_delay or 0) - own - later_own)
    sentence = (
        f"Delay originated at {origin_stage['label']} ({origin_stage['location']}). "
        f"That stage ran {own:.1f} hours longer than planned."
    )
    if later:
        largest = max(later, key=lambda stage: stage["own_delay_hours"] or 0)
        hours = largest["own_delay_hours"] or 0
        sentence += (
            f" {largest['label']} ({largest['location']}) added another {hours:.1f} hours of its own."
        )
        if later_own - hours > 8:
            sentence += f" Other later stages added {later_own - hours:.1f} hours on top of that."
    elif inherited > 2:
        sentence += " Later stages mostly inherited that shift; their own handling stayed close to plan."
    return sentence


def build_journey(order: pd.Series, legs: pd.DataFrame) -> dict:
    legs = legs.sort_values("leg_index")
    by_leg = {int(row.leg_index): row for row in legs.itertuples(index=False)}
    # itertuples mangles column access; use loc rows instead
    indexed = {int(idx): legs[legs["leg_index"] == idx].iloc[0] for idx in sorted(legs["leg_index"].unique())}
    stages = []
    if 0 in indexed:
        stages.append(_stage_from_move("supplier_dispatch", "Supplier", indexed[0]))
    if 0 in indexed and 1 in indexed:
        stages.append(_stage_dwell("production", "Production", indexed[0], indexed[1]))
    if 1 in indexed:
        stages.append(_stage_from_move("inbound_warehouse", "Warehouse", indexed[1]))
    if 2 in indexed:
        stages.append(_stage_from_move("outbound_hub", "Shipment", indexed[2]))
    if 2 in indexed and 3 in indexed:
        stages.append(_stage_dwell("distribution", "Distribution", indexed[2], indexed[3]))
    if 3 in indexed:
        stages.append(_stage_from_move("customer_delivery", "Customer", indexed[3]))
    origin = _mark_origin(stages, str(order["status"]))
    total_delay = None
    if pd.notna(order["actual_delivery_date"]) and pd.notna(order["expected_delivery_date"]):
        raw = (order["actual_delivery_date"] - order["expected_delivery_date"]).total_seconds() / 3600
        total_delay = max(0.0, float(raw))
    return {
        "order": {
            "order_id": order["order_id"],
            "sku": order["sku"],
            "product_name": order["product_name"],
            "quantity": int(order["quantity"]),
            "customer_name": order["customer_name"],
            "region": order["region"],
            "country": order["country"],
            "city": order["city"],
            "status": order["status"],
            "supplier_id": order["supplier_id"],
            "supplier_name": order["supplier_name"],
            "factory_name": order["factory_name"],
            "warehouse_id": order["warehouse_id"],
            "warehouse_name": order["warehouse_name"],
            "hub_name": order["hub_name"],
            "order_date": iso(order["order_date"]),
            "expected_delivery_date": iso(order["expected_delivery_date"]),
            "actual_delivery_date": iso(order["actual_delivery_date"]),
            "lead_time_days": num(order["lead_time_days"], 2),
            "expected_lead_time_days": num(order["expected_lead_time_days"], 2),
            "delay_hours": num(total_delay, 2),
            "logistics_cost": num(order["logistics_cost"], 2),
        },
        "stages": stages,
        "origin_stage": origin,
        "total_delay_hours": num(total_delay, 2),
        "narrative": _narrative(stages, str(order["status"]), origin, total_delay),
    }


def example_delayed_order(orders: pd.DataFrame) -> str | None:
    delayed = orders[(orders["status"] == "delayed") & (orders["warehouse_id"] == "W-042")].dropna(subset=["delay_hours"])
    if delayed.empty:
        delayed = orders[orders["status"] == "delayed"].dropna(subset=["delay_hours"])
    if delayed.empty:
        return None
    return str(delayed.sort_values("delay_hours", ascending=False).iloc[0]["order_id"])
