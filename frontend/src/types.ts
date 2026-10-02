export type Filters = {
  start: string;
  end: string;
  region?: string;
  country?: string;
  supplier?: string;
  warehouse?: string;
  factory?: string;
  product?: string;
  mode?: string;
  status?: string;
  customer?: string;
};

export type DrillStep = {
  dimension: string;
  value: string;
  label: string;
};

export type MetricKey = "otd" | "lead_time" | "logistics_cost" | "stock_coverage";

export type Meta = {
  title: string;
  subtitle: string;
  seed: number;
  generated_at: string | null;
  date_start: string;
  date_end: string;
  default_start: string;
  default_end: string;
  counts: Record<string, number>;
  example_order_id: string | null;
  dataset: string;
};

export type KpiValue = {
  value: number | null;
  baseline: number | null;
  delta: number | null;
  delta_unit: string | null;
  unit: string;
};

export type Kpis = {
  window: { start: string; end: string; days: number } | null;
  baseline_window: { start: string; end: string; days: number } | null;
  orders: KpiValue;
  otd: KpiValue;
  inventory_value: KpiValue;
  lead_time: KpiValue;
  delayed_shipments: KpiValue;
  logistics_cost: KpiValue;
  alerts: KpiValue;
  delivered_orders: number;
  late_orders: number;
};

export type NetworkNode = {
  id: string;
  type: string;
  name: string;
  label: string;
  city: string;
  country: string;
  region: string | null;
  lat: number;
  lon: number;
  orders: number;
  quantity: number;
  shipments: number;
  otd: number | null;
  inventory_units: number | null;
  inventory_value: number | null;
  stock_coverage: number | null;
  delayed_inbound: number;
  delayed_outbound: number;
  betweenness: number | null;
};

export type NetworkEdge = {
  source: string;
  target: string;
  shipments: number;
  quantity: number;
  cost: number | null;
  otd: number | null;
  avg_delay_hours: number | null;
  mode: string | null;
};

export type NetworkData = {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  summary: { nodes: number; edges: number; orders: number; shipments: number };
};

export type Anomaly = {
  id: string;
  severity: "critical" | "high" | "medium" | string;
  type: string;
  entity_type: string;
  entity_id: string;
  entity_label: string;
  metric: string;
  expected_value: number | null;
  observed_value: number | null;
  deviation: number | null;
  deviation_pct: number | null;
  unit: string;
  method: string;
  timestamp: string;
  location: string;
  summary: string;
  context: {
    metric: MetricKey;
    steps: DrillStep[];
    filters: Partial<Filters>;
    extra: Record<string, number | string | null>;
  };
};

export type ContributionRow = {
  id: string;
  label: string;
  volume: number | null;
  current: number | null;
  baseline: number | null;
  deviation: number | null;
  excess: number | null;
  contribution: number | null;
  drillable: boolean;
  order_id: string | null;
};

export type Investigation = {
  metric: MetricKey;
  metric_label: string;
  unit: string;
  question: string;
  dimension: string;
  volume_label: string;
  current: number | null;
  baseline: number | null;
  deviation: number | null;
  deviation_pct: number | null;
  volume: number | null;
  breadcrumb: DrillStep[];
  rows: ContributionRow[];
  evidence: string[];
  steps: DrillStep[];
};

export type JourneyStage = {
  key: string;
  label: string;
  location: string;
  entity_id: string | null;
  expected_start: string | null;
  expected_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  delay_hours: number | null;
  own_delay_hours: number | null;
  status: string;
  origin: boolean;
  propagated: boolean;
  added: boolean;
  lat: number;
  lon: number;
};

export type Journey = {
  order: {
    order_id: string;
    sku: string;
    product_name: string;
    quantity: number;
    customer_name: string;
    region: string;
    country: string;
    city: string;
    status: string;
    supplier_id: string;
    supplier_name: string;
    factory_name: string;
    warehouse_id: string;
    warehouse_name: string;
    hub_name: string;
    order_date: string | null;
    expected_delivery_date: string | null;
    actual_delivery_date: string | null;
    lead_time_days: number | null;
    expected_lead_time_days: number | null;
    delay_hours: number | null;
    logistics_cost: number | null;
  };
  stages: JourneyStage[];
  origin_stage: string | null;
  total_delay_hours: number | null;
  narrative: string;
};

export type Trends = {
  otd_series: { week: string; otd: number | null; orders: number; late: number; baseline_otd: number | null }[];
  volume_series: { week: string; orders: number; shipments: number }[];
  lead_time_hist: { bin: string; actual: number; expected: number }[];
  inventory_series: { week: string; value: number | null }[];
  cost_by_mode: { mode: string; cost: number | null; shipments: number }[];
  supplier_performance: { id: string; label: string; orders: number; otd: number | null; baseline_otd: number | null }[];
  lead_time_actual: number | null;
  lead_time_expected: number | null;
};

export type Breakdown = {
  kpi: string;
  question: string;
  groups: {
    dimension: string;
    title: string;
    rows: { id: string; label: string; value: number | null; volume: number | null; share: number | null; order_id?: string }[];
  }[];
};

export type FilterOptions = {
  regions: string[];
  countries: string[];
  suppliers: { id: string; label: string }[];
  warehouses: { id: string; label: string }[];
  factories: { id: string; label: string }[];
  products: { id: string; label: string }[];
  modes: string[];
  statuses: string[];
};

export type InventoryView = {
  total_value: number | null;
  total_units: number | null;
  by_warehouse: { id: string; label: string; value: number | null; units: number | null }[];
  by_category: { id: string; label: string; value: number | null }[];
  by_region: { id: string; label: string; value: number | null }[];
  series: { week: string; value: number | null }[];
};

export type CostPoint = {
  id: string;
  label: string;
  cost: number | null;
  cost_per_shipment: number | null;
  otd: number | null;
  volume: number;
};

export type CostView = {
  suppliers: CostPoint[];
  routes: CostPoint[];
  supplier_median: { cost: number | null; otd: number | null };
  route_median: { cost: number | null; otd: number | null };
  question: string;
};
