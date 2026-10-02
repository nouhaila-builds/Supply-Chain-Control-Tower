/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', "Segoe UI", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        ink: "#080b10",
        panel: "#10161e",
        line: "rgba(186, 204, 220, 0.14)",
        mist: "#8b9bb0",
        teal: "#5ee0c5",
        amber: "#e6b15a",
        coral: "#f07167",
      },
    },
  },
  plugins: [],
};
