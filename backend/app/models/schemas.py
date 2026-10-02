"""Query validation and documented response shapes."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class FilterQuery(BaseModel):
    start: date | None = None
    end: date | None = None
    region: str | None = None
    country: str | None = None
    supplier: str | None = None
    warehouse: str | None = None
    factory: str | None = None
    product: str | None = None
    mode: str | None = None
    status: str | None = None
    customer: str | None = None


class PeriodModel(BaseModel):
    start: str
    end: str
    days: int


class KpiValue(BaseModel):
    value: float | None = None
    baseline: float | None = None
    delta: float | None = None
    delta_unit: str | None = None
    unit: str


class KpiResponse(BaseModel):
    window: PeriodModel | None = None
    baseline_window: PeriodModel | None = None
    orders: KpiValue
    otd: KpiValue
    inventory_value: KpiValue
    lead_time: KpiValue
    delayed_shipments: KpiValue
    logistics_cost: KpiValue
    alerts: KpiValue
    delivered_orders: int = 0
    late_orders: int = 0


class AnomalyContext(BaseModel):
    metric: str
    steps: list[dict[str, str]]
    filters: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class AnomalyModel(BaseModel):
    id: str
    severity: str
    type: str
    entity_type: str
    entity_id: str
    entity_label: str
    metric: str
    expected_value: float | None
    observed_value: float | None
    deviation: float | None
    deviation_pct: float | None
    unit: str
    method: str
    timestamp: str
    location: str
    summary: str
    context: AnomalyContext


class InvestigationRow(BaseModel):
    id: str
    label: str
    volume: int | None = None
    current: float | None = None
    baseline: float | None = None
    deviation: float | None = None
    excess: float | None = None
    contribution: float | None = None
    drillable: bool = False
    order_id: str | None = None


class InvestigationResponse(BaseModel):
    metric: str
    metric_label: str
    unit: str
    question: str
    dimension: str
    volume_label: str
    window: PeriodModel | None = None
    baseline_window: PeriodModel | None = None
    current: float | None = None
    baseline: float | None = None
    deviation: float | None = None
    deviation_pct: float | None = None
    volume: int | None = None
    breadcrumb: list[dict[str, str]]
    rows: list[InvestigationRow]
    evidence: list[str]
    steps: list[dict[str, str]]
