import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getJson } from "../services/api";
import { useTower } from "../store/useTower";
import type { Anomaly, Breakdown, Kpis, MetricKey, Trends } from "../types";
import { formatDate, formatDelta, formatNumber, formatUnit } from "../lib/format";
import { emphasisFor } from "../lib/locate";
import { ErrorBlock, EmptyBlock, LoadingBlock } from "../components/States";
import { HBars } from "../visualizations/Charts";
import { PlotPanel } from "../visualizations/PlotPanel";

const MEASURES: { key: keyof Kpis; label: string; metric?: MetricKey }[] = [
  { key: "otd", label: "On-time", metric: "otd" },
  { key: "lead_time", label: "Lead time", metric: "lead_time" },
  { key: "delayed_shipments", label: "Delayed" },
  { key: "logistics_cost", label: "Cost", metric: "logistics_cost" },
  { key: "inventory_value", label: "Inventory" },
  { key: "orders", label: "Orders" },
  { key: "alerts", label: "Alerts" },
];

export function DetectView() {
  const filters = useTower((state) => state.filters);
  const ready = useTower((state) => state.ready);
  const focus = useTower((state) => state.focusKpi);
  const setFocusKpi = useTower((state) => state.setFocusKpi);
  const setFilter = useTower((state) => state.setFilter);
  const setFocus = useTower((state) => state.setFocus);
  const setInvestigation = useTower((state) => state.setInvestigation);
  const applyContext = useTower((state) => state.applyContext);
  const navigate = useNavigate();
  const kpis = useQuery({ queryKey: ["kpis", filters], enabled: ready, queryFn: () => getJson<Kpis>("/kpis", filters) });
  const trends = useQuery({ queryKey: ["trends", filters], enabled: ready, queryFn: () => getJson<Trends>("/performance/trends", filters) });
  const breakdown = useQuery({
    queryKey: ["breakdown", focus, filters],
    enabled: ready,
    queryFn: () => getJson<Breakdown>("/performance/breakdown", filters, { kpi: focus }),
  });
  const anomalies = useQuery({ queryKey: ["anomalies", filters], enabled: ready, queryFn: () => getJson<Anomaly[]>("/anomalies", filters) });

  if (kpis.isLoading || trends.isLoading) return <LoadingBlock label="Reading performance" />;
  if (kpis.isError || !kpis.data || trends.isError || !trends.data) {
    return <ErrorBlock message="Performance analytics failed to load." onRetry={() => { kpis.refetch(); trends.refetch(); }} />;
  }

  const hero = kpis.data.otd;
  const heroBad = (hero.delta ?? 0) < 0;

  return (
    <section className="page stack">
      <section className="hero-signal">
        <div>
          <h2>On-time delivery</h2>
          <p className="hero-value">{formatUnit(hero.value, hero.unit)}</p>
          <p className={heroBad ? "delta bad" : "delta"}>{formatDelta(hero.delta, hero.delta_unit)} vs previous period</p>
          <p className="quiet">Plan lead time {trends.data.lead_time_expected?.toFixed(1) ?? "—"}d · actual {trends.data.lead_time_actual?.toFixed(1) ?? "—"}d</p>
        </div>
        <div className="measure-row">
          {MEASURES.map((item) => {
            const kpi = kpis.data?.[item.key];
            if (!kpi || typeof kpi !== "object" || !("unit" in kpi)) return null;
            const bad = (item.key === "otd" && (kpi.delta ?? 0) < 0) || (item.key !== "otd" && item.key !== "orders" && (kpi.delta ?? 0) > 0);
            return (
              <button key={item.key} className={focus === item.key ? "measure on" : "measure"} onClick={() => setFocusKpi(item.key)}>
                <span>{item.label}</span>
                <strong className={bad ? "bad" : ""}>{formatUnit(kpi.value, kpi.unit)}</strong>
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid-2">
        <section className="panel">
          <h2>{breakdown.data?.question || "Where is the change concentrated?"}</h2>
          {(breakdown.data?.groups ?? []).slice(0, 3).map((group) => (
            <div key={group.title} style={{ marginTop: 12 }}>
              <p className="kicker">{group.title}</p>
              <HBars
                rows={group.rows.map((row) => ({
                  id: row.order_id || row.id,
                  label: row.label,
                  value: row.share ?? row.value,
                  note: row.order_id ? `${formatNumber(row.value, 1)}h` : formatNumber(row.value, row.value != null && Math.abs(row.value - Math.round(row.value)) < 0.05 ? 0 : 1),
                }))}
                onPick={(id) => {
                  const row = group.rows.find((item) => item.order_id === id || item.id === id);
                  if (row?.order_id) navigate(`/trace/${row.order_id}`);
                  else if (row && (group.dimension === "warehouse" || group.dimension === "supplier" || group.dimension === "region" || group.dimension === "mode" || group.dimension === "product")) {
                    setFilter(group.dimension === "product" ? "product" : group.dimension, row.id);
                  }
                }}
              />
            </div>
          ))}
          <button className="text-btn" style={{ marginTop: 10 }} onClick={() => {
            const metric: MetricKey = focus === "lead_time" ? "lead_time" : focus === "logistics_cost" ? "logistics_cost" : focus === "inventory_value" ? "stock_coverage" : "otd";
            setInvestigation(metric, []);
            navigate("/investigate");
          }}>Investigate this measure →</button>
        </section>
        <section className="panel">
          <h2>When did on-time delivery move?</h2>
          <p className="question">Weekly rate. The dotted line is the previous window’s average.</p>
          <PlotPanel
            height={240}
            data={[
              { type: "scatter", mode: "lines", name: "On-time", x: trends.data.otd_series.map((row) => row.week), y: trends.data.otd_series.map((row) => (row.otd == null ? null : row.otd * 100)), line: { color: "#0e7c6b", width: 2 } },
              { type: "scatter", mode: "lines", name: "Baseline", x: trends.data.otd_series.map((row) => row.week), y: trends.data.otd_series.map((row) => (row.baseline_otd == null ? null : row.baseline_otd * 100)), line: { color: "#8a97a3", width: 1, dash: "dot" } },
            ]}
            layout={{ yaxis: { title: { text: "%" }, gridcolor: "#e3e8ed", range: [50, 100] }, showlegend: true }}
          />
        </section>
      </div>

      <section className="panel">
        <div className="view-head">
          <div>
            <h2>What else left its baseline?</h2>
          </div>
          <span className="mono">{anomalies.data?.length ?? ""}</span>
        </div>
        {anomalies.isLoading && <LoadingBlock label="Scanning signals" />}
        {anomalies.isError && <ErrorBlock message="Anomaly detection failed." onRetry={() => anomalies.refetch()} />}
        {anomalies.data && anomalies.data.length === 0 && <EmptyBlock label="No alerts for this slice. Widen the window or clear a filter." />}
        <div className="anomaly-grid">
          {(anomalies.data ?? []).map((alert) => (
            <article key={alert.id} className="anomaly-card">
              <header>
                <span className={`sev ${alert.severity}`}>{alert.severity}</span>
                <span className="mono">{formatDate(alert.timestamp)}</span>
              </header>
              <h3>{alert.entity_label}</h3>
              <p>{alert.metric}</p>
              <p className="anomaly-values">
                <strong>{formatUnit(alert.observed_value, alert.unit)}</strong>
                <span>expected {formatUnit(alert.expected_value, alert.unit)}</span>
              </p>
              <p className="mono">{alert.deviation_pct != null ? `${alert.deviation_pct > 0 ? "+" : ""}${(alert.deviation_pct * 100).toFixed(0)}%` : formatUnit(alert.deviation, alert.unit)}</p>
              <p className="quiet">{alert.method}</p>
              <div className="card-actions">
                <button className="text-btn" onClick={() => { setFocus({ kind: "anomaly", id: alert.id }, emphasisFor(alert)); navigate("/"); }}>Locate</button>
                <button className="text-btn primary" onClick={() => { applyContext(alert.context.filters, alert.context.metric, alert.context.steps); navigate("/investigate"); }}>Investigate →</button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
