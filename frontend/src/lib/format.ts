export function parseISODate(iso: string): Date {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

export function formatISODate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function addDays(iso: string, days: number): string {
  const date = parseISODate(iso);
  date.setDate(date.getDate() + days);
  return formatISODate(date);
}

export function addMonths(iso: string, months: number): string {
  const date = parseISODate(iso);
  date.setMonth(date.getMonth() + months);
  return formatISODate(date);
}

export function monthStart(month: string): string {
  return `${month}-01`;
}

export function monthEnd(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  const date = new Date(year, mon, 0);
  return formatISODate(date);
}

export function listMonths(start: string, end: string): string[] {
  const months: string[] = [];
  const cursor = parseISODate(monthStart(start.slice(0, 7)));
  const last = parseISODate(monthStart(end.slice(0, 7)));
  while (cursor <= last) {
    months.push(`${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`);
    cursor.setMonth(cursor.getMonth() + 1);
  }
  return months;
}

export function formatMonth(month: string): string {
  return parseISODate(`${month}-01`).toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return parseISODate(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatStamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.replace("T", " ").slice(0, 16);
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatEur(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value < 0 ? "−" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${sign}€${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${sign}€${(abs / 1_000).toFixed(1)}k`;
  return `${sign}€${abs.toFixed(0)}`;
}

export function formatUnit(value: number | null | undefined, unit: string): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (unit === "ratio") return formatPct(value);
  if (unit === "eur") return formatEur(value);
  if (unit === "eur_per_km") return `€${value.toFixed(2)}/km`;
  if (unit === "days" || unit === "days_cover") return `${value.toFixed(1)}d`;
  if (unit === "count") return formatNumber(value);
  return formatNumber(value, 1);
}

export function formatDelta(delta: number | null | undefined, deltaUnit: string | null): string {
  if (delta == null || Number.isNaN(delta)) return "no baseline";
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
  const abs = Math.abs(delta);
  if (deltaUnit === "pp") return `${sign}${(abs * 100).toFixed(1)} pp`;
  if (deltaUnit === "pct") return `${sign}${(abs * 100).toFixed(1)}%`;
  if (deltaUnit === "days") return `${sign}${abs.toFixed(1)}d`;
  if (deltaUnit === "count") return `${sign}${formatNumber(abs)}`;
  return `${sign}${abs.toFixed(1)}`;
}

export function tone(otd: number | null | undefined): string {
  if (otd == null) return "#8a97a3";
  if (otd < 0.8) return "#c4453c";
  if (otd < 0.9) return "#b86a12";
  if (otd < 0.96) return "#7a8a4a";
  return "#0e7c6b";
}

export function severityColor(severity: string): string {
  if (severity === "critical") return "#c4453c";
  if (severity === "high") return "#b86a12";
  return "#2c6cb5";
}
