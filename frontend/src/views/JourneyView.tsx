import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { getJson } from "../services/api";
import { useTower } from "../store/useTower";
import type { Journey, Meta } from "../types";
import { formatEur, formatNumber } from "../lib/format";
import { ErrorBlock, LoadingBlock } from "../components/States";
import { JourneyTimeline } from "../visualizations/Timeline";

type SearchHit = {
  order_id: string;
  sku: string;
  product_name: string;
  customer_name: string;
  status: string;
  order_date: string | null;
  region: string;
  warehouse_id: string;
};

export function JourneyView() {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const ready = useTower((state) => state.ready);
  const [text, setText] = useState(orderId ?? "");
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => getJson<Meta>("/meta") });
  const search = useQuery({
    queryKey: ["search", text],
    enabled: ready && text.trim().length >= 2,
    queryFn: () => getJson<{ results: SearchHit[] }>("/orders/search", {}, { q: text.trim() }),
  });
  const journey = useQuery({
    queryKey: ["journey", orderId],
    enabled: ready && Boolean(orderId),
    queryFn: () => getJson<Journey>(`/orders/${orderId}/journey`),
  });

  return (
    <section className="page">
      <div className="view-head">
        <div>
          <h2>Where did this order lose time?</h2>
        </div>
      </div>
      <form
        className="toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          const exact = search.data?.results.find((hit) => hit.order_id.toLowerCase() === text.trim().toLowerCase());
          const target = exact?.order_id || search.data?.results[0]?.order_id;
          if (target) navigate(`/trace/${target}`);
        }}
      >
        <label className="search" style={{ minWidth: 280 }}>
          <input value={text} onChange={(event) => setText(event.target.value)} placeholder={meta.data?.example_order_id || "ORD-000123 or SKU-2841"} />
        </label>
        <button className="text-btn primary" type="submit">Open</button>
        {meta.data?.example_order_id && (
          <button className="text-btn" type="button" onClick={() => navigate(`/trace/${meta.data?.example_order_id}`)}>
            Open a delayed W-042 order
          </button>
        )}
      </form>
      {text.trim().length >= 2 && search.data && !orderId && (
        <div className="panel">
          {search.data.results.length === 0 ? <p className="quiet">No matching orders.</p> : (
            <table className="data">
              <thead><tr><th>Order</th><th>Customer</th><th>SKU</th><th>Status</th><th>Warehouse</th></tr></thead>
              <tbody>
                {search.data.results.map((hit) => (
                  <tr key={hit.order_id} className="clickable" onClick={() => navigate(`/trace/${hit.order_id}`)}>
                    <td className="mono">{hit.order_id}</td>
                    <td>{hit.customer_name}</td>
                    <td>{hit.sku}</td>
                    <td>{hit.status.replace("_", " ")}</td>
                    <td>{hit.warehouse_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {orderId && journey.isLoading && <LoadingBlock label="Reconstructing the journey" />}
      {orderId && journey.isError && <ErrorBlock message="That order was not found." />}
      {journey.data && <JourneyDetail journey={journey.data} />}
    </section>
  );
}

function JourneyDetail({ journey }: { journey: Journey }) {
  const order = journey.order;
  const setFilter = useTower((state) => state.setFilter);
  return (
    <div className="stack">
      <section className="panel">
        <div className="view-head">
          <div>
            <h2>{order.order_id}</h2>
            <p className="question">{order.product_name} · {order.quantity} units · {order.customer_name}, {order.city}</p>
          </div>
          <span className={`sev ${order.status === "delayed" ? "critical" : order.status === "on_time" ? "medium" : "high"}`}>{order.status.replace("_", " ")}</span>
        </div>
        <dl className="stat-list">
          <div><dt>Supplier</dt><dd>{order.supplier_id} · {order.supplier_name}</dd></div>
          <div><dt>Path</dt><dd>{order.factory_name} → {order.warehouse_id} → {order.hub_name}</dd></div>
          <div><dt>Planned lead time</dt><dd>{order.expected_lead_time_days?.toFixed(1) ?? "—"}d</dd></div>
          <div><dt>Actual lead time</dt><dd>{order.lead_time_days?.toFixed(1) ?? "—"}d</dd></div>
          <div><dt>Delay</dt><dd>{order.delay_hours != null ? `${formatNumber(order.delay_hours, 1)}h` : "—"}</dd></div>
          <div><dt>Logistics cost</dt><dd>{formatEur(order.logistics_cost)}</dd></div>
        </dl>
        <p style={{ fontSize: 14, lineHeight: 1.5 }}>{journey.narrative}</p>
        <button className="text-btn" onClick={() => setFilter("supplier", order.supplier_id)}>Filter tower to {order.supplier_id}</button>
        <button className="text-btn" onClick={() => setFilter("warehouse", order.warehouse_id)}>Filter tower to {order.warehouse_id}</button>
      </section>
      <section className="panel">
        <h2>Expected versus actual</h2>
        <JourneyTimeline journey={journey} />
      </section>
    </div>
  );
}
