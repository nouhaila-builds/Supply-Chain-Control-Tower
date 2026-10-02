import { scaleLinear } from "d3-scale";
import { formatNumber, formatPct, tone } from "../lib/format";

type Bar = { label: string; value: number | null; note?: string; color?: string; id?: string };

export function HBars({
  rows,
  onPick,
}: {
  rows: Bar[];
  onPick?: (id: string) => void;
}) {
  const max = Math.max(...rows.map((row) => Math.abs(row.value ?? 0)), 0.0001);
  const width = scaleLinear().domain([0, max]).range([0, 100]);
  if (!rows.length) return <p className="quiet">Nothing in this slice.</p>;
  return (
    <div className="hbars">
      {rows.map((row) => {
        const magnitude = Math.abs(row.value ?? 0);
        return (
          <button
            key={row.id || row.label}
            onClick={() => row.id && onPick?.(row.id)}
            className="hbar"
            style={{ display: "grid", gridTemplateColumns: "minmax(120px, 34%) 1fr auto", gap: 12, width: "100%", background: "transparent", border: 0, textAlign: "left", padding: "5px 0", cursor: onPick ? "pointer" : "default" }}
          >
            <span style={{ fontSize: 12, color: "#1c2833", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.label}</span>
            <span style={{ background: "#e3e8ed", height: 6, alignSelf: "center" }}>
              <span style={{ display: "block", height: "100%", width: `${width(magnitude)}%`, background: row.color || "#0e7c6b" }} />
            </span>
            <span className="mono" style={{ fontSize: 11, color: "#5c6b78" }}>{row.note ?? formatNumber(row.value, 0)}</span>
          </button>
        );
      })}
    </div>
  );
}

export function Histogram({
  rows,
}: {
  rows: { bin: string; actual: number; expected: number }[];
}) {
  const max = Math.max(...rows.flatMap((row) => [row.actual, row.expected]), 1);
  const height = 160;
  const y = scaleLinear().domain([0, max]).range([height - 18, 4]);
  const group = 64;
  return (
    <svg viewBox={`0 0 ${rows.length * group} ${height}`} width="100%" height={height} role="img">
      {rows.map((row, index) => {
        const x = index * group + 10;
        return (
          <g key={row.bin}>
            <rect x={x} y={y(row.expected)} width={16} height={height - 18 - y(row.expected)} fill="#c5ced6" />
            <rect x={x + 18} y={y(row.actual)} width={16} height={height - 18 - y(row.actual)} fill="#0e7c6b" />
            <text x={x + 16} y={height - 4} textAnchor="middle" fill="#5c6b78" fontSize="9">{row.bin}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function SupplierBars({
  rows,
  onPick,
}: {
  rows: { id: string; label: string; otd: number | null; baseline_otd: number | null; orders: number }[];
  onPick: (id: string) => void;
}) {
  return (
    <HBars
      onPick={onPick}
      rows={rows.map((row) => ({
        id: row.id,
        label: row.label,
        value: row.otd,
        color: tone(row.otd),
        note: `${formatPct(row.otd)} · base ${formatPct(row.baseline_otd)}`,
      }))}
    />
  );
}
