import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SF Mono", "monospace"],
      },
      colors: {
        paper: "var(--paper)",
        "paper-2": "var(--paper-2)",
        "paper-3": "var(--paper-3)",
        ink: "var(--ink)",
        "ink-2": "var(--ink-2)",
        "ink-3": "var(--ink-3)",
        line: "var(--line)",
        accent: "var(--accent)",
        "accent-wash": "var(--accent-wash)",
        ok: "var(--ok)",
        "ok-wash": "var(--ok-wash)",
        bad: "var(--bad)",
        "bad-wash": "var(--bad-wash)",
        warn: "var(--warn)",
      },
      maxWidth: { content: "72rem" },
      fontSize: { xs: ["0.75rem", "1.1rem"] },
    },
  },
  plugins: [typography],
};
export default config;
