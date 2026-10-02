"""Supply Chain Control Tower API."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(BACKEND)):
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="Supply Chain Control Tower API",
    description=(
        "Aggregated analytics for an interactive supply-chain control tower. "
        "The underlying network is synthetic. Anomaly detection uses baseline comparisons, "
        "z-scores, rolling windows, IQR fences and a linear cost model."
    ),
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "name": "Supply Chain Control Tower",
        "docs": "/docs",
        "meta": "/api/meta",
    }
