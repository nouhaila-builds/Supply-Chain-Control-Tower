"""Root-cause contribution along a drill path. Every sentence is computed from the slice."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from app.analytics.common import clamp_share, mean_or_none, num
from app.analytics.filters import Selection, filter_orders, filter_shipments, period_payload, slice_delivered

SEQUENCES = {
    "otd": ["region", "warehouse", "supplier", "product", "shipment"],
    "lead_time": ["warehouse", "supplier", "product", "shipment"],
    "logistics_cost": ["mode", "route", "supplier", "shipment"],
    "stock_coverage": ["warehouse", "product"],
}

QUESTIONS = {
    "otd": "Where is the loss of on-time delivery coming from?",
    "lead_time": "Where is the extra lead time accumulating?",
    "logistics_cost": "Which flows are absorbing more logistics cost than their baseline?",
    "stock_coverage": "Which stock positions are below their safety cover?",
}

METRIC_META = {
    "otd": {"label": "On-time delivery", "unit": "ratio"},
    "lead_time": {"label": "Lead time", "unit": "days"},
    "logistics_cost": {"label": "Logistics cost", "unit": "eur"},
    "stock_coverage": {"label": "Days of cover", "unit": "days"},
}


def _apply_steps(sel: Selection, steps: list[dict]) -> tuple[Selection, str | None]:
    route = None
    updated = sel
    for step in steps:
        dimension = step["dimension"]
        value = step["value"]
        if dimension == "region":
            updated = replace(updated, region=value)
        elif dimension == "warehouse":
            updated = replace(updated, warehouse=value)
        elif dimension == "supplier":
            updated = replace(updated, supplier=value)
        elif dimension == "product":
            updated = replace(updated, product=value)
        elif dimension == "mode":
            updated = replace(updated, mode=value)
        elif dimension == "route":
            route = value
    return updated, route


def _restrict_route(shipments: pd.DataFrame, route: str | None) -> pd.DataFrame:
    if not route or shipments.empty:
        return shipments
    origin, _, dest = route.partition("→")
    return shipments[(shipments["origin_id"] == origin) & (shipments["dest_id"] == dest)]


def investigate(
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    inventory: pd.DataFrame,
    products: pd.DataFrame,
    sel: Selection,
    baseline: Selection | None,
    metric: str,
    steps: list[dict],
    names: dict[str, pd.Series],
) -> dict:
    if metric not in SEQUENCES:
        metric = "otd"
    sequence = SEQUENCES[metric]
    placed = [step["dimension"] for step in steps]
    remaining = [dimension for dimension in sequence if dimension not in placed]
    dimension = remaining[0] if remaining else sequence[-1]
    focused, route = _apply_steps(sel, steps)
    base_sel, _ = _apply_steps(baseline, steps) if baseline is not None else (None, None)

    current_orders = filter_orders(orders, focused, shipments)
    current_shipments = _restrict_route(filter_shipments(shipments, focused), route)
    if route:
        current_orders = current_orders[current_orders["order_id"].isin(current_shipments["order_id"].unique())]
    base_orders = filter_orders(orders, base_sel, shipments) if base_sel is not None else orders.iloc[0:0]
    base_shipments = _restrict_route(filter_shipments(shipments, base_sel), route) if base_sel is not None else shipments.iloc[0:0]
    if route and not base_orders.empty:
        base_orders = base_orders[base_orders["order_id"].isin(base_shipments["order_id"].unique())]

    if metric == "stock_coverage":
        header, rows, evidence = _stock(orders, inventory, products, focused, base_sel, dimension, names)
        unit = "days"
        volume_label = "units on hand"
    elif metric == "logistics_cost":
        header, rows, evidence = _cost(current_shipments, base_shipments, dimension, names)
        unit = "eur"
        volume_label = "shipments"
    elif metric == "lead_time":
        header, rows, evidence = _lead(slice_delivered(current_orders), slice_delivered(base_orders), current_shipments, dimension, names)
        unit = "days"
        volume_label = "delivered orders"
    else:
        header, rows, evidence = _otd(slice_delivered(current_orders), slice_delivered(base_orders), current_shipments, dimension, names)
        unit = "ratio"
        volume_label = "delivered orders"

    breadcrumb = [{"dimension": "global", "value": "", "label": "Global"}]
    for step in steps:
        breadcrumb.append(
            {
                "dimension": step["dimension"],
                "value": step["value"],
                "label": _label(step["dimension"], step["value"], names, step.get("label")),
            }
        )
    return {
        "metric": metric,
        "metric_label": METRIC_META[metric]["label"],
        "unit": unit,
        "question": QUESTIONS[metric],
        "dimension": dimension,
        "volume_label": volume_label,
        "window": period_payload(focused),
        "baseline_window": period_payload(base_sel),
        "current": header.get("current"),
        "baseline": header.get("baseline"),
        "deviation": header.get("deviation"),
        "deviation_pct": header.get("deviation_pct"),
        "volume": header.get("volume"),
        "breadcrumb": breadcrumb,
        "rows": rows,
        "evidence": evidence,
        "steps": breadcrumb[1:],
    }


def _label(dimension: str, value: str, names: dict[str, pd.Series], fallback: str | None = None) -> str:
    if dimension == "route" and "→" in value:
        origin, _, dest = value.partition("→")
        return f"{_label('node', origin, names)} → {_label('node', dest, names)}"
    if dimension in {"warehouse", "supplier", "product", "node", "factory", "hub", "customer"}:
        series = names.get(dimension if dimension != "node" else "node")
        if series is not None and value in series.index:
            pretty = series.loc[value]
            if dimension == "product":
                return f"{value} · {pretty}"
            if dimension == "node":
                return str(pretty)
            return f"{value} · {pretty}"
    if fallback and fallback != value:
        return fallback
    return str(value)


def _header(current: float | None, baseline: float | None, volume: int) -> dict:
    deviation = None if current is None or baseline is None else current - baseline
    deviation_pct = None
    if deviation is not None and baseline not in (None, 0):
        deviation_pct = deviation / baseline
    return {
        "current": num(current, 4),
        "baseline": num(baseline, 4),
        "deviation": num(deviation, 4),
        "deviation_pct": num(deviation_pct, 4),
        "volume": volume,
    }


def _finalize(rows: list[dict], limit: int = 10) -> list[dict]:
    rows = [row for row in rows if row.get("volume")]
    rows.sort(key=lambda row: (-(row.get("contribution") or 0), -(row.get("excess") or 0)))
    if len(rows) <= limit:
        return rows
    head = rows[:limit]
    rest = rows[limit:]
    head.append(
        {
            "id": "__other__",
            "label": f"Other ({len(rest)})",
            "volume": int(sum(row["volume"] for row in rest)),
            "current": None,
            "baseline": None,
            "deviation": None,
            "excess": num(sum(row.get("excess") or 0 for row in rest), 2),
            "contribution": num(sum(row.get("contribution") or 0 for row in rest), 4),
            "drillable": False,
            "order_id": None,
        }
    )
    return head


def _shares(rows: list[dict]) -> None:
    shares = clamp_share([float(row.get("excess") or 0) for row in rows])
    for row, share in zip(rows, shares):
        row["contribution"] = num(share, 4)


def _otd(current: pd.DataFrame, baseline: pd.DataFrame, shipments: pd.DataFrame, dimension: str, names: dict[str, pd.Series]) -> tuple[dict, list[dict], list[str]]:
    if dimension == "shipment":
        return _shipment_rows(current, baseline, shipments, "delay", names)
    current_rate = float((current["status"] == "on_time").mean()) if len(current) else None
    baseline_rate = float((baseline["status"] == "on_time").mean()) if len(baseline) else None
    header = _header(current_rate, baseline_rate, int(len(current)))
    column = {"region": "region", "warehouse": "warehouse_id", "supplier": "supplier_id", "product": "sku"}[dimension]
    rows = []
    global_base_late = 1 - baseline_rate if baseline_rate is not None else None
    if not current.empty:
        for key, part in current.groupby(column, sort=False):
            before = baseline[baseline[column] == key] if not baseline.empty else baseline
            base_rate = float((before["status"] == "on_time").mean()) if len(before) >= 20 else baseline_rate
            observed = float((part["status"] == "on_time").mean())
            late = int((part["status"] == "delayed").sum())
            expected_late = (1 - base_rate) * len(part) if base_rate is not None else 0
            rows.append(
                {
                    "id": str(key),
                    "label": _label(dimension, str(key), names),
                    "volume": int(len(part)),
                    "current": num(observed, 4),
                    "baseline": num(base_rate, 4),
                    "deviation": num(observed - base_rate, 4) if base_rate is not None else None,
                    "excess": num(late - expected_late, 2),
                    "contribution": 0,
                    "drillable": True,
                    "order_id": None,
                }
            )
    _shares(rows)
    rows = _finalize(rows)
    late_n = int((current["status"] == "delayed").sum()) if len(current) else 0
    expected_late = (global_base_late * len(current)) if global_base_late is not None else None
    evidence = [
        _compare_sentence("On-time delivery", current_rate, baseline_rate, "ratio"),
        (
            f"Delivered orders in this slice: {len(current):,}. Late orders: {late_n:,}."
            + (f" The baseline late rate implies about {expected_late:,.0f} late orders." if expected_late is not None else "")
        ),
    ]
    top = next((row for row in rows if row["id"] != "__other__" and (row.get("contribution") or 0) > 0), None)
    if top:
        evidence.append(
            f"{top['label']} accounts for {top['contribution'] * 100:.0f}% of excess late orders "
            f"({top['excess']:.0f} versus its own baseline rate, on {top['volume']:,} delivered orders)."
        )
    evidence.append("Contribution is the share of late orders above what each entity's baseline rate would have produced.")
    return header, rows, evidence


def _lead(current: pd.DataFrame, baseline: pd.DataFrame, shipments: pd.DataFrame, dimension: str, names: dict[str, pd.Series]) -> tuple[dict, list[dict], list[str]]:
    if dimension == "shipment":
        return _shipment_rows(current, baseline, shipments, "delay", names)
    current_mean = mean_or_none(current["lead_time_days"]) if not current.empty else None
    baseline_mean = mean_or_none(baseline["lead_time_days"]) if not baseline.empty else None
    header = _header(current_mean, baseline_mean, int(len(current)))
    column = {"warehouse": "warehouse_id", "supplier": "supplier_id", "product": "sku"}[dimension]
    rows = []
    if not current.empty:
        for key, part in current.groupby(column, sort=False):
            before = baseline[baseline[column] == key] if not baseline.empty else baseline
            base_mean = mean_or_none(before["lead_time_days"]) if len(before) >= 20 else baseline_mean
            observed = mean_or_none(part["lead_time_days"])
            excess = None
            if observed is not None and base_mean is not None:
                excess = (observed - base_mean) * len(part)
            rows.append(
                {
                    "id": str(key),
                    "label": _label(dimension, str(key), names),
                    "volume": int(len(part)),
                    "current": num(observed, 3),
                    "baseline": num(base_mean, 3),
                    "deviation": num(None if observed is None or base_mean is None else observed - base_mean, 3),
                    "excess": num(excess, 2),
                    "contribution": 0,
                    "drillable": True,
                    "order_id": None,
                }
            )
    _shares(rows)
    rows = _finalize(rows)
    expected_plan = mean_or_none(current["expected_lead_time_days"]) if not current.empty else None
    evidence = [
        _compare_sentence("Actual lead time", current_mean, baseline_mean, "days"),
        _compare_sentence("Planned lead time in this slice", expected_plan, current_mean, "plan"),
    ]
    top = next((row for row in rows if row["id"] != "__other__" and (row.get("contribution") or 0) > 0), None)
    if top and top.get("deviation") is not None:
        evidence.append(
            f"{top['label']} contributes {top['contribution'] * 100:.0f}% of excess lead-time days "
            f"(actual {top['current']:.1f}d vs baseline {top['baseline']:.1f}d, n={top['volume']:,})."
        )
    evidence.append("Excess lead time is (actual − baseline) × delivered orders. Only increases count toward contribution.")
    return header, rows, evidence


def _cost(current: pd.DataFrame, baseline: pd.DataFrame, dimension: str, names: dict[str, pd.Series]) -> tuple[dict, list[dict], list[str]]:
    if dimension == "shipment":
        return _shipment_rows(pd.DataFrame(), pd.DataFrame(), current, "cost", names)
    current_total = float(current["shipping_cost"].sum()) if not current.empty else 0.0
    baseline_mean = float(baseline["shipping_cost"].mean()) if not baseline.empty else None
    baseline_total = (baseline_mean * len(current)) if baseline_mean is not None else None
    header = _header(current_total, baseline_total, int(len(current)))
    frame = current.copy()
    before = baseline.copy()
    if dimension == "route":
        frame["route"] = frame["origin_id"].astype(str) + "→" + frame["dest_id"].astype(str)
        if not before.empty:
            before["route"] = before["origin_id"].astype(str) + "→" + before["dest_id"].astype(str)
        column = "route"
    elif dimension == "mode":
        column = "mode"
    else:
        column = "supplier_id"
    rows = []
    if not frame.empty:
        for key, part in frame.groupby(column, sort=False):
            prior = before[before[column] == key] if not before.empty and column in before.columns else before.iloc[0:0]
            base_mean = float(prior["shipping_cost"].mean()) if len(prior) >= 15 else baseline_mean
            observed = float(part["shipping_cost"].sum())
            expected = (base_mean * len(part)) if base_mean is not None else None
            per_current = float(part["shipping_cost"].mean())
            rows.append(
                {
                    "id": str(key),
                    "label": _label("supplier" if dimension == "supplier" else dimension, str(key), names),
                    "volume": int(len(part)),
                    "current": num(per_current, 2),
                    "baseline": num(base_mean, 2),
                    "deviation": num(None if base_mean is None else per_current - base_mean, 2),
                    "excess": num(None if expected is None else observed - expected, 2),
                    "contribution": 0,
                    "drillable": True,
                    "order_id": None,
                }
            )
    _shares(rows)
    rows = _finalize(rows)
    evidence = [
        _compare_sentence("Logistics cost", current_total, baseline_total, "eur"),
        f"Shipments in this slice: {len(current):,}.",
    ]
    top = next((row for row in rows if row["id"] != "__other__" and (row.get("contribution") or 0) > 0), None)
    if top:
        evidence.append(
            f"{top['label']} accounts for {top['contribution'] * 100:.0f}% of cost above the baseline "
            f"(€{top['excess']:,.0f} on {top['volume']:,} shipments)."
        )
    evidence.append("Baseline cost is the previous window's average shipment cost for the same entity, scaled to current volume.")
    return header, rows, evidence


def _scoped_orders(orders: pd.DataFrame, sel: Selection) -> pd.DataFrame:
    scoped = orders
    if sel.region:
        scoped = scoped[scoped["region"] == sel.region]
    if sel.country:
        scoped = scoped[scoped["country"] == sel.country]
    if sel.supplier:
        scoped = scoped[scoped["supplier_id"] == sel.supplier]
    if sel.warehouse:
        scoped = scoped[scoped["warehouse_id"] == sel.warehouse]
    if sel.factory:
        scoped = scoped[scoped["factory_id"] == sel.factory]
    if sel.product:
        scoped = scoped[scoped["sku"] == sel.product]
    if sel.customer:
        scoped = scoped[scoped["customer_id"] == sel.customer]
    return scoped


def _stock(orders, inventory, products, sel: Selection, baseline: Selection | None, dimension: str, names) -> tuple[dict, list[dict], list[str]]:
    scope = _scoped_orders(orders, sel)

    def snapshot(as_of: pd.Timestamp) -> pd.DataFrame:
        part = inventory[inventory["week_end"] <= as_of]
        if not scope.empty:
            part = part[part["warehouse_id"].isin(scope["warehouse_id"].unique()) & part["sku"].isin(scope["sku"].unique())]
        if part.empty:
            return part
        latest = part.sort_values("week_end").groupby(["warehouse_id", "sku"], sort=False).tail(1).copy()
        start = as_of - pd.Timedelta(days=27)
        demand_orders = scope[
            (scope["order_date"] >= start)
            & (scope["order_date"] < as_of + pd.Timedelta(days=1))
            & (scope["status"] != "cancelled")
        ]
        demand = demand_orders.groupby(["warehouse_id", "sku"])["quantity"].sum() / 28.0
        keys = list(zip(latest["warehouse_id"], latest["sku"]))
        latest["daily_demand"] = [float(demand.get(key, 0.0)) for key in keys]
        latest["coverage"] = [
            (on_hand / rate) if rate >= 1 else pd.NA
            for on_hand, rate in zip(latest["on_hand"], latest["daily_demand"])
        ]
        return latest.merge(products[["sku", "safety_stock", "product_name"]], on="sku", how="left")

    current = snapshot(sel.end)
    baseline_snap = snapshot(baseline.end) if baseline is not None else current.iloc[0:0]
    usable = current[current["coverage"].notna()] if not current.empty else current
    current_cover = float(usable["coverage"].median()) if not usable.empty else None
    base_usable = baseline_snap[baseline_snap["coverage"].notna()] if not baseline_snap.empty else baseline_snap
    baseline_cover = float(base_usable["coverage"].median()) if not base_usable.empty else None
    header = _header(current_cover, baseline_cover, int(usable["on_hand"].sum()) if not usable.empty else 0)
    rows = []
    if dimension == "warehouse" and not usable.empty:
        for key, part in usable.groupby("warehouse_id"):
            rows.append(_stock_row("warehouse", str(key), part, base_usable, names))
    elif not usable.empty:
        for key, part in usable.groupby("sku"):
            rows.append(_stock_row("product", str(key), part, base_usable, names))
    _shares(rows)
    rows = _finalize(rows, limit=12)
    shortest = usable.sort_values("coverage").head(1) if not usable.empty else usable
    evidence = [_compare_sentence("Median days of cover", current_cover, baseline_cover, "days")]
    if len(shortest):
        row = shortest.iloc[0]
        evidence.append(
            f"Shortest cover in this slice is {row.sku} at {row.warehouse_id}: "
            f"{row.on_hand:.0f} units on hand, {row.daily_demand:.0f} units/day, {row.coverage:.1f} days."
        )
    evidence.append("Shortfall treats safety cover as seven days of the trailing demand. Contribution is the share of units below that cover.")
    return header, rows, evidence


def _stock_row(dimension: str, key: str, part: pd.DataFrame, baseline: pd.DataFrame, names) -> dict:
    cover = float(part["coverage"].median())
    if dimension == "warehouse":
        before = baseline[baseline["warehouse_id"] == key] if not baseline.empty else baseline
    else:
        before = baseline[baseline["sku"] == key] if not baseline.empty else baseline
    base_cover = float(before["coverage"].median()) if not before.empty and before["coverage"].notna().any() else None
    safety_units = float((part["daily_demand"] * 7).sum())
    on_hand = float(part["on_hand"].sum())
    excess = max(0.0, safety_units - on_hand)
    return {
        "id": key,
        "label": _label(dimension, key, names),
        "volume": int(round(on_hand)),
        "current": num(cover, 2),
        "baseline": num(base_cover, 2),
        "deviation": num(None if base_cover is None else cover - base_cover, 2),
        "excess": num(excess, 1),
        "contribution": 0,
        "drillable": dimension != "product",
        "order_id": None,
    }


def _shipment_rows(orders: pd.DataFrame, baseline: pd.DataFrame, shipments: pd.DataFrame, kind: str, names) -> tuple[dict, list[dict], list[str]]:
    part = shipments.dropna(subset=["delay_hours"]) if "delay_hours" in shipments.columns else shipments
    if kind == "cost":
        part = shipments.sort_values("shipping_cost", ascending=False).head(15)
        value_col = "shipping_cost"
    else:
        part = part.sort_values("delay_hours", ascending=False).head(15)
        value_col = "delay_hours"
    total_delay = float(shipments["delay_hours"].clip(lower=0).sum()) if not shipments.empty and "delay_hours" in shipments.columns else 0.0
    header = _header(
        mean_or_none(orders["lead_time_days"]) if not orders.empty and "lead_time_days" in orders.columns else None,
        mean_or_none(baseline["lead_time_days"]) if not baseline.empty and "lead_time_days" in getattr(baseline, "columns", []) else None,
        int(len(shipments)),
    )
    rows = []
    for row in part.itertuples(index=False):
        magnitude = float(getattr(row, value_col) or 0)
        rows.append(
            {
                "id": row.shipment_id,
                "label": f"{row.shipment_id} · {row.origin_id}→{row.dest_id}",
                "volume": int(row.quantity),
                "current": num(magnitude, 2),
                "baseline": None,
                "deviation": num(magnitude, 2),
                "excess": num(max(magnitude, 0), 2),
                "contribution": num((max(magnitude, 0) / total_delay) if kind != "cost" and total_delay else None, 4),
                "drillable": False,
                "order_id": row.order_id,
            }
        )
    evidence = [
        f"Showing the {len(rows)} shipments with the largest {'cost' if kind == 'cost' else 'delay'} inside the current drill.",
        "Open an order to see where that delay started and which later stages inherited it.",
    ]
    return header, rows, evidence


def _compare_sentence(label: str, current: float | None, baseline: float | None, unit: str) -> str:
    if current is None:
        return f"{label} is unavailable for this slice."
    if unit == "ratio":
        if baseline is None:
            return f"{label} is {current:.1%} in this window. The previous window is too short to use as a baseline."
        return (
            f"{label} is {current:.1%} in this window, against {baseline:.1%} in the previous window "
            f"({(current - baseline) * 100:+.1f} percentage points)."
        )
    if unit == "days":
        if baseline is None:
            return f"{label} is {current:.1f} days in this window."
        return f"{label} is {current:.1f} days against a baseline of {baseline:.1f} days ({current - baseline:+.1f} days)."
    if unit == "plan":
        if baseline is None or current is None:
            return "Planned lead time is not available for this slice."
        # Here `current` is the plan and `baseline` is the actual, from the call site.
        plan, actual = current, baseline
        gap = actual - plan
        pct = gap / plan if plan else None
        pct_txt = f", {pct:+.0%}" if pct is not None else ""
        return f"Planned lead time is {plan:.1f} days and actual lead time is {actual:.1f} days ({gap:+.1f} days{pct_txt})."
    if unit == "eur":
        if baseline is None:
            return f"{label} is €{current:,.0f}."
        return f"{label} is €{current:,.0f} against a volume-adjusted baseline of €{baseline:,.0f} ({current - baseline:+,.0f})."
    return f"{label}: {current}."
