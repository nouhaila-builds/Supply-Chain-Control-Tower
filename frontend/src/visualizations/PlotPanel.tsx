import { useMemo } from "react";
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-basic-dist";
import type { Data, Layout } from "plotly.js";

const Plot = createPlotlyComponent(Plotly);

const baseLayout: Partial<Layout> = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "IBM Plex Sans, sans-serif", color: "#5c6b78", size: 11 },
  margin: { l: 48, r: 12, t: 10, b: 36 },
  xaxis: { gridcolor: "#e3e8ed", zeroline: false, color: "#5c6b78" },
  yaxis: { gridcolor: "#e3e8ed", zeroline: false, color: "#5c6b78" },
  showlegend: true,
  legend: { orientation: "h", y: 1.12, font: { size: 10 } },
};

export function PlotPanel({ data, layout, height = 260 }: { data: Data[]; layout?: Partial<Layout>; height?: number }) {
  const merged = useMemo(() => ({ ...baseLayout, height, ...layout }), [layout, height]);
  return (
    <Plot
      data={data}
      layout={merged}
      config={{ displayModeBar: false, responsive: true }}
      useResizeHandler
      style={{ width: "100%", height }}
    />
  );
}
