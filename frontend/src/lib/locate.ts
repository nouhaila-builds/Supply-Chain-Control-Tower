import type { Anomaly, Kpis, NetworkNode } from "../types";

export function emphasisFor(alert: Anomaly, nodes: NetworkNode[] = []): string[] {
  if (alert.entity_type === "region") {
    return nodes.filter((node) => node.region === alert.entity_id).map((node) => node.id);
  }
  if (alert.entity_type === "supplier" || alert.entity_type === "warehouse" || alert.entity_type === "factory") {
    return [alert.entity_id];
  }
  if (alert.entity_type === "route") {
    return alert.entity_id.split("→").map((part) => part.trim()).filter(Boolean);
  }
  if (alert.context.filters.warehouse) return [alert.context.filters.warehouse];
  if (alert.context.filters.supplier) return [alert.context.filters.supplier];
  return [];
}

export function healthStatement(kpis: Kpis): string {
  const days = kpis.baseline_window?.days;
  const baseline = days ? `the previous ${days}-day window` : "the previous window";
  const delta = kpis.otd.delta;
  if (delta == null) return "This window has no baseline of equal length yet.";
  const points = Math.abs(delta * 100).toFixed(1);
  if (delta <= -0.05) return `Delivery performance fell ${points} percentage points against ${baseline}.`;
  if (delta >= 0.02) return `Delivery performance rose ${points} percentage points against ${baseline}.`;
  return `Delivery performance is close to ${baseline}.`;
}

export function anchorAnomaly(alerts: Anomaly[]): Anomaly | undefined {
  return alerts.find((alert) => alert.type === "warehouse_delay") ?? alerts[0];
}
