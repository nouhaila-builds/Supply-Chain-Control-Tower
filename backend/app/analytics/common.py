"""Small helpers shared by analytical modules."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

DELIVERED = ("on_time", "delayed")


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def num(value: Any, digits: int | None = None) -> float | None:
    if is_missing(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    if digits is not None:
        return round(out, digits)
    return out


def integer(value: Any) -> int | None:
    parsed = num(value)
    if parsed is None:
        return None
    return int(round(parsed))


def iso(value: Any) -> str | None:
    if is_missing(value):
        return None
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        return None
    return stamp.isoformat(timespec="minutes")


def week_start(series: pd.Series) -> pd.Series:
    stamps = pd.to_datetime(series)
    return stamps.dt.to_period("W-SUN").dt.start_time


def safe_rate(numerator: float, denominator: float) -> float | None:
    if denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def mean_or_none(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return float(clean.mean())


def std_or_floor(series: pd.Series, floor: float) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 3:
        return floor
    sigma = float(clean.std(ddof=1))
    if not math.isfinite(sigma) or sigma < floor:
        return floor
    return sigma


def delivered(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return orders
    return orders[orders["status"].isin(DELIVERED)]


def zscore(observed: float, baseline: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return (observed - baseline) / sigma


def clamp_share(values: list[float]) -> list[float]:
    positive = [max(0.0, value) for value in values]
    total = sum(positive)
    if total <= 0:
        return [0.0 for _ in values]
    return [value / total for value in positive]


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    cleaned = frame.replace({np.nan: None})
    return cleaned.to_dict(orient="records")
