import { useQuery } from "@tanstack/react-query";
import { getJson } from "../services/api";
import { useTower } from "../store/useTower";
import type { Meta } from "../types";

export function AboutPanel() {
  const open = useTower((state) => state.aboutOpen);
  const toggle = useTower((state) => state.toggleAbout);
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => getJson<Meta>("/meta") });
  if (!open) return null;
  const counts = meta.data?.counts ?? {};
  return (
    <div className="about-scrim" onClick={toggle}>
      <aside className="about" onClick={(event) => event.stopPropagation()}>
        <div className="context-head">
          <p className="kicker">About this project</p>
          <button className="icon-btn" onClick={toggle} aria-label="Close about">×</button>
        </div>
        <h2>Supply Chain Control Tower</h2>
        <p>
          An interactive visual analytics prototype for investigating a synthetic European supply chain.
          Every figure on screen is aggregated from the generated orders, shipments, and inventory.
        </p>
        <dl className="stat-list">
          <div><dt>Orders</dt><dd>{counts.orders?.toLocaleString("en-GB") ?? "30,000"}</dd></div>
          <div><dt>Shipment legs</dt><dd>{counts.shipments?.toLocaleString("en-GB") ?? "120,000"}</dd></div>
          <div><dt>Suppliers</dt><dd>{counts.suppliers ?? 50}</dd></div>
          <div><dt>Warehouses</dt><dd>{counts.warehouses ?? 10}</dd></div>
        </dl>
        <p className="quiet">React, TypeScript, FastAPI, Python, D3, MapLibre, Plotly, scikit-learn.</p>
        <p className="status-line">Synthetic data. Statistical anomaly detection. Contribution is not causation.</p>
      </aside>
    </div>
  );
}
