"use client";
export const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
export const DASH = ["", "6 4", "1 4", "10 4 2 4"];
export const axisProps = {
  tick: { fill: "var(--ink-3)", fontSize: 11 },
  axisLine: { stroke: "var(--axis)" },
  tickLine: false as const,
};
export const tooltipStyle = {
  contentStyle: { background: "var(--paper-2)", border: "1px solid var(--line)", borderRadius: 6, fontSize: 12, color: "var(--ink)" },
  labelStyle: { color: "var(--ink-2)" },
};
