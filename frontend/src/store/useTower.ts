import { create } from "zustand";
import type { DrillStep, Filters, Meta, MetricKey } from "../types";
import { addDays, addMonths, formatISODate, parseISODate } from "../lib/format";

const FILTER_FIELDS = ["region", "country", "supplier", "warehouse", "factory", "product", "mode", "status", "customer"] as const;

const STEP_FIELD: Record<string, keyof Filters | undefined> = {
  region: "region",
  country: "country",
  supplier: "supplier",
  warehouse: "warehouse",
  factory: "factory",
  product: "product",
  mode: "mode",
  customer: "customer",
};

type Bounds = { start: string; end: string };

export type FocusTarget = { kind: "node" | "anomaly"; id: string };

type TowerState = {
  ready: boolean;
  bounds: Bounds;
  filters: Filters;
  filtersOpen: boolean;
  metric: MetricKey;
  steps: DrillStep[];
  focusKpi: string;
  focus: FocusTarget | null;
  emphasisIds: string[];
  aboutOpen: boolean;
  guideStep: number | null;
  init: (meta: Meta) => void;
  toggleFilters: () => void;
  setFilter: (key: keyof Filters, value: string | undefined) => void;
  clearEntities: () => void;
  setPreset: (days: number) => void;
  setRange: (start: string, end: string) => void;
  shiftWindow: (months: number) => void;
  setFocusKpi: (kpi: string) => void;
  setFocus: (focus: FocusTarget | null, emphasisIds?: string[]) => void;
  setInvestigation: (metric: MetricKey, steps: DrillStep[]) => void;
  drill: (step: DrillStep) => void;
  goToCrumb: (index: number) => void;
  applyContext: (filters: Partial<Filters>, metric: MetricKey, steps: DrillStep[]) => void;
  toggleAbout: () => void;
  startGuide: () => void;
  setGuideStep: (step: number | null) => void;
};

function clampRange(start: string, end: string, bounds: Bounds): Filters["start"] extends string ? { start: string; end: string } : never {
  let nextStart = start < bounds.start ? bounds.start : start;
  let nextEnd = end > bounds.end ? bounds.end : end;
  if (nextStart > nextEnd) nextStart = nextEnd;
  return { start: nextStart, end: nextEnd };
}

export const useTower = create<TowerState>((set, get) => ({
  ready: false,
  bounds: { start: "2025-10-01", end: "2026-09-30" },
  filters: { start: "2026-07-03", end: "2026-09-30" },
  filtersOpen: true,
  metric: "otd",
  steps: [],
  focusKpi: "otd",
  focus: null,
  emphasisIds: [],
  aboutOpen: false,
  guideStep: null,
  init: (meta) =>
    set({
      ready: true,
      bounds: { start: meta.date_start, end: meta.date_end },
      filters: { start: meta.default_start, end: meta.default_end },
    }),
  toggleFilters: () => set((state) => ({ filtersOpen: !state.filtersOpen })),
  setFilter: (key, value) =>
    set((state) => {
      const filters = { ...state.filters, [key]: value || undefined };
      const resetPath = key !== "start" && key !== "end";
      return { filters, steps: resetPath ? [] : state.steps };
    }),
  clearEntities: () =>
    set((state) => {
      const filters: Filters = { start: state.filters.start, end: state.filters.end };
      return { filters, steps: [] };
    }),
  setPreset: (days) => {
    const { bounds } = get();
    const end = bounds.end;
    const start = addDays(end, -(days - 1));
    set((state) => ({ filters: { ...state.filters, ...clampRange(start, end, bounds) }, steps: state.steps }));
  },
  setRange: (start, end) => {
    const [from, to] = start <= end ? [start, end] : [end, start];
    set((state) => ({ filters: { ...state.filters, ...clampRange(from, to, state.bounds) } }));
  },
  shiftWindow: (months) => {
    const { filters, bounds } = get();
    const start = addMonths(filters.start, months);
    const endDate = parseISODate(filters.end);
    endDate.setMonth(endDate.getMonth() + months);
    const end = formatISODate(endDate);
    set({ filters: { ...filters, ...clampRange(start, end, bounds) } });
  },
  setFocusKpi: (focusKpi) => set({ focusKpi }),
  setFocus: (focus, emphasisIds) => set({ focus, emphasisIds: emphasisIds ?? (focus?.kind === "node" ? [focus.id] : []) }),
  toggleAbout: () => set((state) => ({ aboutOpen: !state.aboutOpen })),
  startGuide: () => set((state) => ({ guideStep: 0, focus: null, emphasisIds: [], steps: [], filters: { start: state.filters.start, end: state.filters.end } })),
  setGuideStep: (guideStep) => set({ guideStep }),
  setInvestigation: (metric, steps) => set({ metric, steps }),
  drill: (step) =>
    set((state) => {
      const field = STEP_FIELD[step.dimension];
      const filters = field ? { ...state.filters, [field]: step.value } : state.filters;
      const steps = [...state.steps.filter((item) => item.dimension !== step.dimension), step];
      return { filters, steps };
    }),
  goToCrumb: (index) =>
    set((state) => {
      const kept = state.steps.slice(0, index);
      const removed = state.steps.slice(index);
      const filters = { ...state.filters };
      for (const step of removed) {
        const field = STEP_FIELD[step.dimension];
        if (field && filters[field] === step.value) delete filters[field];
      }
      return { steps: kept, filters };
    }),
  applyContext: (incoming, metric, steps) =>
    set((state) => {
      const filters: Filters = { start: state.filters.start, end: state.filters.end };
      for (const key of FILTER_FIELDS) {
        const value = incoming[key];
        if (value) filters[key] = value;
      }
      return { filters, metric, steps };
    }),
}));
