"""Time series and distributions for the performance view."""

from __future__ import annotations

import pandas as pd

from app.analytics.common import mean_or_none, num, week_start
from app.analytics.filters import Selection, filter_orders, filter_shipments, slice_delivered


def _weekly_otd(orders: pd.DataFrame, baseline_rate: float | None) -> list[dict]:
    done = slice_delivered(orders)
    if done.empty:
        return []
    frame = done.copy()
    frame["week"] = week_start(frame["order_date"])
    grouped = frame.groupby("week", sort=True)
    rows = []
    for week, part in grouped:
        delivered_n = len(part)
        on_time = int((part["status"] == "on_time").sum())
        rows.append(
            {
                "week": pd.Timestamp(week).date().isoformat(),
                "otd": num(on_time / delivered_n, 4) if delivered_n else None,
                "orders": delivered_n,
                "late": delivered_n - on_time,
                "baseline_otd": num(baseline_rate, 4),
            }
        )
    return rows


def _lead_hist(orders: pd.DataFrame) -> list[dict]:
    done = slice_delivered(orders)
    if done.empty:
        return []
    bins = [0, 2, 4, 6, 8, 10, 14, 21, 40]
    labels = ["0–2d", "2–4d", "4–6d", "6–8d", "8–10d", "10–14d", "14–21d", "21d+"]
    actual = pd.cut(done["lead_time_days"], bins=bins, labels=labels, right=False)
    expected = pd.cut(done["expected_lead_time_days"], bins=bins, labels=labels, right=False)
    actual_counts = actual.value_counts().reindex(labels, fill_value=0)
    expected_counts = expected.value_counts().reindex(labels, fill_value=0)
    return [
        {"bin": label, "actual": int(actual_counts[label]), "expected": int(expected_counts[label])}
        for label in labels
    ]


def _inventory_series(inventory: pd.DataFrame, orders: pd.DataFrame, sel: Selection) -> list[dict]:
    part = inventory[(inventory["week_end"] >= sel.start) & (inventory["week_end"] <= sel.end + pd.Timedelta(days=1))]
    if not orders.empty:
        part = part[part["warehouse_id"].isin(orders["warehouse_id"].unique()) & part["sku"].isin(orders["sku"].unique())]
    if part.empty:
        return []
    grouped = part.groupby("week_end", sort=True)["inventory_value"].sum()
    return [{"week": pd.Timestamp(week).date().isoformat(), "value": num(value, 2)} for week, value in grouped.items()]


def performance_trends(
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    inventory: pd.DataFrame,
    sel: Selection,
    baseline: Selection | None,
    supplier_names: pd.Series,
) -> dict:
    current_orders = filter_orders(orders, sel, shipments)
    current_shipments = filter_shipments(shipments, sel)
    base_orders = filter_orders(orders, baseline, shipments) if baseline is not None else orders.iloc[0:0]
    base_done = slice_delivered(base_orders)
    baseline_rate = float((base_done["status"] == "on_time").mean()) if not base_done.empty else None

    done = slice_delivered(current_orders).copy()
    volume = []
    if not current_orders.empty:
        current_orders = current_orders.copy()
        current_orders["week"] = week_start(current_orders["order_date"])
        ship = current_shipments.copy()
        ship["week"] = week_start(ship["order_date"])
        order_counts = current_orders.groupby("week").size()
        ship_counts = ship.groupby("week").size()
        weeks = sorted(set(order_counts.index).union(ship_counts.index))
        for week in weeks:
            volume.append(
                {
                    "week": pd.Timestamp(week).date().isoformat(),
                    "orders": int(order_counts.get(week, 0)),
                    "shipments": int(ship_counts.get(week, 0)),
                }
            )

    cost_by_mode = []
    if not current_shipments.empty:
        grouped = current_shipments.groupby("mode", sort=False).agg(
            cost=("shipping_cost", "sum"),
            shipments=("shipment_id", "count"),
        )
        for mode, row in grouped.sort_values("cost", ascending=False).iterrows():
            cost_by_mode.append({"mode": str(mode), "cost": num(row["cost"], 2), "shipments": int(row["shipments"])})

    suppliers = []
    if not done.empty:
        current_rates = done.groupby("supplier_id").agg(orders=("order_id", "count"), on_time=("status", lambda s: (s == "on_time").mean()))
        if not base_done.empty:
            base_rates = base_done.groupby("supplier_id")["status"].apply(lambda s: (s == "on_time").mean())
        else:
            base_rates = pd.Series(dtype=float)
        current_rates = current_rates.sort_values("orders", ascending=False).head(12)
        for supplier_id, row in current_rates.iterrows():
            suppliers.append(
                {
                    "id": str(supplier_id),
                    "label": f"{supplier_id} · {supplier_names.get(supplier_id, supplier_id)}",
                    "orders": int(row["orders"]),
                    "otd": num(row["on_time"], 4),
                    "baseline_otd": num(base_rates.get(supplier_id), 4),
                }
            )

    return {
        "otd_series": _weekly_otd(current_orders if "week" not in current_orders.columns else filter_orders(orders, sel, shipments), baseline_rate),
        "volume_series": volume,
        "lead_time_hist": _lead_hist(current_orders if "status" in current_orders.columns else done),
        "inventory_series": _inventory_series(inventory, filter_orders(orders, sel, shipments), sel),
        "cost_by_mode": cost_by_mode,
        "supplier_performance": suppliers,
        "lead_time_actual": num(mean_or_none(done["lead_time_days"]) if not done.empty else None, 2),
        "lead_time_expected": num(mean_or_none(done["expected_lead_time_days"]) if not done.empty else None, 2),
    }


def kpi_breakdown(
    kpi: str,
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    inventory: pd.DataFrame,
    sel: Selection,
    names: dict[str, pd.Series],
) -> dict:
    current_orders = filter_orders(orders, sel, shipments)
    current_shipments = filter_shipments(shipments, sel)
    done = slice_delivered(current_orders)
    groups: list[dict] = []

    def label(kind: str, key: str) -> str:
        series = names.get(kind)
        if series is not None and key in series.index:
            return f"{key} · {series.loc[key]}"
        return str(key)

    def rank_frame(frame: pd.DataFrame, column: str, value: str, kind: str, title: str, limit: int = 8) -> dict:
        if frame.empty or column not in frame.columns:
            return {"dimension": kind, "title": title, "rows": []}
        grouped = frame.groupby(column, sort=False)[value]
        if value == "late":
            summary = grouped.agg(volume="count", amount="sum")
        elif value == "order_id":
            summary = frame.groupby(column, sort=False).size().rename("amount").to_frame()
            summary["volume"] = summary["amount"]
        else:
            summary = grouped.agg(amount="sum", volume="count")
        summary = summary.sort_values("amount", ascending=False).head(limit)
        rows = []
        total = float(summary["amount"].sum()) or 1.0
        for key, row in summary.iterrows():
            rows.append(
                {
                    "id": str(key),
                    "label": label(kind, str(key)),
                    "value": num(row["amount"], 2),
                    "volume": int(row["volume"]),
                    "share": num(float(row["amount"]) / total, 4),
                }
            )
        return {"dimension": kind, "title": title, "rows": rows}

    if kpi == "orders":
        groups.append(rank_frame(current_orders.assign(one=1), "region", "one", "region", "Orders by region"))
        groups.append(rank_frame(current_orders.assign(one=1), "warehouse_id", "one", "warehouse", "Orders by warehouse"))
    elif kpi == "otd":
        late = done.copy()
        late["late"] = late["status"].eq("delayed").astype(int)
        groups.append(rank_frame(late, "region", "late", "region", "Late orders by region"))
        groups.append(rank_frame(late, "warehouse_id", "late", "warehouse", "Late orders by warehouse"))
        groups.append(rank_frame(late, "supplier_id", "late", "supplier", "Late orders by supplier"))
    elif kpi == "delayed_shipments":
        delayed = current_shipments[current_shipments["delay_hours"].fillna(0) > 1].copy()
        delayed["one"] = 1
        delayed["route"] = delayed["origin_id"].astype(str) + "→" + delayed["dest_id"].astype(str)
        groups.append(rank_frame(delayed, "warehouse_id", "one", "warehouse", "Delayed shipments by warehouse"))
        groups.append(rank_frame(delayed, "supplier_id", "one", "supplier", "Delayed shipments by supplier"))
        groups.append(rank_frame(delayed, "route", "one", "route", "Delayed shipments by lane"))
        top = delayed.sort_values("delay_hours", ascending=False).head(8)
        groups.append(
            {
                "dimension": "shipment",
                "title": "Longest current delays",
                "rows": [
                    {
                        "id": row.shipment_id,
                        "label": f"{row.shipment_id} · {row.origin_id}→{row.dest_id}",
                        "value": num(row.delay_hours, 1),
                        "volume": int(row.quantity),
                        "share": None,
                        "order_id": row.order_id,
                    }
                    for row in top.itertuples(index=False)
                ],
            }
        )
    elif kpi == "lead_time":
        groups.append(
            {
                "dimension": "warehouse",
                "title": "Average actual lead time by warehouse",
                "rows": _mean_rows(done, "warehouse_id", "lead_time_days", "warehouse", names),
            }
        )
    elif kpi == "logistics_cost":
        groups.append(rank_frame(current_shipments, "mode", "shipping_cost", "mode", "Cost by mode"))
        groups.append(rank_frame(current_shipments, "supplier_id", "shipping_cost", "supplier", "Cost by supplier"))
        routed = current_shipments.copy()
        routed["route"] = routed["origin_id"].astype(str) + "→" + routed["dest_id"].astype(str)
        groups.append(rank_frame(routed, "route", "shipping_cost", "route", "Cost by lane"))
    elif kpi == "inventory_value":
        snap = inventory[inventory["week_end"] <= sel.end]
        if not current_orders.empty:
            snap = snap[snap["warehouse_id"].isin(current_orders["warehouse_id"].unique())]
        latest = snap.sort_values("week_end").groupby(["warehouse_id", "sku"], sort=False).tail(1) if not snap.empty else snap
        if not latest.empty:
            grouped = latest.groupby("warehouse_id")["inventory_value"].sum().sort_values(ascending=False).head(8)
            total = float(grouped.sum()) or 1.0
            groups.append(
                {
                    "dimension": "warehouse",
                    "title": "Inventory value by warehouse",
                    "rows": [
                        {
                            "id": str(key),
                            "label": label("warehouse", str(key)),
                            "value": num(value, 2),
                            "volume": None,
                            "share": num(float(value) / total, 4),
                        }
                        for key, value in grouped.items()
                    ],
                }
            )
    else:
        groups.append({"dimension": "alert", "title": "Open the anomaly register", "rows": []})

    questions = {
        "orders": "Where is order volume concentrated in this window?",
        "otd": "Which parts of the network account for late orders?",
        "delayed_shipments": "Which warehouses, suppliers and lanes produce delayed shipments?",
        "lead_time": "Where is actual lead time longest?",
        "logistics_cost": "Which modes and lanes absorb logistics spend?",
        "inventory_value": "Where is inventory value sitting at the end of the window?",
        "alerts": "Which abnormal movements are active for this slice?",
    }
    return {"kpi": kpi, "question": questions.get(kpi, ""), "groups": groups}


def _mean_rows(frame: pd.DataFrame, column: str, value: str, kind: str, names: dict[str, pd.Series]) -> list[dict]:
    if frame.empty:
        return []
    grouped = frame.groupby(column)[value].agg(["mean", "count"]).sort_values("mean", ascending=False).head(8)
    rows = []
    series = names.get(kind)
    for key, row in grouped.iterrows():
        label = f"{key} · {series.loc[key]}" if series is not None and key in series.index else str(key)
        rows.append({"id": str(key), "label": label, "value": num(row["mean"], 2), "volume": int(row["count"]), "share": None})
    return rows
