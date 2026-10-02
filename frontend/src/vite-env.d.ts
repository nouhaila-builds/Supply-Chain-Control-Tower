/// <reference types="vite/client" />

declare module "plotly.js-basic-dist" {
  const Plotly: typeof import("plotly.js");
  export default Plotly;
}
