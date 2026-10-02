"""Interpretable anomaly detection: baseline z-scores, rolling means, IQR, and a cost model."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from app.analytics.common import num, std_or_floor, week_start, zscore
from app.analytics.filters import Selection, filter_orders, filter_shipments, slice_delivered

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2}


def _severity_drop(drop: float, critical: float, high: float) -> str:
    if drop >= critical:
        return "critical"
    if drop >= high:
        return "high"
    return "medium"


def _weekly_rate(frame: pd.DataFrame, key: str, flag: pd.Series) -> pd.Series:
    temp = frame[[key]].copy()
    temp["week"] = week_start(frame["order_date"])
    temp["flag"] = flag.to_numpy()
    return temp.groupby([key, "week"])["flag"].mean()


def detect_anomalies(
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    inventory: pd.DataFrame,
    products: pd.DataFrame,
    warehouses: pd.DataFrame,
    suppliers: pd.DataFrame,
    sel: Selection,
    baseline: Selection | None,
) -> list[dict]:
    alerts: list[dict] = []
    current_orders = filter_orders(orders, sel, shipments)
    current_shipments = filter_shipments(shipments, sel)
    base_orders = filter_orders(orders, baseline, shipments) if baseline is not None else orders.iloc[0:0]
    base_shipments = filter_shipments(shipments, baseline) if baseline is not None else shipments.iloc[0:0]
    supplier_names = suppliers.set_index("supplier_id")["supplier_name"]
    warehouse_names = warehouses.set_index("warehouse_id")["warehouse_name"]
    warehouse_city = warehouses.set_index("warehouse_id")["city"]
    product_names = products.set_index("sku")["product_name"]
    safety = products.set_index("sku")["safety_stock"]

    if baseline is not None:
        alerts.extend(
            _supplier_alerts(current_shipments, base_shipments, supplier_names, suppliers, sel)
        )
        alerts.extend(_warehouse_alerts(current_shipments, base_shipments, warehouse_names, warehouse_city, sel))
        alerts.extend(_region_alerts(current_orders, base_orders, sel))
        alerts.extend(
            _route_cost_alerts(current_shipments, base_shipments, warehouse_names, sel)
        )
    alerts.extend(
        _stock_alerts(current_orders, inventory, product_names, safety, warehouse_names, warehouse_city, sel)
    )
    alerts.sort(key=lambda item: (SEVERITY_RANK.get(item["severity"], 9), -abs(item.get("deviation") or 0)))
    return alerts


def _supplier_alerts(current: pd.DataFrame, baseline: pd.DataFrame, names: pd.Series, suppliers: pd.DataFrame, sel: Selection) -> list[dict]:
    cur = current[(current["leg_index"] == 0) & current["on_time"].notna()]
    base = baseline[(baseline["leg_index"] == 0) & baseline["on_time"].notna()]
    if cur.empty or base.empty:
        return []
    historical = suppliers.set_index("supplier_id")["historical_on_time_rate"]
    alerts = []
    for supplier_id, part in cur.groupby("supplier_id"):
        before = base[base["supplier_id"] == supplier_id]
        if len(part) < 80 or len(before) < 80:
            continue
        observed = float(part["on_time"].mean())
        expected = float(before["on_time"].mean())
        drop = expected - observed
        weekly = before.groupby(week_start(before["order_date"]))["on_time"].mean()
        sigma = std_or_floor(weekly, 0.015)
        score = zscore(observed, expected, sigma)
        rolling = _rolling_otd(part)
        if drop < 0.10 or score > -2.0:
            continue
        severity = _severity_drop(drop, 0.15, 0.10)
        label = f"{supplier_id} · {names.get(supplier_id, supplier_id)}"
        alerts.append(
            _alert(
                alert_id=f"supplier_otd:{supplier_id}",
                severity=severity,
                alert_type="supplier_otd",
                entity_type="supplier",
                entity_id=str(supplier_id),
                entity_label=label,
                metric="On-time dispatch rate",
                expected=expected,
                observed=observed,
                unit="ratio",
                method="rolling 4-week on-time rate vs historical baseline (z-score)",
                timestamp=_cross_timestamp(part, expected, sigma) or sel.end.date().isoformat(),
                location=str(suppliers.set_index("supplier_id").loc[supplier_id, "country"]) if supplier_id in historical.index else "",
                summary=(
                    f"Dispatch on-time rate is {observed:.0%} against a baseline of {expected:.0%} "
                    f"({(observed - expected) * 100:+.1f} pp, z={score:.1f})."
                ),
                metric_key="otd",
                steps=[{"dimension": "supplier", "value": str(supplier_id), "label": label}],
                filters={"supplier": str(supplier_id)},
                extra={"z": num(score, 2), "shipments": int(len(part)), "rolling_otd": num(rolling, 4)},
            )
        )
    return alerts


def _rolling_otd(part: pd.DataFrame) -> float | None:
    weekly = part.groupby(week_start(part["order_date"]))["on_time"].mean().sort_index()
    if weekly.empty:
        return None
    return float(weekly.tail(4).mean())


def _cross_timestamp(part: pd.DataFrame, expected: float, sigma: float) -> str | None:
    weekly = part.groupby(week_start(part["order_date"]))["on_time"].mean().sort_index()
    if len(weekly) < 2:
        return None
    rolling = weekly.rolling(4, min_periods=2).mean()
    crossed = rolling[rolling < expected - 2 * sigma]
    if crossed.empty:
        return None
    return pd.Timestamp(crossed.index[0]).date().isoformat()


def _warehouse_alerts(
    current: pd.DataFrame,
    baseline: pd.DataFrame,
    names: pd.Series,
    cities: pd.Series,
    sel: Selection,
) -> list[dict]:
    def inbound(frame: pd.DataFrame) -> pd.DataFrame:
        part = frame[(frame["leg_index"] == 1) & frame["actual_arrival"].notna() & frame["actual_departure"].notna()].copy()
        if part.empty:
            return part
        part["cycle_days"] = (part["actual_arrival"] - part["actual_departure"]).dt.total_seconds() / 86400
        return part

    cur = inbound(current)
    base = inbound(baseline)
    if cur.empty or base.empty:
        return []
    alerts = []
    for warehouse_id, part in cur.groupby("dest_id"):
        before = base[base["dest_id"] == warehouse_id]
        if len(part) < 40 or len(before) < 40:
            continue
        observed = float(part["cycle_days"].mean())
        expected = float(before["cycle_days"].mean())
        if expected <= 0:
            continue
        lift = (observed - expected) / expected
        weekly = before.groupby(week_start(before["order_date"]))["cycle_days"].mean()
        sigma = std_or_floor(weekly, 0.15)
        score = zscore(observed, expected, sigma)
        if lift < 0.25 or score < 2.5:
            continue
        severity = "critical" if lift >= 0.5 or score >= 4 else "high"
        label = f"{warehouse_id} · {names.get(warehouse_id, warehouse_id)}"
        alerts.append(
            _alert(
                alert_id=f"warehouse_delay:{warehouse_id}",
                severity=severity,
                alert_type="warehouse_delay",
                entity_type="warehouse",
                entity_id=str(warehouse_id),
                entity_label=label,
                metric="Inbound cycle time",
                expected=expected,
                observed=observed,
                unit="days",
                method="inbound cycle time vs historical baseline (z-score)",
                timestamp=sel.end.date().isoformat(),
                location=str(cities.get(warehouse_id, "")),
                summary=(
                    f"Inbound cycle time is {observed:.1f} days against a baseline of {expected:.1f} days "
                    f"({lift:+.0%}, z={score:.1f})."
                ),
                metric_key="lead_time",
                steps=[{"dimension": "warehouse", "value": str(warehouse_id), "label": label}],
                filters={"warehouse": str(warehouse_id)},
                extra={"z": num(score, 2), "shipments": int(len(part)), "lift": num(lift, 3)},
            )
        )
    return alerts


def _region_alerts(current_orders: pd.DataFrame, base_orders: pd.DataFrame, sel: Selection) -> list[dict]:
    cur = slice_delivered(current_orders)
    base = slice_delivered(base_orders)
    if cur.empty or base.empty:
        return []
    alerts = []
    for region, part in cur.groupby("region"):
        before = base[base["region"] == region]
        if len(part) < 80 or len(before) < 80:
            continue
        observed = float((part["status"] == "on_time").mean())
        expected = float((before["status"] == "on_time").mean())
        drop = expected - observed
        weekly = before.groupby(week_start(before["order_date"]))["status"].apply(lambda s: float((s == "on_time").mean()))
        sigma = std_or_floor(weekly, 0.015)
        score = zscore(observed, expected, sigma)
        if drop < 0.08 or score > -2.0:
            continue
        severity = _severity_drop(drop, 0.15, 0.08)
        alerts.append(
            _alert(
                alert_id=f"region_late:{region}",
                severity=severity,
                alert_type="region_late",
                entity_type="region",
                entity_id=str(region),
                entity_label=str(region),
                metric="On-time delivery",
                expected=expected,
                observed=observed,
                unit="ratio",
                method="late-delivery rate vs historical baseline (z-score)",
                timestamp=sel.end.date().isoformat(),
                location=str(region),
                summary=(
                    f"On-time delivery in {region} is {observed:.0%} against a baseline of {expected:.0%} "
                    f"({(observed - expected) * 100:+.1f} pp, z={score:.1f})."
                ),
                metric_key="otd",
                steps=[{"dimension": "region", "value": str(region), "label": str(region)}],
                filters={"region": str(region)},
                extra={"z": num(score, 2), "orders": int(len(part))},
            )
        )
    return alerts


def _route_cost_alerts(
    current: pd.DataFrame,
    baseline: pd.DataFrame,
    warehouse_names: pd.Series,
    sel: Selection,
) -> list[dict]:
    cur = current[(current["distance_km"] > 30) & (current["shipping_cost"] > 0)].copy()
    base = baseline[(baseline["distance_km"] > 30) & (baseline["shipping_cost"] > 0)].copy()
    if len(cur) < 50 or len(base) < 50:
        return []
    cur["cpk"] = cur["shipping_cost"] / cur["distance_km"]
    base["cpk"] = base["shipping_cost"] / base["distance_km"]
    cur["lane"] = cur["origin_id"].astype(str) + "→" + cur["dest_id"].astype(str)
    base["lane"] = base["origin_id"].astype(str) + "→" + base["dest_id"].astype(str)
    residuals = _cost_residuals(base, cur)
    cur = cur.assign(residual=residuals)
    global_sigma = std_or_floor(pd.Series(_cost_residuals(base, base)), 0.5)
    alerts = []
    for lane, part in cur.groupby("lane"):
        before = base[base["lane"] == lane]
        if len(part) < 25 or len(before) < 25:
            continue
        observed = float(part["cpk"].median())
        expected = float(before["cpk"].median())
        if expected <= 0:
            continue
        ratio = observed / expected
        weekly = before.groupby(week_start(before["order_date"]))["cpk"].median()
        q1 = float(weekly.quantile(0.25)) if len(weekly) else expected
        q3 = float(weekly.quantile(0.75)) if len(weekly) else expected
        fence = q3 + 1.5 * (q3 - q1)
        mean_residual = float(part["residual"].mean())
        score = zscore(mean_residual, 0.0, global_sigma)
        if ratio < 1.45 or observed <= fence or score < 2.5:
            continue
        origin, dest = str(lane).split("→")
        label = f"{origin} → {dest}"
        severity = "critical" if ratio >= 2 else "high"
        alerts.append(
            _alert(
                alert_id=f"route_cost:{lane}",
                severity=severity,
                alert_type="route_cost",
                entity_type="route",
                entity_id=str(lane),
                entity_label=label,
                metric="Cost per kilometre",
                expected=expected,
                observed=observed,
                unit="eur_per_km",
                method="IQR fence on cost per km, plus residual vs a linear model of distance, mode and quantity (scikit-learn)",
                timestamp=sel.end.date().isoformat(),
                location=label,
                summary=(
                    f"Median cost per km is €{observed:.2f} against a baseline of €{expected:.2f} "
                    f"({ratio:.2f}×). The lane also exceeds the distance/mode/quantity cost model "
                    f"(mean residual €{mean_residual:.0f}, z={score:.1f})."
                ),
                metric_key="logistics_cost",
                steps=[{"dimension": "route", "value": str(lane), "label": label}],
                filters={},
                extra={"z": num(score, 2), "ratio": num(ratio, 3), "shipments": int(len(part)), "warehouse_name": str(warehouse_names.get(origin, ""))},
            )
        )
    return alerts


def _cost_residuals(train: pd.DataFrame, predict: pd.DataFrame) -> np.ndarray:
    modes = sorted(set(train["mode"].unique()).union(set(predict["mode"].unique())))

    def design(frame: pd.DataFrame) -> np.ndarray:
        columns = [frame["distance_km"].to_numpy(dtype=float), frame["quantity"].to_numpy(dtype=float)]
        for mode in modes:
            columns.append((frame["mode"] == mode).to_numpy(dtype=float))
        return np.column_stack(columns)

    model = LinearRegression()
    model.fit(design(train), train["shipping_cost"].to_numpy(dtype=float))
    return predict["shipping_cost"].to_numpy(dtype=float) - model.predict(design(predict))


def _stock_alerts(
    orders: pd.DataFrame,
    inventory: pd.DataFrame,
    names: pd.Series,
    safety: pd.Series,
    warehouse_names: pd.Series,
    cities: pd.Series,
    sel: Selection,
) -> list[dict]:
    as_of = sel.end
    snap = inventory[inventory["week_end"] <= as_of]
    if snap.empty:
        return []
    latest = snap.sort_values("week_end").groupby(["warehouse_id", "sku"], sort=False).tail(1)
    window_start = as_of - pd.Timedelta(days=27)
    demand_orders = orders[
        (orders["order_date"] >= window_start)
        & (orders["order_date"] < as_of + pd.Timedelta(days=1))
        & (orders["status"] != "cancelled")
    ]
    if not orders.empty and (orders["warehouse_id"].nunique() < inventory["warehouse_id"].nunique() or sel.warehouse or sel.product or sel.region):
        latest = latest[latest["warehouse_id"].isin(orders["warehouse_id"].unique()) & latest["sku"].isin(orders["sku"].unique())]
    demand = demand_orders.groupby(["warehouse_id", "sku"])["quantity"].sum() / 28.0
    alerts = []
    for row in latest.itertuples(index=False):
        rate = float(demand.get((row.warehouse_id, row.sku), 0.0))
        if rate < 8:
            continue
        cover = float(row.on_hand) / rate
        safety_units = float(safety.get(row.sku, 0))
        if cover >= 7 and float(row.on_hand) >= safety_units:
            continue
        if cover >= 8:
            continue
        severity = "critical" if cover < 3 else "high" if cover < 5 else "medium"
        expected = float(safety_units / rate) if rate else 7.0
        label = f"{row.sku} · {names.get(row.sku, row.sku)}"
        city = str(cities.get(row.warehouse_id, ""))
        alerts.append(
            _alert(
                alert_id=f"stockout_risk:{row.warehouse_id}:{row.sku}",
                severity=severity,
                alert_type="stockout_risk",
                entity_type="product",
                entity_id=str(row.sku),
                entity_label=label,
                metric="Days of cover",
                expected=expected,
                observed=cover,
                unit="days_cover",
                method="coverage days versus safety stock, using trailing 28-day demand",
                timestamp=as_of.date().isoformat() if isinstance(as_of, pd.Timestamp) else str(as_of),
                location=f"{city} · {row.warehouse_id}",
                summary=(
                    f"On hand {row.on_hand:.0f} units at {warehouse_names.get(row.warehouse_id, row.warehouse_id)}. "
                    f"Trailing demand is {rate:.0f} units/day, so cover is {cover:.1f} days "
                    f"against safety stock of {safety_units:.0f} units ({expected:.1f} days)."
                ),
                metric_key="stock_coverage",
                steps=[
                    {"dimension": "warehouse", "value": str(row.warehouse_id), "label": f"{row.warehouse_id} · {warehouse_names.get(row.warehouse_id, row.warehouse_id)}"},
                    {"dimension": "product", "value": str(row.sku), "label": label},
                ],
                filters={"warehouse": str(row.warehouse_id), "product": str(row.sku)},
                extra={"on_hand": num(row.on_hand, 1), "daily_demand": num(rate, 2), "safety_stock": num(safety_units, 1)},
            )
        )
    return alerts


def _alert(
    alert_id: str,
    severity: str,
    alert_type: str,
    entity_type: str,
    entity_id: str,
    entity_label: str,
    metric: str,
    expected: float,
    observed: float,
    unit: str,
    method: str,
    timestamp: str,
    location: str,
    summary: str,
    metric_key: str,
    steps: list[dict],
    filters: dict,
    extra: dict,
) -> dict:
    deviation = observed - expected
    deviation_pct = (deviation / expected) if expected not in (0, None) else None
    return {
        "id": alert_id,
        "severity": severity,
        "type": alert_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_label": entity_label,
        "metric": metric,
        "expected_value": num(expected, 4),
        "observed_value": num(observed, 4),
        "deviation": num(deviation, 4),
        "deviation_pct": num(deviation_pct, 4),
        "unit": unit,
        "method": method,
        "timestamp": timestamp if isinstance(timestamp, str) else pd.Timestamp(timestamp).date().isoformat(),
        "location": location,
        "summary": summary,
        "context": {"metric": metric_key, "steps": steps, "filters": filters, "extra": extra},
    }
