"""HTTP API. Aggregations stay on the server; responses are already filtered."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.analytics.anomalies import detect_anomalies
from app.analytics.filters import Selection, baseline_selection, default_window, selection_from_dates
from app.analytics.finance import cost_service, inventory_view
from app.analytics.investigation import investigate
from app.analytics.journey import build_journey, example_delayed_order, search_orders
from app.analytics.kpis import compute_kpis
from app.analytics.network import build_network
from app.analytics.trends import kpi_breakdown, performance_trends
from app.models.schemas import AnomalyModel, InvestigationResponse, KpiResponse
from app.services.store import DataStore, get_store

router = APIRouter()
_CACHE: dict[tuple, object] = {}


def _cached(key: tuple, builder):
    if key not in _CACHE:
        if len(_CACHE) > 48:
            _CACHE.clear()
        _CACHE[key] = builder()
    return _CACHE[key]


def _selection(
    store: DataStore,
    start: date | None,
    end: date | None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> Selection:
    data_start = store.data_start.date()
    data_end = store.data_end.date()
    if start is None or end is None:
        start, end = default_window(data_start, data_end)
    if start < data_start:
        start = data_start
    if end > data_end:
        end = data_end
    if start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    return selection_from_dates(
        start,
        end,
        region=region or None,
        country=country or None,
        supplier=supplier or None,
        warehouse=warehouse or None,
        factory=factory or None,
        product=product or None,
        mode=mode or None,
        status=status or None,
        customer=customer or None,
    )


def _names(store: DataStore) -> dict:
    pieces = [
        store.suppliers.set_index("supplier_id")["supplier_name"],
        store.factories.set_index("factory_id")["factory_name"],
        store.warehouses.set_index("warehouse_id")["warehouse_name"],
        store.hubs.set_index("hub_id")["hub_name"],
        store.customers.set_index("customer_id")["customer_name"],
    ]
    import pandas as pd

    return {
        "supplier": pieces[0],
        "factory": pieces[1],
        "warehouse": pieces[2],
        "hub": pieces[3],
        "customer": pieces[4],
        "product": store.products.set_index("sku")["product_name"],
        "node": pd.concat(pieces),
    }


def _parse_steps(drill: list[str] | None) -> list[dict]:
    steps = []
    for item in drill or []:
        dimension, separator, value = item.partition(":")
        if separator and dimension and value:
            steps.append({"dimension": dimension, "value": value, "label": value})
    return steps


def _anomalies(store: DataStore, sel: Selection, baseline: Selection | None) -> list[dict]:
    return _cached(
        ("anomalies", sel.key(), None if baseline is None else baseline.key()),
        lambda: detect_anomalies(
            store.orders,
            store.shipments,
            store.inventory,
            store.products,
            store.warehouses,
            store.suppliers,
            sel,
            baseline,
        ),
    )


@router.get("/meta")
def meta() -> dict:
    store = get_store()
    start, end = default_window(store.data_start.date(), store.data_end.date())
    counts = store.manifest.get("counts", {})
    return {
        "title": "Supply Chain Control Tower",
        "subtitle": "Interactive Visual Analytics for Supply Chain Operations",
        "seed": store.manifest.get("seed", 42),
        "generated_at": store.manifest.get("generated_at"),
        "date_start": store.data_start.date().isoformat(),
        "date_end": store.data_end.date().isoformat(),
        "default_start": start.isoformat(),
        "default_end": end.isoformat(),
        "counts": counts,
        "example_order_id": example_delayed_order(store.orders),
        "dataset": "synthetic",
    }


@router.get("/filters/options")
def filter_options() -> dict:
    store = get_store()
    return {
        "regions": sorted(store.orders["region"].dropna().unique().tolist()),
        "countries": sorted(store.orders["country"].dropna().unique().tolist()),
        "suppliers": [
            {"id": row.supplier_id, "label": f"{row.supplier_id} · {row.supplier_name}"}
            for row in store.suppliers.sort_values("supplier_id").itertuples(index=False)
        ],
        "warehouses": [
            {"id": row.warehouse_id, "label": f"{row.warehouse_id} · {row.warehouse_name}"}
            for row in store.warehouses.sort_values("warehouse_id").itertuples(index=False)
        ],
        "factories": [
            {"id": row.factory_id, "label": f"{row.factory_id} · {row.factory_name}"}
            for row in store.factories.sort_values("factory_id").itertuples(index=False)
        ],
        "products": [
            {"id": row.sku, "label": f"{row.sku} · {row.product_name}"}
            for row in store.products.sort_values("sku").itertuples(index=False)
        ],
        "modes": sorted(store.shipments["mode"].dropna().unique().tolist()),
        "statuses": ["on_time", "delayed", "in_transit", "cancelled"],
    }


@router.get("/kpis", response_model=KpiResponse)
def kpis(
    start: date | None = None,
    end: date | None = None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> dict:
    store = get_store()
    sel = _selection(store, start, end, region, country, supplier, warehouse, factory, product, mode, status, customer)
    baseline = baseline_selection(sel, store.data_start)
    alerts = _anomalies(store, sel, baseline)
    baseline_alerts = None
    if baseline is not None:
        prior = baseline_selection(baseline, store.data_start)
        baseline_alerts = len(_anomalies(store, baseline, prior))
    return compute_kpis(store.orders, store.shipments, store.inventory, sel, baseline, len(alerts), baseline_alerts)


@router.get("/performance/trends")
def trends(
    start: date | None = None,
    end: date | None = None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> dict:
    store = get_store()
    sel = _selection(store, start, end, region, country, supplier, warehouse, factory, product, mode, status, customer)
    baseline = baseline_selection(sel, store.data_start)
    names = _names(store)
    return _cached(
        ("trends", sel.key()),
        lambda: performance_trends(
            store.orders,
            store.shipments,
            store.inventory,
            sel,
            baseline,
            names["supplier"],
        ),
    )


@router.get("/performance/breakdown")
def breakdown(
    kpi: str = Query("otd"),
    start: date | None = None,
    end: date | None = None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> dict:
    allowed = {"orders", "otd", "delayed_shipments", "lead_time", "logistics_cost", "inventory_value", "alerts"}
    if kpi not in allowed:
        raise HTTPException(status_code=422, detail=f"kpi must be one of {sorted(allowed)}")
    store = get_store()
    sel = _selection(store, start, end, region, country, supplier, warehouse, factory, product, mode, status, customer)
    return kpi_breakdown(kpi, store.orders, store.shipments, store.inventory, sel, _names(store))


@router.get("/network")
def network(
    start: date | None = None,
    end: date | None = None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> dict:
    store = get_store()
    sel = _selection(store, start, end, region, country, supplier, warehouse, factory, product, mode, status, customer)
    masters = {
        "suppliers": store.suppliers,
        "factories": store.factories,
        "warehouses": store.warehouses,
        "hubs": store.hubs,
        "customers": store.customers,
    }
    return _cached(
        ("network", sel.key()),
        lambda: build_network(store.orders, store.shipments, store.inventory, masters, sel),
    )


@router.get("/anomalies", response_model=list[AnomalyModel])
def anomalies(
    start: date | None = None,
    end: date | None = None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> list[dict]:
    store = get_store()
    sel = _selection(store, start, end, region, country, supplier, warehouse, factory, product, mode, status, customer)
    baseline = baseline_selection(sel, store.data_start)
    return _anomalies(store, sel, baseline)


@router.get("/investigation", response_model=InvestigationResponse)
def investigation(
    metric: str = Query("otd"),
    drill: list[str] | None = Query(default=None),
    start: date | None = None,
    end: date | None = None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> dict:
    allowed = {"otd", "lead_time", "logistics_cost", "stock_coverage"}
    if metric not in allowed:
        raise HTTPException(status_code=422, detail=f"metric must be one of {sorted(allowed)}")
    store = get_store()
    sel = _selection(store, start, end, region, country, supplier, warehouse, factory, product, mode, status, customer)
    baseline = baseline_selection(sel, store.data_start)
    steps = _parse_steps(drill)
    return _cached(
        ("investigation", metric, tuple(drill or []), sel.key()),
        lambda: investigate(
            store.orders,
            store.shipments,
            store.inventory,
            store.products,
            sel,
            baseline,
            metric,
            steps,
            _names(store),
        ),
    )


@router.get("/orders/search")
def order_search(q: str = Query("", min_length=0, max_length=80)) -> dict:
    store = get_store()
    return {"results": search_orders(store.orders, q)}


@router.get("/orders/{order_id}/journey")
def order_journey(order_id: str) -> dict:
    store = get_store()
    match = store.orders[store.orders["order_id"] == order_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Order {order_id} was not found")
    legs = store.shipments[store.shipments["order_id"] == order_id]
    return build_journey(match.iloc[0], legs)


@router.get("/inventory")
def inventory(
    start: date | None = None,
    end: date | None = None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> dict:
    store = get_store()
    sel = _selection(store, start, end, region, country, supplier, warehouse, factory, product, mode, status, customer)
    return _cached(
        ("inventory", sel.key()),
        lambda: inventory_view(store.orders, store.shipments, store.inventory, store.products, store.warehouses, sel),
    )


@router.get("/costs")
def costs(
    start: date | None = None,
    end: date | None = None,
    region: str | None = None,
    country: str | None = None,
    supplier: str | None = None,
    warehouse: str | None = None,
    factory: str | None = None,
    product: str | None = None,
    mode: str | None = None,
    status: str | None = None,
    customer: str | None = None,
) -> dict:
    store = get_store()
    sel = _selection(store, start, end, region, country, supplier, warehouse, factory, product, mode, status, customer)
    return _cached(
        ("costs", sel.key()),
        lambda: cost_service(store.orders, store.shipments, sel, _names(store)),
    )
