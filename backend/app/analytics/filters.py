"""Filter orders and shipments with one selection object."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

import pandas as pd

from app.analytics.common import delivered


@dataclass(frozen=True)
class Selection:
    start: pd.Timestamp
    end: pd.Timestamp
    region: str | None = None
    country: str | None = None
    supplier: str | None = None
    warehouse: str | None = None
    factory: str | None = None
    product: str | None = None
    mode: str | None = None
    status: str | None = None
    customer: str | None = None

    def key(self) -> tuple:
        return (
            self.start.date().isoformat(),
            self.end.date().isoformat(),
            self.region,
            self.country,
            self.supplier,
            self.warehouse,
            self.factory,
            self.product,
            self.mode,
            self.status,
            self.customer,
        )


def selection_from_dates(
    start: date,
    end: date,
    **kwargs: str | None,
) -> Selection:
    return Selection(start=pd.Timestamp(start), end=pd.Timestamp(end), **kwargs)


def window_bounds(sel: Selection) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Inclusive start, exclusive end."""
    return sel.start.normalize(), (sel.end.normalize() + pd.Timedelta(days=1))


def baseline_selection(sel: Selection, data_start: pd.Timestamp) -> Selection | None:
    length_days = (sel.end.normalize() - sel.start.normalize()).days
    if length_days < 7:
        return None
    baseline_end = sel.start.normalize() - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=length_days)
    data_floor = pd.Timestamp(data_start).normalize()
    if baseline_end < data_floor:
        return None
    if baseline_start < data_floor:
        baseline_start = data_floor
    if (baseline_end - baseline_start).days < 14:
        return None
    return replace(sel, start=baseline_start, end=baseline_end)


def _mask_common(frame: pd.DataFrame, sel: Selection) -> pd.Series:
    start, end = window_bounds(sel)
    mask = (frame["order_date"] >= start) & (frame["order_date"] < end)
    if sel.region:
        mask &= frame["region"].eq(sel.region)
    if sel.country:
        mask &= frame["country"].eq(sel.country)
    if sel.supplier:
        mask &= frame["supplier_id"].eq(sel.supplier)
    if sel.warehouse:
        mask &= frame["warehouse_id"].eq(sel.warehouse)
    if sel.factory:
        mask &= frame["factory_id"].eq(sel.factory)
    if sel.product:
        mask &= frame["sku"].eq(sel.product)
    if sel.customer and "customer_id" in frame.columns:
        mask &= frame["customer_id"].eq(sel.customer)
    return mask


def filter_shipments(shipments: pd.DataFrame, sel: Selection) -> pd.DataFrame:
    mask = _mask_common(shipments, sel)
    if sel.mode:
        mask &= shipments["mode"].eq(sel.mode)
    if sel.status:
        mask &= shipments["order_status"].eq(sel.status)
    return shipments.loc[mask]


def filter_orders(orders: pd.DataFrame, sel: Selection, shipments: pd.DataFrame | None = None) -> pd.DataFrame:
    mask = _mask_common(orders, sel)
    if sel.status:
        mask &= orders["status"].eq(sel.status)
    narrowed = orders.loc[mask]
    if sel.mode and shipments is not None:
        ids = filter_shipments(shipments, sel)["order_id"].unique()
        narrowed = narrowed[narrowed["order_id"].isin(ids)]
    return narrowed


def period_payload(sel: Selection | None) -> dict | None:
    if sel is None:
        return None
    return {
        "start": sel.start.date().isoformat(),
        "end": sel.end.date().isoformat(),
        "days": int((sel.end.normalize() - sel.start.normalize()).days) + 1,
    }


def default_window(data_start: date, data_end: date) -> tuple[date, date]:
    start = data_end - timedelta(days=89)
    if start < data_start:
        start = data_start
    return start, data_end


def slice_delivered(orders: pd.DataFrame) -> pd.DataFrame:
    return delivered(orders)
