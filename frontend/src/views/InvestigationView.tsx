import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getJson } from "../services/api";
import { useTower } from "../store/useTower";
import type { Investigation, MetricKey, NetworkData, NetworkNode } from "../types";
import { formatNumber, formatPct, formatUnit } from "../lib/format";
import { ErrorBlock, LoadingBlock } from "../components/States";
import { HBars } from "../visualizations/Charts";
import { GeoMap } from "../visualizations/GeoMap";

const METRICS: { id: MetricKey; label: string }[] = [
  { id: "otd", label: "On-time" },
  { id: "lead_time", label: "Lead time" },
  { id: "logistics_cost", label: "Cost" },
  { id: "stock_coverage", label: "Stock cover" },
];

export function InvestigationView() {
  const filters = useTower((state) => state.filters);
  const ready = useTower((state) => state.ready);
  const metric = useTower((state) => state.metric);
  const steps = useTower((state) => state.steps);
  const setInvestigation = useTower((state) => state.setInvestigation);
  const drill = useTower((state) => state.drill);
  const goToCrumb = useTower((state) => state.goToCrumb);
  const navigate = useNavigate();
  const drillParams = steps.map((step) => `${step.dimension}:${step.value}`);
  const query = useQuery({
    queryKey: ["investigation", metric, drillParams, filters],
    enabled: ready,
    queryFn: () => getJson<Investigation>("/investigation", filters, { metric, drill: drillParams }),
  });
  const scope = { start: filters.start, end: filters.end };
  const network = useQuery({
    queryKey: ["network", scope],
    enabled: ready,
    queryFn: () => getJson<NetworkData>("/network", scope),
  });

  if (query.isLoading) return <LoadingBlock label="Decomposing the gap" />;
  if (query.isError || !query.data) return <ErrorBlock message="The investigation could not be computed." onRetry={() => query.refetch()} />;
  const data = query.data;
  const emphasisIds = emphasisFrom(steps, network.data?.nodes ?? []);

  function openRow(row: Investigation["rows"][number]) {
    if (!row || row.id === "__other__") return;
    if (row.order_id) navigate(`/trace/${row.order_id}`);
    else if (row.drillable) drill({ dimension: data.dimension, value: row.id, label: row.label });
  }

  function pickNode(node: NetworkNode) {
    if (data.dimension === "region" && node.region) {
      const region = data.rows.find((row) => row.id === node.region);
      if (region?.drillable) drill({ dimension: "region", value: node.region, label: region.label });
      return;
    }
    if (node.type === data.dimension) {
      const row = data.rows.find((item) => item.id === node.id);
      if (row?.drillable) drill({ dimension: data.dimension, value: node.id, label: row.label });
    }
  }

  return (
    <section className="page invest-page">
      <div className="view-head">
        <div>
          <h2>{data.question}</h2>
        </div>
        <div className="seg">
          {METRICS.map((item) => (
            <button key={item.id} className={metric === item.id ? "on" : ""} onClick={() => setInvestigation(item.id, [])}>
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="path">
        <button onClick={() => goToCrumb(0)}>Global</button>
        {steps.map((step, index) => (
          <span key={`${step.dimension}-${step.value}`}>
            <span>→</span>{" "}
            <button onClick={() => goToCrumb(index + 1)}>{step.label}</button>
          </span>
        ))}
      </div>
      <div className="metric-hero">
        <span className="now">{formatUnit(data.current, data.unit === "eur" && (data.current ?? 0) > 1000 ? "eur" : data.unit === "ratio" ? "ratio" : data.unit)}</span>
        <span className="arrow">vs</span>
        <span className="then">{formatUnit(data.baseline, data.unit)}</span>
        {data.deviation != null && (
          <span className="mono" style={{ color: data.deviation < 0 && data.unit === "ratio" ? "#c4453c" : "#b86a12" }}>
            {data.unit === "ratio" ? `${(data.deviation * 100).toFixed(1)} pp` : formatUnit(data.deviation, data.unit)}
          </span>
        )}
      </div>
      <div className="invest">
        <div className="stage invest-map">
          {network.data ? (
            <GeoMap
              nodes={network.data.nodes}
              edges={network.data.edges}
              sizeKey="shipments"
              emphasisIds={emphasisIds}
              onSelect={(id) => {
                const node = network.data?.nodes.find((item) => item.id === id);
                if (node) pickNode(node);
              }}
              onHover={() => undefined}
            />
          ) : <LoadingBlock label="Placing the chain" />}
        </div>
        <div className="invest-side">
          <section className="panel">
            <h2>Who contributes most?</h2>
            <p className="question">{data.dimension} · {data.volume_label}. A share is not a cause.</p>
            <HBars
              rows={data.rows.map((row) => ({
                id: row.id,
                label: row.label,
                value: row.contribution,
                color: (row.deviation ?? 0) < 0 ? "#c4453c" : "#b86a12",
                note: formatPct(row.contribution, 0),
              }))}
              onPick={(id) => {
                const row = data.rows.find((item) => item.id === id);
                if (row) openRow(row);
              }}
            />
            <table className="data">
              <thead>
                <tr>
                  <th>Entity</th><th>Volume</th><th>Current</th><th>Baseline</th><th>Deviation</th><th>Share</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.id} className={row.drillable || row.order_id ? "clickable" : ""} onClick={() => openRow(row)}>
                    <td>{row.label}</td>
                    <td className="mono">{formatNumber(row.volume)}</td>
                    <td className="mono">{formatUnit(row.current, data.unit === "eur" ? "eur" : data.unit)}</td>
                    <td className="mono">{formatUnit(row.baseline, data.unit === "eur" ? "eur" : data.unit)}</td>
                    <td className="mono">{formatUnit(row.deviation, data.unit === "ratio" ? "ratio" : data.unit)}</td>
                    <td className="mono">{formatPct(row.contribution, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <aside className="panel evidence">
            <p className="kicker">Evidence</p>
            <ul>
              {data.evidence.map((line) => <li key={line}>{line}</li>)}
            </ul>
          </aside>
        </div>
      </div>
    </section>
  );
}

function emphasisFrom(steps: { dimension: string; value: string }[], nodes: NetworkNode[]): string[] {
  const facilities = steps.flatMap((step) => {
    if (step.dimension === "route") return step.value.split("→").map((part) => part.trim());
    if (["supplier", "warehouse", "factory", "hub", "customer"].includes(step.dimension)) return [step.value];
    return [];
  });
  if (facilities.length) return facilities;
  const region = [...steps].reverse().find((step) => step.dimension === "region");
  if (region) return nodes.filter((node) => node.region === region.value || node.id === region.value).map((node) => node.id);
  return [];
}
