"""Load generated tables once and share them across requests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.generator.generate import generate_dataset  # noqa: E402


class DataStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.generated = self.root / "data" / "generated"
        self.manifest: dict = {}
        self.suppliers = pd.DataFrame()
        self.factories = pd.DataFrame()
        self.warehouses = pd.DataFrame()
        self.hubs = pd.DataFrame()
        self.customers = pd.DataFrame()
        self.products = pd.DataFrame()
        self.orders = pd.DataFrame()
        self.shipments = pd.DataFrame()
        self.inventory = pd.DataFrame()
        self.load()

    def load(self) -> None:
        if not (self.generated / "orders.parquet").exists():
            generate_dataset(output_dir=self.generated)
        self.suppliers = pd.read_parquet(self.generated / "suppliers.parquet")
        self.factories = pd.read_parquet(self.generated / "factories.parquet")
        self.warehouses = pd.read_parquet(self.generated / "warehouses.parquet")
        self.hubs = pd.read_parquet(self.generated / "hubs.parquet")
        self.customers = pd.read_parquet(self.generated / "customers.parquet")
        self.products = pd.read_parquet(self.generated / "products.parquet")
        self.orders = pd.read_parquet(self.generated / "orders.parquet")
        self.shipments = pd.read_parquet(self.generated / "shipments.parquet")
        self.inventory = pd.read_parquet(self.generated / "inventory.parquet")
        manifest_path = self.generated / "manifest.json"
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        for column in ("order_date", "expected_delivery_date", "actual_delivery_date"):
            self.orders[column] = pd.to_datetime(self.orders[column])
        for column in (
            "order_date",
            "expected_departure",
            "actual_departure",
            "expected_arrival",
            "actual_arrival",
        ):
            self.shipments[column] = pd.to_datetime(self.shipments[column])
        self.inventory["week_end"] = pd.to_datetime(self.inventory["week_end"])

    @property
    def data_start(self) -> pd.Timestamp:
        return pd.Timestamp(self.manifest.get("date_start") or self.orders["order_date"].min())

    @property
    def data_end(self) -> pd.Timestamp:
        return pd.Timestamp(self.manifest.get("date_end") or self.orders["order_date"].max())


STORE: DataStore | None = None


def get_store() -> DataStore:
    global STORE
    if STORE is None:
        STORE = DataStore()
    return STORE
