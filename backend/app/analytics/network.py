"""Aggregated supply-chain graph for geographic and topology views."""

from __future__ import annotations

import pandas as pd
import networkx as nx

from app.analytics.common import mean_or_none, num
from app.analytics.filters import Selection, filter_orders, filter_shipments


def _lookup(store_frames: dict[str, pd.DataFrame]) -> dict[str, dict]:
    nodes: dict[str, dict] = {}

    def add(frame: pd.DataFrame, id_col: str, name_col: str, kind: str) -> None:
        for row in frame.itertuples(index=False):
            nodes[getattr(row, id_col)] = {
                "id": getattr(row, id_col),
                "name": getattr(row, name_col),
                "type": kind,
                "city": row.city,
                "country": row.country,
                "lat": float(row.latitude),
                "lon": float(row.longitude),
                "region": getattr(row, "region", None),
            }

    add(store_frames["suppliers"], "supplier_id", "supplier_name", "supplier")
    add(store_frames["factories"], "factory_id", "factory_name", "factory")
    add(store_frames["warehouses"], "warehouse_id", "warehouse_name", "warehouse")
    add(store_frames["hubs"], "hub_id", "hub_name", "hub")
    add(store_frames["customers"], "customer_id", "customer_name", "customer")
    return nodes


def build_network(
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    inventory: pd.DataFrame,
    masters: dict[str, pd.DataFrame],
    sel: Selection,
) -> dict:
    current_orders = filter_orders(orders, sel, shipments)
    current_shipments = filter_shipments(shipments, sel)
    catalog = _lookup(masters)
    done = current_orders[current_orders["status"].isin(["on_time", "delayed"])]

    snap = inventory[inventory["week_end"] <= sel.end]
    latest = (
        snap.sort_values("week_end").groupby(["warehouse_id", "sku"], sort=False).tail(1)
        if not snap.empty
        else snap
    )
    stock = latest.groupby("warehouse_id").agg(units=("on_hand", "sum"), value=("inventory_value", "sum")) if not latest.empty else pd.DataFrame()
    coverage = pd.Series(dtype=float)
    if not latest.empty:
        demand = latest["recent_daily_demand"].replace(0, pd.NA)
        latest = latest.assign(cover=latest["on_hand"] / demand)
        coverage = latest.groupby("warehouse_id")["cover"].min()

    def order_stats(column: str) -> pd.DataFrame:
        if current_orders.empty:
            return pd.DataFrame(columns=["orders", "otd", "quantity"])
        base = current_orders.groupby(column).agg(orders=("order_id", "count"), quantity=("quantity", "sum"))
        if done.empty:
            base["otd"] = pd.NA
        else:
            base["otd"] = done.groupby(column)["status"].apply(lambda s: float((s == "on_time").mean()))
        return base

    stats = {
        "supplier": order_stats("supplier_id"),
        "factory": order_stats("factory_id"),
        "warehouse": order_stats("warehouse_id"),
        "hub": order_stats("hub_id"),
        "customer": order_stats("customer_id"),
    }

    delayed_in = (
        current_shipments[current_shipments["delay_hours"].fillna(0) > 1].groupby("dest_id").size()
        if not current_shipments.empty
        else pd.Series(dtype=int)
    )
    delayed_out = (
        current_shipments[current_shipments["delay_hours"].fillna(0) > 1].groupby("origin_id").size()
        if not current_shipments.empty
        else pd.Series(dtype=int)
    )
    touch = pd.Series(dtype=int)
    if not current_shipments.empty:
        touch = pd.concat([current_shipments["origin_id"], current_shipments["dest_id"]]).value_counts()

    active_ids = set(touch.index.astype(str))
    graph = nx.Graph()
    edges = []
    if not current_shipments.empty:
        grouped = current_shipments.groupby(["origin_id", "dest_id"], sort=False)
        for (origin, dest), part in grouped:
            if origin not in catalog or dest not in catalog:
                continue
            on_time = part["on_time"].dropna()
            edges.append(
                {
                    "source": str(origin),
                    "target": str(dest),
                    "shipments": int(len(part)),
                    "quantity": int(part["quantity"].sum()),
                    "cost": num(part["shipping_cost"].sum(), 2),
                    "otd": num(on_time.mean(), 4) if len(on_time) else None,
                    "avg_delay_hours": num(mean_or_none(part["delay_hours"]), 2),
                    "mode": str(part["mode"].mode().iloc[0]) if not part["mode"].mode().empty else None,
                }
            )
            graph.add_edge(str(origin), str(dest), weight=int(len(part)))
            active_ids.add(str(origin))
            active_ids.add(str(dest))

    centrality = nx.betweenness_centrality(graph) if graph.number_of_nodes() else {}
    nodes = []
    for node_id in active_ids:
        meta = catalog.get(node_id)
        if meta is None:
            continue
        table = stats.get(meta["type"], pd.DataFrame())
        row = table.loc[node_id] if node_id in table.index else None
        wh_stock = stock.loc[node_id] if meta["type"] == "warehouse" and node_id in getattr(stock, "index", []) else None
        nodes.append(
            {
                "id": node_id,
                "type": meta["type"],
                "name": meta["name"],
                "label": f"{node_id} · {meta['name']}",
                "city": meta["city"],
                "country": meta["country"],
                "region": meta["region"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "orders": int(row["orders"]) if row is not None else 0,
                "quantity": int(row["quantity"]) if row is not None else 0,
                "shipments": int(touch.get(node_id, 0)),
                "otd": num(row["otd"], 4) if row is not None else None,
                "inventory_units": num(wh_stock["units"], 1) if wh_stock is not None else None,
                "inventory_value": num(wh_stock["value"], 2) if wh_stock is not None else None,
                "stock_coverage": num(coverage.get(node_id), 2) if meta["type"] == "warehouse" else None,
                "delayed_inbound": int(delayed_in.get(node_id, 0)),
                "delayed_outbound": int(delayed_out.get(node_id, 0)),
                "betweenness": num(centrality.get(node_id, 0.0), 4),
            }
        )
    nodes.sort(key=lambda item: (-item["shipments"], item["id"]))
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "orders": int(len(current_orders)),
            "shipments": int(len(current_shipments)),
        },
    }
