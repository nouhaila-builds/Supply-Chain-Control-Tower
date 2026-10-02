import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useIsFetching, useQuery } from "@tanstack/react-query";
import { getJson } from "../services/api";
import { useTower } from "../store/useTower";
import type { FilterOptions, Meta } from "../types";
import { formatDate, formatMonth, listMonths, monthEnd, monthStart, parseISODate } from "../lib/format";
import { ErrorBlock } from "./States";
import { NetworkView } from "../views/NetworkView";
import { DetectView } from "../views/DetectView";
import { InvestigationView } from "../views/InvestigationView";
import { JourneyView } from "../views/JourneyView";
import { ContextPanel } from "./ContextPanel";
import { AboutPanel } from "./AboutPanel";
import { GuideRail } from "./GuideRail";

const FLOW = [
  { path: "/", label: "Overview" },
  { path: "/detect", label: "Detect" },
  { path: "/investigate", label: "Investigate" },
  { path: "/trace", label: "Trace" },
] as const;

const PRIMARY_FIELDS = [
  ["region", "Region"],
  ["warehouse", "Warehouse"],
  ["supplier", "Supplier"],
] as const;

const MORE_FIELDS = [
  ["country", "Country"],
  ["factory", "Factory"],
  ["product", "Product"],
  ["mode", "Mode"],
  ["status", "Status"],
] as const;

const CHIP_LABEL: Record<string, string> = {
  region: "Region",
  country: "Country",
  supplier: "Supplier",
  warehouse: "Warehouse",
  factory: "Factory",
  product: "Product",
  mode: "Mode",
  status: "Status",
  customer: "Customer",
};

export function Shell() {
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => getJson<Meta>("/meta") });
  const ready = useTower((state) => state.ready);
  const init = useTower((state) => state.init);
  useEffect(() => {
    if (meta.data && !ready) init(meta.data);
  }, [meta.data, ready, init]);

  if (meta.isError) return <ErrorBlock message="The control tower API is not responding." onRetry={() => meta.refetch()} />;
  if (!ready || !meta.data) return <div className="state">Bringing the network online…</div>;

  return (
    <div className="app">
      <Header meta={meta.data} />
      <Workspace />
      <AboutPanel />
    </div>
  );
}

function Header({ meta }: { meta: Meta }) {
  const filters = useTower((state) => state.filters);
  const shiftWindow = useTower((state) => state.shiftWindow);
  const toggleAbout = useTower((state) => state.toggleAbout);
  const { pathname } = useLocation();
  return (
    <header className="header">
      <div className="brand">
        <h1>Control Tower</h1>
      </div>
      <nav className="nav" aria-label="Analytical depth">
        {FLOW.map((item) => (
          <NavLink key={item.path} to={item.path} end={item.path === "/"} className={({ isActive }) => (isActive || (item.path === "/trace" && pathname.startsWith("/trace")) ? "active" : "")}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="status-cluster">
        <div className="period-shift">
          <button className="icon-btn" onClick={() => shiftWindow(-1)} aria-label="Previous month">‹</button>
          <span>{formatDate(filters.start)} – {formatDate(filters.end)}</span>
          <button className="icon-btn" onClick={() => shiftWindow(1)} aria-label="Next month">›</button>
        </div>
        <button className="text-btn" onClick={toggleAbout} title={meta.generated_at ? `Generated ${formatDate(meta.generated_at)}` : "About this dataset"}>About</button>
      </div>
    </header>
  );
}

function Workspace() {
  const open = useTower((state) => state.filtersOpen);
  const focus = useTower((state) => state.focus);
  const fetching = useIsFetching();
  return (
    <div className={`${open ? "body" : "body filters-closed"}${focus ? " with-context" : ""}`}>
      <FilterPanel />
      <main className="main">
        <div className={fetching ? "fetch-bar on" : "fetch-bar"} />
        <GuideRail />
        <Chips />
        <Routes>
          <Route path="/" element={<NetworkView />} />
          <Route path="/detect" element={<DetectView />} />
          <Route path="/investigate" element={<InvestigationView />} />
          <Route path="/trace" element={<JourneyView />} />
          <Route path="/trace/:orderId" element={<JourneyView />} />
          <Route path="/performance" element={<Navigate to="/detect" replace />} />
          <Route path="/anomalies" element={<Navigate to="/detect" replace />} />
          <Route path="/investigation" element={<Navigate to="/investigate" replace />} />
          <Route path="/journey" element={<Navigate to="/trace" replace />} />
          <Route path="/journey/:orderId" element={<JourneyRedirect />} />
        </Routes>
      </main>
      <ContextPanel />
    </div>
  );
}

function JourneyRedirect() {
  const { orderId } = useParams();
  return <Navigate to={`/trace/${orderId ?? ""}`} replace />;
}

function FilterPanel() {
  const open = useTower((state) => state.filtersOpen);
  const toggle = useTower((state) => state.toggleFilters);
  const filters = useTower((state) => state.filters);
  const bounds = useTower((state) => state.bounds);
  const setPreset = useTower((state) => state.setPreset);
  const setRange = useTower((state) => state.setRange);
  const clearEntities = useTower((state) => state.clearEntities);
  const options = useQuery({ queryKey: ["options"], queryFn: () => getJson<FilterOptions>("/filters/options") });
  const months = listMonths(bounds.start, bounds.end);
  const activeMonths = months.filter((month) => monthEnd(month) >= filters.start && monthStart(month) <= filters.end);
  const windowDays = Math.round((parseISODate(filters.end).getTime() - parseISODate(filters.start).getTime()) / 86400000) + 1;
  const presetActive = filters.end === bounds.end ? windowDays : 0;
  const moreInUse = MORE_FIELDS.some(([key]) => Boolean(filters[key]));
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <aside className={open ? "filters" : "filters is-closed"}>
      <div className="filter-head">
        <button className="icon-btn" onClick={toggle} aria-label={open ? "Collapse filters" : "Expand filters"}>
          {open ? "‹" : "›"}
        </button>
      </div>
      {open && (
        <div className="filter-body">
          <div className="filter-block">
            <label>When</label>
            <div className="presets">
              {[
                { days: 30, label: "30D" },
                { days: 90, label: "90D" },
                { days: 180, label: "6M" },
                { days: 365, label: "12M" },
              ].map((preset) => (
                <button key={preset.label} className={presetActive === preset.days ? "preset on" : "preset"} onClick={() => setPreset(preset.days)}>
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="months">
              {months.map((month) => (
                <button
                  key={month}
                  className={activeMonths.includes(month) ? "month on" : "month"}
                  onClick={() => setRange(monthStart(month), monthEnd(month))}
                >
                  {formatMonth(month)}
                </button>
              ))}
            </div>
          </div>
          <div className="filter-block">
            {PRIMARY_FIELDS.map(([key, label]) => (
              <FilterSelect key={key} field={key} label={label} options={options.data} />
            ))}
          </div>
          <button className="text-btn" onClick={() => setMoreOpen((value) => !value)}>
            {moreOpen || moreInUse ? "Fewer" : "More"}
          </button>
          {(moreOpen || moreInUse) && MORE_FIELDS.map(([key, label]) => (
            <FilterSelect key={key} field={key} label={label} options={options.data} />
          ))}
          {moreInUse && <button className="text-btn" onClick={clearEntities}>Clear</button>}
        </div>
      )}
    </aside>
  );
}

function FilterSelect({ field, label, options }: { field: string; label: string; options: FilterOptions | undefined }) {
  const filters = useTower((state) => state.filters);
  const setFilter = useTower((state) => state.setFilter);
  return (
    <label className="field">
      <span>{label}</span>
      <select value={filters[field as keyof typeof filters] ?? ""} onChange={(event) => setFilter(field as keyof typeof filters, event.target.value || undefined)}>
        <option value="">All</option>
        {choices(options, field).map((choice) => (
          <option key={choice.id} value={choice.id}>{choice.label}</option>
        ))}
      </select>
    </label>
  );
}

function choices(options: FilterOptions | undefined, key: string): { id: string; label: string }[] {
  if (!options) return [];
  if (key === "region") return options.regions.map((id) => ({ id, label: id }));
  if (key === "country") return options.countries.map((id) => ({ id, label: id }));
  if (key === "supplier") return options.suppliers;
  if (key === "warehouse") return options.warehouses;
  if (key === "factory") return options.factories;
  if (key === "product") return options.products;
  if (key === "mode") return options.modes.map((id) => ({ id, label: id }));
  if (key === "status") return options.statuses.map((id) => ({ id, label: id.replace("_", " ") }));
  return [];
}

function Chips() {
  const filters = useTower((state) => state.filters);
  const setFilter = useTower((state) => state.setFilter);
  const clearEntities = useTower((state) => state.clearEntities);
  const entries = Object.entries(filters).filter(([key, value]) => value && key !== "start" && key !== "end");
  if (entries.length === 0) return null;
  return (
    <div className="chips">
      {entries.map(([key, value]) => (
        <span className="chip" key={key}>
          {CHIP_LABEL[key] ?? key} {String(value).replaceAll("_", " ")}
          <button onClick={() => setFilter(key as keyof typeof filters, undefined)} aria-label={`Remove ${CHIP_LABEL[key] ?? key}`}>×</button>
        </span>
      ))}
      <button className="text-btn" onClick={clearEntities}>Clear</button>
    </div>
  );
}

