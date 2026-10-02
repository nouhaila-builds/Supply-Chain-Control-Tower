import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getJson } from "../services/api";
import { useTower } from "../store/useTower";
import type { Anomaly, Kpis, NetworkData, NetworkNode } from "../types";
import { formatDelta, formatNumber, formatPct, formatUnit } from "../lib/format";
import { emphasisFor, healthStatement } from "../lib/locate";
import { ErrorBlock, LoadingBlock } from "../components/States";
import { GeoMap } from "../visualizations/GeoMap";
import { Topology } from "../visualizations/Topology";

type SizeKey = "shipments" | "orders" | "inventory_units" | "inventory_value";

export function NetworkView() {
  const filters = useTower((state) => state.filters);
  const ready = useTower((state) => state.ready);
  const setFocus = useTower((state) => state.setFocus);
  const emphasisIds = useTower((state) => state.emphasisIds);
  const startGuide = useTower((state) => state.startGuide);
  const navigate = useNavigate();
  const [mode, setMode] = useState<"geo" | "topo">("geo");
  const [sizeKey, setSizeKey] = useState<SizeKey>("shipments");
  const [hover, setHover] = useState<{ node: NetworkNode; x: number; y: number } | null>(null);
  const network = useQuery({ queryKey: ["network", filters], enabled: ready, queryFn: () => getJson<NetworkData>("/network", filters) });
  const kpis = useQuery({ queryKey: ["kpis", filters], enabled: ready, queryFn: () => getJson<Kpis>("/kpis", filters) });
  const anomalies = useQuery({ queryKey: ["anomalies", filters], enabled: ready, queryFn: () => getJson<Anomaly[]>("/anomalies", filters) });

  if (network.isLoading) return <LoadingBlock label="Building the network" />;
  if (network.isError || !network.data) return <ErrorBlock message="The network could not be loaded." onRetry={() => network.refetch()} />;

  const top = anomalies.data?.[0];
  const signalCount = anomalies.data?.length ?? kpis.data?.alerts.value ?? 0;

  function select(node: NetworkNode) {
    setFocus({ kind: "node", id: node.id }, [node.id]);
  }

  function openIssue(alert: Anomaly) {
    setFocus({ kind: "anomaly", id: alert.id }, emphasisFor(alert, network.data?.nodes ?? []));
  }

  return (
    <section className="network-page">
      <div className="band">
        <p className="band-sentence">{kpis.data ? healthStatement(kpis.data) : "Reading the current window…"}</p>
        <div className="band-figures">
          <span>On-time <strong className={(kpis.data?.otd.delta ?? 0) < 0 ? "bad" : ""}>{kpis.data ? formatUnit(kpis.data.otd.value, kpis.data.otd.unit) : "—"}</strong> <em className={(kpis.data?.otd.delta ?? 0) < 0 ? "bad" : ""}>{kpis.data ? formatDelta(kpis.data.otd.delta, kpis.data.otd.delta_unit) : ""}</em></span>
          <span>Lead <strong>{kpis.data ? formatUnit(kpis.data.lead_time.value, kpis.data.lead_time.unit) : "—"}</strong></span>
          <button className="text-btn" onClick={() => navigate("/detect")}>{formatNumber(signalCount)} signals</button>
          {top && (
            <button className="band-issue" onClick={() => openIssue(top)}>
              {top.entity_label}
            </button>
          )}
          <button className="text-btn" onClick={startGuide}>Walk a disruption</button>
        </div>
      </div>
      <div className="network-stage">
        <div className="stage">
          <div className="map-tools">
            <div className="seg">
              <button className={mode === "geo" ? "on" : ""} onClick={() => setMode("geo")}>Map</button>
              <button className={mode === "topo" ? "on" : ""} onClick={() => setMode("topo")}>Topology</button>
            </div>
            <label>
              Size
              <select value={sizeKey} onChange={(event) => setSizeKey(event.target.value as SizeKey)}>
                <option value="shipments">Volume</option>
                <option value="orders">Orders</option>
                <option value="inventory_units">Units</option>
                <option value="inventory_value">Value</option>
              </select>
            </label>
            <span className="legend"><span>Late</span><span className="swatch" /><span>On time</span></span>
          </div>
          {mode === "geo" ? (
            <GeoMap
              nodes={network.data.nodes}
              edges={network.data.edges}
              sizeKey={sizeKey}
              emphasisIds={emphasisIds}
              onSelect={(id) => {
                const node = network.data?.nodes.find((item) => item.id === id);
                if (node) select(node);
              }}
              onHover={(id, x, y) => {
                const node = id ? network.data?.nodes.find((item) => item.id === id) ?? null : null;
                setHover(node ? { node, x, y } : null);
              }}
            />
          ) : (
            <Topology
              nodes={network.data.nodes}
              edges={network.data.edges}
              sizeKey={sizeKey}
              emphasisIds={emphasisIds}
              onSelect={select}
              onHover={(node, x, y) => setHover(node ? { node, x, y } : null)}
            />
          )}
          {hover && (
            <aside className="hover-card" style={{ left: Math.min(hover.x + 14, window.innerWidth - 250), top: hover.y + 14 }}>
              <strong>{hover.node.label}</strong>
              <p>{hover.node.city}, {hover.node.country}</p>
              <p>{formatNumber(hover.node.orders)} orders · {formatPct(hover.node.otd)} on time</p>
              <p>{formatNumber(hover.node.delayed_inbound)} delayed inbound</p>
            </aside>
          )}
        </div>
      </div>
    </section>
  );
}
