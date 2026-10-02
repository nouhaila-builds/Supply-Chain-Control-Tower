import { useMemo, useState } from "react";
import { scaleSqrt } from "d3-scale";
import type { NetworkEdge, NetworkNode } from "../types";
import { formatEur, formatNumber, formatPct, tone } from "../lib/format";

const COLUMNS = [
  ["supplier", "Suppliers"],
  ["factory", "Factories"],
  ["warehouse", "Warehouses"],
  ["hub", "Distribution"],
  ["customer", "Customers"],
] as const;

export function Topology({
  nodes,
  edges,
  sizeKey,
  emphasisIds = [],
  onSelect,
  onHover,
}: {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  sizeKey: "shipments" | "orders" | "inventory_units" | "inventory_value";
  emphasisIds?: string[];
  onSelect: (node: NetworkNode) => void;
  onHover: (node: NetworkNode | null, x: number, y: number) => void;
}) {
  const [local, setLocal] = useState<string | null>(null);
  const focus = local;
  const layout = useMemo(() => {
    const grouped = COLUMNS.map(([type]) => nodes.filter((node) => node.type === type).sort((a, b) => b.shipments - a.shipments));
    const values = nodes.map((node) => Number(node[sizeKey] ?? 0)).filter((value) => value > 0);
    const radius = scaleSqrt().domain([0, Math.max(...values, 1)]).range([4, 16]);
    const colW = 210;
    const positioned = new Map<string, { x: number; y: number; r: number }>();
    grouped.forEach((column, index) => {
      column.forEach((node, row) => {
        positioned.set(node.id, { x: 70 + index * colW, y: 36 + row * 22, r: radius(Number(node[sizeKey] ?? 0)) });
      });
    });
    const height = Math.max(640, ...grouped.map((column) => 70 + column.length * 22));
    return { positioned, height, width: 70 + COLUMNS.length * colW };
  }, [nodes, sizeKey]);

  const emphasis = new Set(emphasisIds.length ? emphasisIds : focus ? [focus] : []);
  const connected = new Set<string>(emphasis);
  if (emphasis.size) {
    edges.forEach((edge) => {
      if (emphasis.has(edge.source) || emphasis.has(edge.target)) {
        connected.add(edge.source);
        connected.add(edge.target);
      }
    });
  }

  return (
    <div className="topo-scroll">
      <svg width={layout.width} height={layout.height} role="img" aria-label="Supply chain topology">
        {COLUMNS.map(([type, label], index) => (
          <text key={type} x={70 + index * 210} y={16} fill="#8a97a3" fontSize="10" letterSpacing="1.2">
            {label.toUpperCase()}
          </text>
        ))}
        {edges.map((edge) => {
          const source = layout.positioned.get(edge.source);
          const target = layout.positioned.get(edge.target);
          if (!source || !target) return null;
          const mid = (source.x + target.x) / 2;
          const hot = !emphasis.size || emphasis.has(edge.source) || emphasis.has(edge.target);
          return (
            <path
              key={`${edge.source}-${edge.target}`}
              d={`M${source.x},${source.y} C${mid},${source.y} ${mid},${target.y} ${target.x},${target.y}`}
              fill="none"
              stroke={tone(edge.otd)}
              strokeWidth={Math.max(0.6, Math.min(3.2, edge.shipments / 400))}
              opacity={hot ? 0.7 : 0.08}
            />
          );
        })}
        {nodes.map((node) => {
          const point = layout.positioned.get(node.id);
          if (!point) return null;
          const hot = !emphasis.size || connected.has(node.id);
          const marked = emphasis.has(node.id);
          return (
            <g
              key={node.id}
              onClick={() => onSelect(node)}
              onMouseEnter={(event) => {
                setLocal(node.id);
                onHover(node, event.clientX, event.clientY);
              }}
              onMouseLeave={() => onHover(null, 0, 0)}
              style={{ cursor: "pointer" }}
            >
              <circle
                cx={point.x}
                cy={point.y}
                r={point.r}
                fill={tone(node.otd)}
                opacity={hot ? 0.95 : 0.22}
                stroke={marked ? "#2c6cb5" : "#ffffff"}
                strokeWidth={1.4}
              />
              {(hot || marked) && (
                <text x={point.x + point.r + 4} y={point.y + 3} fill={marked ? "#1c2833" : "#5c6b78"} fontSize="9">
                  {node.id}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function NodeFacts({ node }: { node: NetworkNode }) {
  const rows: [string, string][] = [
    ["Orders", formatNumber(node.orders)],
    ["Shipments", formatNumber(node.shipments)],
    ["On-time", formatPct(node.otd)],
    ["Delayed inbound", formatNumber(node.delayed_inbound)],
    ["Delayed outbound", formatNumber(node.delayed_outbound)],
  ];
  if (node.inventory_units != null) rows.push(["Stock", `${formatNumber(node.inventory_units, 0)} units`]);
  if (node.inventory_value != null) rows.push(["Inventory value", formatEur(node.inventory_value)]);
  if (node.stock_coverage != null) rows.push(["Thinnest cover", `${node.stock_coverage.toFixed(1)}d`]);
  return (
    <dl className="stat-list">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
