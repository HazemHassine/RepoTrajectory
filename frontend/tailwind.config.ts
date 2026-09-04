import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#050505",
        surface: "#090909",
        "surface-dim": "#111111",
        "surface-container": "#161616",
        "surface-hover": "#1a1a1a",
        "border-primary": "#262626",
        "border-muted": "#181818",
        "primary-fixed": "#ccf200",
        "text-primary": "#ffffff",
        "text-muted": "#9a9a9a",
        "text-dim": "#646464",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "IBM Plex Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
} satisfies Config;
