"""Detection and investigation checks against the seeded dataset."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.analytics.anomalies import detect_anomalies
from app.analytics.filters import baseline_selection, default_window, selection_from_dates
from app.analytics.investigation import investigate
from app.analytics.journey import build_journey
from app.main import app
from app.services.store import get_store


def _window():
    store = get_store()
    start, end = default_window(store.data_start.date(), store.data_end.date())
    sel = selection_from_dates(start, end)
    baseline = baseline_selection(sel, store.data_start)
    return store, sel, baseline


def test_dataset_shape():
    store = get_store()
    assert len(store.suppliers) == 50
    assert len(store.factories) == 5
    assert len(store.warehouses) == 10
    assert len(store.hubs) == 15
    assert len(store.products) == 100
    assert len(store.orders) == 30_000
    assert len(store.shipments) == 120_000
    assert set(store.orders["status"]) >= {"on_time", "delayed", "in_transit", "cancelled"}


def test_injected_anomalies_are_detected():
    store, sel, baseline = _window()
    alerts = detect_anomalies(
        store.orders,
        store.shipments,
        store.inventory,
        store.products,
        store.warehouses,
        store.suppliers,
        sel,
        baseline,
    )
    by_id = {alert["entity_id"]: alert for alert in alerts}
    assert "S-018" in by_id
    assert by_id["S-018"]["type"] == "supplier_otd"
    assert by_id["S-018"]["observed_value"] < 0.8
    assert by_id["S-018"]["expected_value"] > 0.9
    assert "W-042" in by_id
    assert by_id["W-042"]["type"] == "warehouse_delay"
    assert by_id["W-042"]["observed_value"] > 4.5
    assert by_id["W-042"]["expected_value"] < 3.2
    assert "SKU-2841" in by_id
    assert by_id["SKU-2841"]["type"] == "stockout_risk"
    assert by_id["SKU-2841"]["observed_value"] < 3
    assert "France" in by_id
    assert any(alert["type"] == "route_cost" and "W-055" in alert["entity_id"] and "H-330" in alert["entity_id"] for alert in alerts)


def test_investigation_ranks_w042_and_sums_contribution():
    store, sel, baseline = _window()
    names = {
        "supplier": store.suppliers.set_index("supplier_id")["supplier_name"],
        "warehouse": store.warehouses.set_index("warehouse_id")["warehouse_name"],
        "product": store.products.set_index("sku")["product_name"],
        "node": store.warehouses.set_index("warehouse_id")["warehouse_name"],
    }
    result = investigate(store.orders, store.shipments, store.inventory, store.products, sel, baseline, "otd", [], names)
    assert result["current"] < result["baseline"]
    top = result["rows"][0]
    assert top["id"] == "W-042" or top["id"] in {"DACH", "France", "W-042"}
    # First dimension is region. W-042's volume lands mostly in DACH.
    assert result["dimension"] == "region"
    share = sum(row["contribution"] or 0 for row in result["rows"])
    assert 0.98 <= share <= 1.01
    drilled = investigate(
        store.orders,
        store.shipments,
        store.inventory,
        store.products,
        sel,
        baseline,
        "otd",
        [{"dimension": "region", "value": "DACH", "label": "DACH"}],
        names,
    )
    assert drilled["dimension"] == "warehouse"
    assert drilled["rows"][0]["id"] == "W-042"


def test_journey_identifies_a_real_origin():
    store = get_store()
    order = store.orders[(store.orders["status"] == "delayed") & (store.orders["warehouse_id"] == "W-042")].iloc[0]
    legs = store.shipments[store.shipments["order_id"] == order["order_id"]]
    journey = build_journey(order, legs)
    assert len(journey["stages"]) == 6
    assert journey["origin_stage"] == "Warehouse"
    assert any(stage["origin"] for stage in journey["stages"])
    assert any(stage["propagated"] for stage in journey["stages"])
    assert "hours longer than planned" in journey["narrative"]


def test_api_meta_kpis_and_filters():
    client = TestClient(app)
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    body = meta.json()
    assert body["default_start"] < body["default_end"]
    kpis = client.get("/api/kpis")
    assert kpis.status_code == 200
    payload = kpis.json()
    assert payload["orders"]["value"] > 1000
    assert payload["otd"]["value"] < payload["otd"]["baseline"]
    narrowed = client.get("/api/kpis", params={"warehouse": "W-042"})
    assert narrowed.status_code == 200
    assert narrowed.json()["orders"]["value"] < payload["orders"]["value"]
    missing = client.get("/api/orders/DOES-NOT-EXIST/journey")
    assert missing.status_code == 404
    journey = client.get(f"/api/orders/{body['example_order_id']}/journey")
    assert journey.status_code == 200
    assert journey.json()["origin_stage"]
    bad = client.get("/api/kpis", params={"start": "2026-09-01", "end": "2026-01-01"})
    assert bad.status_code == 422
