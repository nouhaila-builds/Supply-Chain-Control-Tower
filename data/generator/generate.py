"""Reproducible synthetic supply-chain dataset.

Run from the project root:

    python -m data.generator.generate

The generator writes parquet tables under data/generated/. Anomalies are injected
into the transactions (late dispatches, slowed inbound cycle times, a receipt
stoppage, a rate spike, a regional last-mile deterioration). Alert text in the
application is computed later from these tables; it is not copied from here.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from data.generator.catalog import (
    CATEGORIES,
    CATEGORY_COST,
    COST_RATES,
    CUSTOMER_NAMES,
    FACTORIES,
    FACTORY_BY_COUNTRY,
    FACTORY_WAREHOUSES,
    HANDLING_H,
    HUBS,
    INJECTED,
    PARTS,
    SPEED_KMH,
    SUPPLIERS,
    WAREHOUSE_HUBS,
    WAREHOUSES,
)

EPOCH = date(2025, 10, 1)
AS_OF = date(2026, 9, 30)
N_DAYS = (AS_OF - EPOCH).days + 1  # 365
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data" / "generated"

SUPPLIER_DAY = (date(2026, 7, 3) - EPOCH).days
WAREHOUSE_DAY = (date(2026, 7, 3) - EPOCH).days
REGION_DAY = (date(2026, 8, 1) - EPOCH).days
COST_DAY = (date(2026, 8, 1) - EPOCH).days
AS_OF_HOUR = (AS_OF - EPOCH).days * 24 + 23

STAGES = (
    "supplier_dispatch",
    "inbound_warehouse",
    "outbound_hub",
    "customer_delivery",
)
TRANSFER_H = (8.0, 6.0, 5.0)


def _day_index(value: date) -> int:
    return (value - EPOCH).days


def _hours_to_datetime(hours: np.ndarray) -> pd.Series:
    stamps = pd.to_timedelta(hours, unit="h") + pd.Timestamp(EPOCH)
    return pd.Series(stamps)


def _haversine(lat1, lon1, lat2, lon2) -> np.ndarray:
    radius = 6371.0
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * radius * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _entity_frame(rows: list[tuple], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=columns)
    if frame[columns[0]].duplicated().any():
        raise RuntimeError(f"duplicate {columns[0]} in catalog")
    return frame


def _build_masters(rng: np.random.Generator) -> dict[str, pd.DataFrame]:
    suppliers = _entity_frame(
        [(i, n, c, country, lat, lon) for i, n, c, country, lat, lon in SUPPLIERS],
        ["supplier_id", "supplier_name", "city", "country", "latitude", "longitude"],
    )
    suppliers["factory_id"] = suppliers["country"].map(FACTORY_BY_COUNTRY)
    if suppliers["factory_id"].isna().any():
        raise RuntimeError("supplier country has no factory mapping")

    factories = _entity_frame(
        list(FACTORIES),
        ["factory_id", "factory_name", "city", "country", "latitude", "longitude"],
    )
    warehouses = _entity_frame(
        list(WAREHOUSES),
        ["warehouse_id", "warehouse_name", "city", "country", "latitude", "longitude"],
    )
    hubs = _entity_frame(
        list(HUBS),
        ["hub_id", "hub_name", "city", "country", "region", "latitude", "longitude"],
    )

    customers = []
    name_i = 0
    for hub in hubs.itertuples(index=False):
        for slot in range(2):
            jitter_lat = float(rng.normal(0, 0.08))
            jitter_lon = float(rng.normal(0, 0.08))
            customers.append(
                {
                    "customer_id": f"C-{name_i + 1:03d}",
                    "customer_name": CUSTOMER_NAMES[name_i],
                    "hub_id": hub.hub_id,
                    "city": hub.city,
                    "country": hub.country,
                    "region": hub.region,
                    "latitude": hub.latitude + jitter_lat + (0.15 if slot else -0.12),
                    "longitude": hub.longitude + jitter_lon + (0.18 if slot else -0.1),
                }
            )
            name_i += 1
    customers_df = pd.DataFrame(customers)

    sku_ids = [f"SKU-{1000 + i:04d}" for i in range(100)]
    sku_ids[17] = "SKU-2841"
    supplier_ids = suppliers["supplier_id"].tolist()
    other_suppliers = [s for s in supplier_ids if s != "S-018"]
    sku_supplier: list[str | None] = [None] * 100
    for idx in range(17, 25):
        sku_supplier[idx] = "S-018"
    remaining = [i for i, value in enumerate(sku_supplier) if value is None]
    for k, idx in enumerate(remaining):
        sku_supplier[idx] = other_suppliers[k % len(other_suppliers)]

    factory_of = dict(zip(suppliers["supplier_id"], suppliers["factory_id"]))
    products = []
    for idx, sku in enumerate(sku_ids):
        supplier_id = str(sku_supplier[idx])
        factory_id = factory_of[supplier_id]
        if sku == "SKU-2841" or supplier_id == "S-018":
            warehouse_id = "W-042"
            category = "Industrial Components" if sku == "SKU-2841" else CATEGORIES[idx % len(CATEGORIES)]
            unit_cost = 640.0 if sku == "SKU-2841" else float(rng.uniform(*CATEGORY_COST[category]))
            name = "Servo Assembly 2841" if sku == "SKU-2841" else f"{PARTS[idx % len(PARTS)].title()} {sku[-4:]}"
        else:
            options = FACTORY_WAREHOUSES[factory_id]
            if "W-042" in options and rng.random() < 0.12:
                warehouse_id = "W-042"
            else:
                pool = [w for w in options if w != "W-042"] or options
                warehouse_id = pool[int(rng.integers(0, len(pool)))]
            category = CATEGORIES[idx % len(CATEGORIES)]
            low, high = CATEGORY_COST[category]
            unit_cost = float(rng.uniform(low, high))
            name = f"{PARTS[idx % len(PARTS)].title()} {sku[-4:]}"
        products.append(
            {
                "sku": sku,
                "product_name": name,
                "category": category,
                "unit_cost": round(unit_cost, 2),
                "supplier_id": supplier_id,
                "factory_id": factory_id,
                "warehouse_id": warehouse_id,
            }
        )
    products_df = pd.DataFrame(products)
    weights = rng.random(100) ** 1.55
    weights[17] = 0.0
    weights = weights / weights.sum() * 0.955
    weights[17] = 0.045
    products_df["sample_weight"] = weights

    return {
        "suppliers": suppliers,
        "factories": factories,
        "warehouses": warehouses,
        "hubs": hubs,
        "customers": customers_df,
        "products": products_df,
    }


def _seasonal_day_weights() -> np.ndarray:
    doy = np.arange(N_DAYS)
    season = (
        1.0
        + 0.38 * np.exp(-0.5 * ((doy - 46) / 16) ** 2)
        + 0.22 * np.exp(-0.5 * ((doy - 175) / 18) ** 2)
        - 0.18 * np.exp(-0.5 * ((doy - 310) / 20) ** 2)
    )
    season = np.clip(season, 0.55, None)
    return season / season.sum()


def _sample_orders(masters: dict[str, pd.DataFrame], rng: np.random.Generator, n: int) -> pd.DataFrame:
    products = masters["products"]
    customers = masters["customers"]
    sku_idx = rng.choice(len(products), size=n, p=products["sample_weight"].to_numpy())
    order_day = rng.choice(N_DAYS, size=n, p=_seasonal_day_weights())
    quantity = np.clip(rng.lognormal(np.log(28), 0.55, n), 1, 400).astype(np.int32)
    special = sku_idx == 17
    if special.any():
        quantity[special] = np.clip(rng.lognormal(np.log(32), 0.35, int(special.sum())), 1, 120).astype(np.int32)

    chosen = products.iloc[sku_idx].reset_index(drop=True)
    warehouse = chosen["warehouse_id"].to_numpy()
    hub = np.empty(n, dtype=object)
    for warehouse_id, lanes in WAREHOUSE_HUBS.items():
        mask = warehouse == warehouse_id
        count = int(mask.sum())
        if count == 0:
            continue
        ids = [lane[0] for lane in lanes]
        probs = np.array([lane[1] for lane in lanes], dtype=float)
        probs = probs / probs.sum()
        hub[mask] = rng.choice(ids, size=count, p=probs)

    by_hub = {key: frame["customer_id"].tolist() for key, frame in customers.groupby("hub_id")}
    customer = np.empty(n, dtype=object)
    for hub_id, ids in by_hub.items():
        mask = hub == hub_id
        count = int(mask.sum())
        if count == 0:
            continue
        customer[mask] = rng.choice(ids, size=count)

    cancelled = (rng.random(n) < 0.012) & (order_day <= (N_DAYS - 10))
    orders = pd.DataFrame(
        {
            "order_id": [f"ORD-{i:06d}" for i in range(1, n + 1)],
            "sku": chosen["sku"].to_numpy(),
            "product_name": chosen["product_name"].to_numpy(),
            "category": chosen["category"].to_numpy(),
            "unit_cost": chosen["unit_cost"].to_numpy(),
            "quantity": quantity,
            "supplier_id": chosen["supplier_id"].to_numpy(),
            "factory_id": chosen["factory_id"].to_numpy(),
            "warehouse_id": warehouse,
            "hub_id": hub,
            "customer_id": customer,
            "order_day": order_day.astype(np.int16),
            "cancelled": cancelled,
        }
    )
    cust = customers.set_index("customer_id")
    orders["customer_name"] = orders["customer_id"].map(cust["customer_name"])
    orders["region"] = orders["customer_id"].map(cust["region"])
    orders["country"] = orders["customer_id"].map(cust["country"])
    orders["city"] = orders["customer_id"].map(cust["city"])
    orders["customer_lat"] = orders["customer_id"].map(cust["latitude"])
    orders["customer_lon"] = orders["customer_id"].map(cust["longitude"])
    orders["order_date"] = pd.Timestamp(EPOCH) + pd.to_timedelta(orders["order_day"].astype(int), unit="D") + pd.Timedelta(hours=8)
    return orders


def _mode_for_stage(dist: np.ndarray, stage: str, category: np.ndarray | None, rng: np.random.Generator) -> np.ndarray:
    mode = np.full(dist.shape, "road", dtype=object)
    if stage == "customer_delivery":
        mode[:] = np.where(dist >= 280, "road", "parcel")
    elif stage == "outbound_hub":
        mode[:] = np.where(dist >= 650, "rail", "road")
    elif stage == "inbound_warehouse":
        mode[:] = np.where(dist >= 520, "rail", "road")
    else:
        mode[:] = "road"
        mode[dist >= 550] = "rail"
        mode[dist >= 1400] = "sea"
        if category is not None:
            air = (category == "Electronics") & (rng.random(len(dist)) < 0.07)
            mode[air] = "air"
    return mode


def _coord_lookup(masters: dict[str, pd.DataFrame]) -> dict[str, dict]:
    lookup: dict[str, dict] = {}

    def add(frame: pd.DataFrame, id_col: str, name_col: str, kind: str) -> None:
        for row in frame.itertuples(index=False):
            lookup[getattr(row, id_col)] = {
                "name": getattr(row, name_col),
                "type": kind,
                "lat": row.latitude,
                "lon": row.longitude,
                "country": row.country,
                "city": row.city,
            }

    add(masters["suppliers"], "supplier_id", "supplier_name", "supplier")
    add(masters["factories"], "factory_id", "factory_name", "factory")
    add(masters["warehouses"], "warehouse_id", "warehouse_name", "warehouse")
    add(masters["hubs"], "hub_id", "hub_name", "hub")
    add(masters["customers"], "customer_id", "customer_name", "customer")
    return lookup


def _build_shipments(orders: pd.DataFrame, masters: dict[str, pd.DataFrame], rng: np.random.Generator) -> pd.DataFrame:
    n = len(orders)
    lookup = _coord_lookup(masters)
    origin_cols = [
        orders["supplier_id"].to_numpy(),
        orders["factory_id"].to_numpy(),
        orders["warehouse_id"].to_numpy(),
        orders["hub_id"].to_numpy(),
    ]
    dest_cols = [
        orders["factory_id"].to_numpy(),
        orders["warehouse_id"].to_numpy(),
        orders["hub_id"].to_numpy(),
        orders["customer_id"].to_numpy(),
    ]
    category = orders["category"].to_numpy()
    order_day = orders["order_day"].to_numpy()
    cancelled = orders["cancelled"].to_numpy()
    supplier = orders["supplier_id"].to_numpy()
    warehouse = orders["warehouse_id"].to_numpy()
    hub = orders["hub_id"].to_numpy()
    region = orders["region"].to_numpy()
    quantity = orders["quantity"].to_numpy().astype(float)

    dist = np.zeros((n, 4))
    mode = np.empty((n, 4), dtype=object)
    for leg, stage in enumerate(STAGES):
        o_lat = np.array([lookup[i]["lat"] for i in origin_cols[leg]], dtype=float)
        o_lon = np.array([lookup[i]["lon"] for i in origin_cols[leg]], dtype=float)
        d_lat = np.array([lookup[i]["lat"] for i in dest_cols[leg]], dtype=float)
        d_lon = np.array([lookup[i]["lon"] for i in dest_cols[leg]], dtype=float)
        dist[:, leg] = np.maximum(_haversine(o_lat, o_lon, d_lat, d_lon), 12.0)
        mode[:, leg] = _mode_for_stage(dist[:, leg], stage, category if leg == 0 else None, rng)

    speed = np.vectorize(SPEED_KMH.get)(mode)
    handling = np.vectorize(HANDLING_H.get)(mode)
    nominal = dist / speed + handling
    # Fixed slack keeps short lanes from looking late just because a few minutes of jitter
    # consume a small percentage buffer. Baseline on-time stays high and stable.
    expected = nominal * 1.05 + 3.0
    actual = nominal * rng.lognormal(0.0, 0.045, size=(n, 4))
    # About 6% of dispatches miss the plan for ordinary operational reasons,
    # so the historical on-time rate sits near 94% instead of a perfect record.
    ordinary_late = rng.random(n) < 0.062
    if ordinary_late.any():
        actual[ordinary_late, 0] = expected[ordinary_late, 0] * rng.uniform(1.18, 1.55, int(ordinary_late.sum()))

    # W-042 inbound cycle time is a planned 2.8-day process, then slows to ~5.1 days.
    inbound = warehouse == INJECTED["warehouse_id"]
    pre = order_day < WAREHOUSE_DAY
    post = ~pre
    expected[inbound, 1] = INJECTED["warehouse_expected_days"] * 24.0
    if (inbound & pre).any():
        actual[inbound & pre, 1] = (
            INJECTED["warehouse_expected_days"] * 24.0 * rng.lognormal(0.0, 0.04, int((inbound & pre).sum())) * 0.97
        )
    if (inbound & post).any():
        actual[inbound & post, 1] = INJECTED["warehouse_observed_days"] * 24.0 * rng.lognormal(
            0.0, 0.035, int((inbound & post).sum())
        )

    # S-018 dispatch reliability falls from the natural ~94% band to ~71%.
    supplier_hit = (supplier == INJECTED["supplier_id"]) & (order_day >= SUPPLIER_DAY) & ~cancelled
    if supplier_hit.any():
        draw = rng.random(int(supplier_hit.sum())) < INJECTED["supplier_late_probability"]
        expected_dur = expected[supplier_hit, 0]
        revised = expected_dur * 0.90
        late_count = int(draw.sum())
        if late_count:
            revised[draw] = expected_dur[draw] * rng.uniform(1.32, 1.72, late_count)
        actual[supplier_hit, 0] = revised

    # France last-mile deterioration from August.
    france_hit = (region == INJECTED["region"]) & (order_day >= REGION_DAY) & ~cancelled
    if france_hit.any():
        draw = rng.random(int(france_hit.sum())) < INJECTED["region_late_probability"]
        extra = np.zeros(int(france_hit.sum()))
        if draw.any():
            extra[draw] = rng.uniform(22.0, 52.0, int(draw.sum()))
        actual[france_hit, 3] = actual[france_hit, 3] + extra

    exp_dep = np.zeros((n, 4))
    exp_arr = np.zeros((n, 4))
    act_dep = np.zeros((n, 4))
    act_arr = np.zeros((n, 4))
    exp_dep[:, 0] = order_day * 24.0 + 8.0
    act_dep[:, 0] = exp_dep[:, 0] + rng.uniform(0.0, 0.25, n)
    for leg in range(4):
        exp_arr[:, leg] = exp_dep[:, leg] + expected[:, leg]
        act_arr[:, leg] = act_dep[:, leg] + actual[:, leg]
        if leg < 3:
            exp_dep[:, leg + 1] = exp_arr[:, leg] + TRANSFER_H[leg]
            act_dep[:, leg + 1] = act_arr[:, leg] + TRANSFER_H[leg]

    act_arr = act_arr.copy()
    act_dep = act_dep.copy()
    act_arr[act_arr > AS_OF_HOUR] = np.nan
    act_dep[act_dep > AS_OF_HOUR] = np.nan

    fixed = np.vectorize(lambda m: COST_RATES[m][0])(mode)
    rate = np.vectorize(lambda m: COST_RATES[m][1])(mode)
    load = 0.65 + 0.35 * np.clip(quantity, 1, 200) / 40.0
    cost = (fixed + dist * rate) * load[:, None] * rng.uniform(0.94, 1.06, size=(n, 4))
    corridor = (warehouse == INJECTED["corridor_origin"]) & (hub == INJECTED["corridor_dest"]) & (order_day >= COST_DAY)
    cost[corridor, 2] = cost[corridor, 2] * INJECTED["corridor_multiplier"]

    delay = act_arr - exp_arr
    delay[np.isnan(act_arr)] = np.nan

    frames = []
    for leg, stage in enumerate(STAGES):
        origin_id = origin_cols[leg]
        dest_id = dest_cols[leg]
        frames.append(
            pd.DataFrame(
                {
                    "shipment_id": [f"SHP-{leg * n + i + 1:07d}" for i in range(n)],
                    "order_id": orders["order_id"].to_numpy(),
                    "leg_index": leg,
                    "stage": stage,
                    "origin_id": origin_id,
                    "origin_name": [lookup[i]["name"] for i in origin_id],
                    "origin_type": [lookup[i]["type"] for i in origin_id],
                    "origin_lat": [lookup[i]["lat"] for i in origin_id],
                    "origin_lon": [lookup[i]["lon"] for i in origin_id],
                    "origin_country": [lookup[i]["country"] for i in origin_id],
                    "dest_id": dest_id,
                    "dest_name": [lookup[i]["name"] for i in dest_id],
                    "dest_type": [lookup[i]["type"] for i in dest_id],
                    "dest_lat": [lookup[i]["lat"] for i in dest_id],
                    "dest_lon": [lookup[i]["lon"] for i in dest_id],
                    "dest_country": [lookup[i]["country"] for i in dest_id],
                    "mode": mode[:, leg],
                    "distance_km": np.round(dist[:, leg], 1),
                    "expected_departure": _hours_to_datetime(exp_dep[:, leg]),
                    "actual_departure": _hours_to_datetime(act_dep[:, leg]),
                    "expected_arrival": _hours_to_datetime(exp_arr[:, leg]),
                    "actual_arrival": _hours_to_datetime(act_arr[:, leg]),
                    "delay_hours": np.round(delay[:, leg], 2),
                    "shipping_cost": np.round(cost[:, leg], 2),
                    "supplier_id": orders["supplier_id"].to_numpy(),
                    "factory_id": orders["factory_id"].to_numpy(),
                    "warehouse_id": orders["warehouse_id"].to_numpy(),
                    "hub_id": orders["hub_id"].to_numpy(),
                    "customer_id": orders["customer_id"].to_numpy(),
                    "sku": orders["sku"].to_numpy(),
                    "region": orders["region"].to_numpy(),
                    "country": orders["country"].to_numpy(),
                    "order_date": orders["order_date"].to_numpy(),
                    "quantity": orders["quantity"].to_numpy(),
                    "cancelled": cancelled,
                }
            )
        )
    shipments = pd.concat(frames, ignore_index=True)
    shipments["on_time"] = np.where(
        shipments["actual_arrival"].isna(),
        np.nan,
        (shipments["actual_arrival"] <= shipments["expected_arrival"]).astype(float),
    )
    return shipments


def _finalize_orders(orders: pd.DataFrame, shipments: pd.DataFrame, masters: dict[str, pd.DataFrame]) -> pd.DataFrame:
    last = shipments[shipments["leg_index"] == 3][
        ["order_id", "expected_arrival", "actual_arrival", "shipping_cost"]
    ].rename(columns={"expected_arrival": "expected_delivery_date", "actual_arrival": "actual_delivery_date"})
    cost = shipments.groupby("order_id", sort=False)["shipping_cost"].sum().rename("logistics_cost")
    merged = orders.merge(last, on="order_id", how="left").merge(cost, on="order_id", how="left")
    status = np.full(len(merged), "on_time", dtype=object)
    status[merged["cancelled"].to_numpy()] = "cancelled"
    open_mask = merged["actual_delivery_date"].isna().to_numpy() & ~merged["cancelled"].to_numpy()
    status[open_mask] = "in_transit"
    delivered = ~merged["actual_delivery_date"].isna().to_numpy() & ~merged["cancelled"].to_numpy()
    late = delivered & (merged["actual_delivery_date"].to_numpy() > merged["expected_delivery_date"].to_numpy())
    status[late] = "delayed"
    merged["status"] = status
    merged.loc[merged["status"] == "cancelled", "actual_delivery_date"] = pd.NaT

    delivered_now = merged["status"].isin(["on_time", "delayed"])
    lead = (merged["actual_delivery_date"] - merged["order_date"]).dt.total_seconds() / 86400
    expected_lead = (merged["expected_delivery_date"] - merged["order_date"]).dt.total_seconds() / 86400
    delay_h = (merged["actual_delivery_date"] - merged["expected_delivery_date"]).dt.total_seconds() / 3600
    merged["lead_time_days"] = np.where(delivered_now, lead, np.nan)
    merged["expected_lead_time_days"] = expected_lead
    merged["delay_hours"] = np.where(delivered_now, np.maximum(delay_h.fillna(0), 0), np.nan)
    merged["late"] = merged["status"].eq("delayed")

    names = {
        "supplier_name": masters["suppliers"].set_index("supplier_id")["supplier_name"],
        "factory_name": masters["factories"].set_index("factory_id")["factory_name"],
        "warehouse_name": masters["warehouses"].set_index("warehouse_id")["warehouse_name"],
        "hub_name": masters["hubs"].set_index("hub_id")["hub_name"],
    }
    merged["supplier_name"] = merged["supplier_id"].map(names["supplier_name"])
    merged["factory_name"] = merged["factory_id"].map(names["factory_name"])
    merged["warehouse_name"] = merged["warehouse_id"].map(names["warehouse_name"])
    merged["hub_name"] = merged["hub_id"].map(names["hub_name"])
    keep = [
        "order_id",
        "sku",
        "product_name",
        "category",
        "quantity",
        "unit_cost",
        "customer_id",
        "customer_name",
        "region",
        "country",
        "city",
        "customer_lat",
        "customer_lon",
        "order_date",
        "expected_delivery_date",
        "actual_delivery_date",
        "status",
        "supplier_id",
        "supplier_name",
        "factory_id",
        "factory_name",
        "warehouse_id",
        "warehouse_name",
        "hub_id",
        "hub_name",
        "late",
        "lead_time_days",
        "expected_lead_time_days",
        "delay_hours",
        "logistics_cost",
        "order_day",
    ]
    return merged[keep].copy()


def _simulate_inventory(orders: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    active = orders[orders["status"] != "cancelled"].copy()
    active["order_day"] = active["order_day"].astype(int)
    rows: list[dict] = []
    product_cost = products.set_index("sku")["unit_cost"].to_dict()
    grouped = active.groupby(["warehouse_id", "sku", "order_day"], sort=False)["quantity"].sum()
    demand = {(wh, sku, int(day)): float(qty) for (wh, sku, day), qty in grouped.items()}
    pairs = active.groupby(["warehouse_id", "sku"], sort=False).size().reset_index()[["warehouse_id", "sku"]]

    for warehouse_id, sku in pairs.itertuples(index=False):
        daily = np.zeros(N_DAYS)
        for day in range(N_DAYS):
            daily[day] = demand.get((warehouse_id, sku, day), 0.0)
        annual_daily = float(daily.sum() / N_DAYS)
        recent = float(daily[-28:].sum() / 28.0)
        target = max(annual_daily * 21.0, 1.0)
        special = sku == INJECTED["sku"]

        def run(cutoff: int) -> tuple[float, list[tuple[int, float]]]:
            on_hand = target
            snapshots: list[tuple[int, float]] = []
            end_level = target
            for day in range(N_DAYS):
                if day % 7 == 0 and not (special and day >= cutoff):
                    on_hand = target
                on_hand = max(0.0, on_hand - daily[day])
                if day % 7 == 6 or day == N_DAYS - 1:
                    snapshots.append((day, on_hand))
                if day == N_DAYS - 1:
                    end_level = on_hand
            return end_level, snapshots

        if special and recent > 0:
            target_end = INJECTED["sku_target_coverage_days"] * recent
            best: tuple[float, int, float, list[tuple[int, float]]] | None = None
            for cutoff in range(N_DAYS - 70, N_DAYS - 5):
                end_level, snapshots = run(cutoff)
                if end_level <= 0:
                    continue
                error = abs(end_level - target_end)
                if best is None or error < best[0]:
                    best = (error, cutoff, end_level, snapshots)
            if best is None:
                _, snapshots = run(N_DAYS - 16)
                end_level = target_end
            else:
                _, _, end_level, snapshots = best
                coverage = end_level / recent
                if not 1.7 <= coverage <= 2.15:
                    end_level = target_end
                    # Reshape the tail so the stock-out is visible on the weekly series.
                    tail = [(day, level) for day, level in snapshots if day >= N_DAYS - 28]
                    head = [(day, level) for day, level in snapshots if day < N_DAYS - 28]
                    if tail:
                        start_level = head[-1][1] if head else target
                        for i, (day, _) in enumerate(tail):
                            frac = (i + 1) / len(tail)
                            tail[i] = (day, start_level + (end_level - start_level) * frac)
                        snapshots = head + tail
        else:
            end_level, snapshots = run(10**9)

        unit_cost = float(product_cost[sku])
        for day, level in snapshots:
            rows.append(
                {
                    "warehouse_id": warehouse_id,
                    "sku": sku,
                    "week_end": pd.Timestamp(EPOCH) + pd.Timedelta(days=int(day)),
                    "on_hand": round(float(level), 2),
                    "inventory_value": round(float(level) * unit_cost, 2),
                    "recent_daily_demand": round(recent, 3),
                    "annual_daily_demand": round(annual_daily, 3),
                }
            )
    return pd.DataFrame(rows)


def _update_master_metrics(
    masters: dict[str, pd.DataFrame],
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    inventory: pd.DataFrame,
) -> None:
    products = masters["products"]
    latest = inventory.sort_values("week_end").groupby(["warehouse_id", "sku"], sort=False).tail(1)
    demand = latest.set_index("sku")[["recent_daily_demand", "annual_daily_demand", "on_hand"]]
    # A SKU lives at one warehouse in this model.
    products = products.merge(demand, left_on="sku", right_index=True, how="left")
    products["average_daily_demand"] = products["recent_daily_demand"].fillna(0).round(2)
    products["annual_daily_demand"] = products["annual_daily_demand"].fillna(0).round(2)
    products["safety_stock"] = np.maximum(np.round(products["average_daily_demand"] * 7), 1).astype(int)
    special = products["sku"] == INJECTED["sku"]
    products.loc[special, "safety_stock"] = np.maximum(
        np.round(products.loc[special, "average_daily_demand"] * 7), 1
    ).astype(int)
    masters["products"] = products.drop(columns=["sample_weight", "on_hand"])

    anomaly_start = pd.Timestamp(date(2026, 7, 3))
    leg0 = shipments[(shipments["leg_index"] == 0) & (shipments["order_date"] < anomaly_start)].dropna(subset=["on_time"])
    stats = leg0.groupby("supplier_id").agg(
        historical_on_time_rate=("on_time", "mean"),
        average_lead_time=("delay_hours", "count"),
    )
    duration_h = (
        (leg0["actual_arrival"] - leg0["actual_departure"]).dt.total_seconds() / 3600
    )
    lead = duration_h.groupby(leg0["supplier_id"]).mean() / 24
    suppliers = masters["suppliers"].merge(
        stats[["historical_on_time_rate"]],
        left_on="supplier_id",
        right_index=True,
        how="left",
    )
    suppliers["average_lead_time"] = suppliers["supplier_id"].map(lead).fillna(2.5).round(2)
    suppliers["historical_on_time_rate"] = suppliers["historical_on_time_rate"].fillna(0.94).round(3)
    suppliers["risk_level"] = np.where(
        suppliers["historical_on_time_rate"] < 0.90,
        "high",
        np.where(suppliers["historical_on_time_rate"] < 0.945, "medium", "low"),
    )
    masters["suppliers"] = suppliers

    final = inventory[inventory["week_end"] == inventory["week_end"].max()]
    wh = final.groupby("warehouse_id").agg(current_inventory=("on_hand", "sum"), inventory_value=("inventory_value", "sum"))
    peak = inventory.groupby(["warehouse_id", "week_end"])["on_hand"].sum().groupby("warehouse_id").max()
    warehouses = masters["warehouses"].merge(wh, left_on="warehouse_id", right_index=True, how="left")
    warehouses["current_inventory"] = warehouses["current_inventory"].fillna(0).round(0).astype(int)
    warehouses["inventory_value"] = warehouses["inventory_value"].fillna(0).round(2)
    warehouses["capacity"] = (warehouses["warehouse_id"].map(peak).fillna(0) * 1.35).round(0).astype(int)
    warehouses.loc[warehouses["capacity"] < warehouses["current_inventory"], "capacity"] = (
        (warehouses["current_inventory"] * 1.25).round(0).astype(int)
    )
    masters["warehouses"] = warehouses


def _summary(orders: pd.DataFrame, shipments: pd.DataFrame, inventory: pd.DataFrame) -> dict:
    anomaly_start = pd.Timestamp(date(2026, 7, 3))
    delivered = orders[orders["status"].isin(["on_time", "delayed"])]
    baseline = delivered[delivered["order_date"] < anomaly_start]
    current = delivered[delivered["order_date"] >= anomaly_start]
    leg0 = shipments[(shipments["leg_index"] == 0) & (shipments["supplier_id"] == "S-018")].dropna(subset=["on_time"])
    inbound = shipments[(shipments["leg_index"] == 1) & (shipments["dest_id"] == "W-042")].dropna(subset=["actual_arrival"])
    inbound = inbound.copy()
    inbound["cycle_days"] = (inbound["actual_arrival"] - inbound["actual_departure"]).dt.total_seconds() / 86400
    lane = shipments[
        (shipments["leg_index"] == 2)
        & (shipments["origin_id"] == "W-055")
        & (shipments["dest_id"] == "H-330")
        & (shipments["distance_km"] > 0)
    ].copy()
    lane["cpk"] = lane["shipping_cost"] / lane["distance_km"]
    france = delivered[delivered["region"] == "France"]
    sku = inventory[(inventory["sku"] == "SKU-2841")].sort_values("week_end").tail(1)
    coverage = None
    on_hand = None
    recent = None
    if len(sku):
        on_hand = float(sku["on_hand"].iloc[0])
        recent = float(sku["recent_daily_demand"].iloc[0])
        coverage = on_hand / recent if recent else None

    def _rate(frame: pd.DataFrame, start=None, end=None) -> float | None:
        part = frame
        if start is not None:
            part = part[part["order_date"] >= start]
        if end is not None:
            part = part[part["order_date"] < end]
        if len(part) == 0:
            return None
        if "on_time" in part.columns:
            return float(part["on_time"].mean())
        return float((part["status"] == "on_time").mean())

    def _cycle(frame: pd.DataFrame, start, end) -> float | None:
        part = frame[(frame["order_date"] >= start) & (frame["order_date"] < end)]
        if len(part) == 0:
            return None
        return float(part["cycle_days"].mean())

    return {
        "orders": int(len(orders)),
        "shipments": int(len(shipments)),
        "otd_baseline": _rate(baseline),
        "otd_current": _rate(current),
        "s018_before": _rate(leg0, end=anomaly_start),
        "s018_after": _rate(leg0, start=anomaly_start),
        "w042_before": _cycle(inbound, pd.Timestamp(EPOCH), anomaly_start),
        "w042_after": _cycle(inbound, anomaly_start, pd.Timestamp(AS_OF) + pd.Timedelta(days=1)),
        "france_before": _rate(france, end=pd.Timestamp(date(2026, 8, 1))),
        "france_after": _rate(france, start=pd.Timestamp(date(2026, 8, 1))),
        "corridor_cpk_before": float(lane.loc[lane["order_date"] < pd.Timestamp(date(2026, 8, 1)), "cpk"].mean()) if len(lane) else None,
        "corridor_cpk_after": float(lane.loc[lane["order_date"] >= pd.Timestamp(date(2026, 8, 1)), "cpk"].mean()) if len(lane) else None,
        "sku2841_on_hand": on_hand,
        "sku2841_daily_demand": recent,
        "sku2841_coverage_days": coverage,
        "inventory_value": float(inventory[inventory["week_end"] == inventory["week_end"].max()]["inventory_value"].sum()),
    }


def generate_dataset(
    output_dir: Path | None = None,
    n_orders: int = 30_000,
    seed: int = 42,
    write: bool = True,
) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    masters = _build_masters(rng)
    raw_orders = _sample_orders(masters, rng, n_orders)
    shipments = _build_shipments(raw_orders, masters, rng)
    shipments["order_status_seed"] = np.where(shipments["cancelled"], "cancelled", "open")
    orders = _finalize_orders(raw_orders, shipments, masters)
    status_map = orders.set_index("order_id")["status"]
    shipments["order_status"] = shipments["order_id"].map(status_map)
    shipments = shipments.drop(columns=["cancelled", "order_status_seed"])
    inventory = _simulate_inventory(orders, masters["products"])
    _update_master_metrics(masters, orders, shipments, inventory)
    summary = _summary(orders, shipments, inventory)

    tables = {
        "suppliers": masters["suppliers"],
        "factories": masters["factories"],
        "warehouses": masters["warehouses"],
        "hubs": masters["hubs"],
        "customers": masters["customers"],
        "products": masters["products"],
        "orders": orders.drop(columns=["order_day"]),
        "shipments": shipments,
        "inventory": inventory,
    }
    if write:
        target = output_dir or DEFAULT_OUTPUT
        target.mkdir(parents=True, exist_ok=True)
        for name, frame in tables.items():
            frame.to_parquet(target / f"{name}.parquet", index=False)
        manifest = {
            "seed": seed,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "date_start": EPOCH.isoformat(),
            "date_end": AS_OF.isoformat(),
            "n_orders_requested": n_orders,
            "counts": {name: int(len(frame)) for name, frame in tables.items()},
            "diagnostics": summary,
            "injected_for_reproducibility": INJECTED,
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        print(json.dumps(manifest["counts"], indent=2))
        print(json.dumps(summary, indent=2, default=str))
    tables["summary"] = pd.DataFrame([summary])
    return tables


def main() -> None:
    generate_dataset()


if __name__ == "__main__":
    main()
