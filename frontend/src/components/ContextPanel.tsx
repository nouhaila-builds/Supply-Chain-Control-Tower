import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getJson } from "../services/api";
import { useTower } from "../store/useTower";
import type { Anomaly, MetricKey, NetworkData } from "../types";
import { formatDate, formatEur, formatNumber, formatPct, formatUnit } from "../lib/format";
import { NodeFacts } from "../visualizations/Topology";

export function ContextPanel() {
  const focus = useTower((state) => state.focus);
  const filters = useTower((state) => state.filters);
  const ready = useTower((state) => state.ready);
  const setFocus = useTower((state) => state.setFocus);
  const applyContext = useTower((state) => state.applyContext);
  const navigate = useNavigate();
  const network = useQuery({
    queryKey: ["network", filters],
    enabled: ready && focus?.kind === "node",
    queryFn: () => getJson<NetworkData>("/network", filters),
  });
  const anomalies = useQuery({
    queryKey: ["anomalies", filters],
    enabled: ready && Boolean(focus),
    queryFn: () => getJson<Anomaly[]>("/anomalies", filters),
  });

  if (!focus) return null;
  const alert = focus.kind === "anomaly" ? anomalies.data?.find((item) => item.id === focus.id) : undefined;
  const node = focus.kind === "node" ? network.data?.nodes.find((item) => item.id === focus.id) : undefined;
  const related = (anomalies.data ?? []).filter((item) => item.id !== alert?.id && sharesContext(item, alert, node?.id, node?.region));

  function investigate() {
    if (alert) {
      applyContext(alert.context.filters, alert.context.metric, alert.context.steps);
    } else if (node) {
      const metric: MetricKey = "otd";
      if (node.type === "supplier") applyContext({ supplier: node.id }, metric, []);
      else if (node.type === "warehouse") applyContext({ warehouse: node.id }, metric, []);
      else if (node.type === "factory") applyContext({ factory: node.id }, metric, []);
      else if (node.type === "customer") applyContext({ customer: node.id }, metric, []);
      else if (node.region) applyContext({ region: node.region }, metric, []);
      else return;
    } else return;
    navigate("/investigate");
  }

  const title = alert?.entity_label ?? node?.label ?? focus.id;
  const place = alert?.location || (node ? `${node.city}, ${node.country}` : "");
  const attention = Boolean(alert) || (node?.otd != null && node.otd < 0.9);

  return (
    <aside className="context">
      <div className="context-head">
        <p className="kicker">{alert ? alert.entity_type : node?.type ?? "Selection"}</p>
        <button className="icon-btn" onClick={() => setFocus(null, [])} aria-label="Close context">×</button>
      </div>
      <h2>{title}</h2>
      {place && <p className="question">{place}</p>}
      <p className={attention ? "status-line bad" : "status-line"}>{attention ? "Needs attention" : "Within recent range"}</p>
      {alert && (
        <dl className="stat-list">
          <div><dt>{alert.metric}</dt><dd>{formatUnit(alert.observed_value, alert.unit)}</dd></div>
          <div><dt>Expected</dt><dd>{formatUnit(alert.expected_value, alert.unit)}</dd></div>
          <div><dt>Deviation</dt><dd>{alert.deviation_pct != null ? `${alert.deviation_pct > 0 ? "+" : ""}${(alert.deviation_pct * 100).toFixed(0)}%` : formatUnit(alert.deviation, alert.unit)}</dd></div>
          <div><dt>Method</dt><dd>{alert.method}</dd></div>
          <div><dt>Observed</dt><dd>{formatDate(alert.timestamp)}</dd></div>
        </dl>
      )}
      {node && (
        <>
          <NodeFacts node={node} />
          {node.inventory_value != null && <p className="quiet">{formatEur(node.inventory_value)} on hand · {formatNumber(node.orders)} orders · {formatPct(node.otd)} on time</p>}
        </>
      )}
      {alert && <p className="context-copy">{alert.summary}</p>}
      <p className="kicker" style={{ marginTop: 16 }}>Other signals in this slice</p>
      {related.length === 0 ? <p className="quiet">No other alert shares this entity or location.</p> : (
        <ul className="signal-list">
          {related.slice(0, 4).map((item) => (
            <li key={item.id}>
              <button onClick={() => setFocus({ kind: "anomaly", id: item.id })}>
                <strong>{item.entity_label}</strong>
                <span>{item.metric}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <button className="text-btn primary context-go" onClick={investigate}>Investigate {shortName(title)} →</button>
      <p className="quiet">Opens the contribution drill with this selection. A share of the gap is not a cause.</p>
    </aside>
  );
}

function shortName(label: string): string {
  return label.split("·")[0]?.trim() || label;
}

function sharesContext(item: Anomaly, alert: Anomaly | undefined, nodeId?: string, region?: string | null): boolean {
  const blob = `${item.entity_id} ${item.location} ${item.entity_label} ${JSON.stringify(item.context.filters)}`;
  if (alert && (blob.includes(alert.entity_id) || (alert.location && blob.includes(alert.location)))) return true;
  if (nodeId && blob.includes(nodeId)) return true;
  if (region && blob.includes(region)) return true;
  return false;
}
