"""Operational KPIs for the selected window versus the previous window."""

from __future__ import annotations

import pandas as pd

from app.analytics.common import integer, mean_or_none, num
from app.analytics.filters import Selection, filter_orders, filter_shipments, period_payload, slice_delivered


def _otd(orders: pd.DataFrame) -> float | None:
    done = slice_delivered(orders)
    if done.empty:
        return None
    return float((done["status"] == "on_time").mean())


def _inventory_value(inventory: pd.DataFrame, as_of: pd.Timestamp, orders: pd.DataFrame) -> float | None:
    part = inventory[inventory["week_end"] <= as_of]
    if part.empty:
        return None
    if not orders.empty:
        part = part[part["warehouse_id"].isin(orders["warehouse_id"].unique()) & part["sku"].isin(orders["sku"].unique())]
    if part.empty:
        return None
    latest = part.sort_values("week_end").groupby(["warehouse_id", "sku"], sort=False).tail(1)
    return float(latest["inventory_value"].sum())


def _pack(value: float | None, baseline: float | None, unit: str, delta_unit: str) -> dict:
    delta = None
    if value is not None and baseline is not None:
        if delta_unit == "pct" and baseline not in (0, None):
            delta = (value - baseline) / abs(baseline)
        else:
            delta = value - baseline
    return {
        "value": num(value, 4) if unit == "ratio" else num(value, 2),
        "baseline": num(baseline, 4) if unit == "ratio" else num(baseline, 2),
        "delta": num(delta, 4),
        "delta_unit": delta_unit,
        "unit": unit,
    }


def compute_kpis(
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    inventory: pd.DataFrame,
    sel: Selection,
    baseline: Selection | None,
    alert_count: int,
    baseline_alert_count: int | None,
) -> dict:
    current_orders = filter_orders(orders, sel, shipments)
    current_shipments = filter_shipments(shipments, sel)
    base_orders = filter_orders(orders, baseline, shipments) if baseline is not None else orders.iloc[0:0]
    base_shipments = filter_shipments(shipments, baseline) if baseline is not None else shipments.iloc[0:0]

    done = slice_delivered(current_orders)
    base_done = slice_delivered(base_orders)
    delayed_shipments = int((current_shipments["delay_hours"].fillna(0) > 1).sum())
    base_delayed = int((base_shipments["delay_hours"].fillna(0) > 1).sum()) if baseline is not None else None

    return {
        "window": period_payload(sel),
        "baseline_window": period_payload(baseline),
        "orders": _pack(float(len(current_orders)), float(len(base_orders)) if baseline is not None else None, "count", "pct"),
        "otd": _pack(_otd(current_orders), _otd(base_orders) if baseline is not None else None, "ratio", "pp"),
        "inventory_value": _pack(
            _inventory_value(inventory, sel.end, current_orders),
            _inventory_value(inventory, baseline.end, base_orders) if baseline is not None else None,
            "eur",
            "pct",
        ),
        "lead_time": _pack(
            mean_or_none(done["lead_time_days"]) if not done.empty else None,
            mean_or_none(base_done["lead_time_days"]) if not base_done.empty else None,
            "days",
            "days",
        ),
        "delayed_shipments": _pack(float(delayed_shipments), float(base_delayed) if base_delayed is not None else None, "count", "count"),
        "logistics_cost": _pack(
            float(current_shipments["shipping_cost"].sum()) if not current_shipments.empty else 0.0,
            float(base_shipments["shipping_cost"].sum()) if baseline is not None else None,
            "eur",
            "pct",
        ),
        "alerts": _pack(float(alert_count), float(baseline_alert_count) if baseline_alert_count is not None else None, "count", "count"),
        "delivered_orders": integer(len(done)) or 0,
        "late_orders": integer((done["status"] == "delayed").sum()) if not done.empty else 0,
    }
