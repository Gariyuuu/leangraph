"use client";
import { Bar, BarChart, CartesianGrid, ErrorBar, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, tooltipStyle } from "./common";

/** One series, one hue. Optional 95% interval as error bars. Values labelled at the bar end. */
export function HBarChart({ data, valueFormat = "pct", xLabel }: {
  data: { label: string; value: number; lo?: number; hi?: number }[]; valueFormat?: "pct" | "int"; xLabel: string;
}) {
  const rows = data.map((d) => ({ ...d, err: d.lo != null && d.hi != null ? [d.value - d.lo, d.hi - d.value] : undefined }));
  const fmt = (v: number) => (valueFormat === "pct" ? `${Math.round(v * 100)}%` : v.toLocaleString("en-US"));
  return (
    <div className="w-full panel" style={{ height: 48 + rows.length * 30 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 48, left: 8, bottom: 16 }}>
          <CartesianGrid stroke="var(--line)" horizontal={false} />
          <XAxis type="number" {...axisProps} domain={valueFormat === "pct" ? [0, 1] : [0, "auto"]} tickFormatter={fmt}
            label={{ value: xLabel, position: "insideBottom", offset: -8, fill: "var(--ink-3)", fontSize: 11 }} />
          <YAxis type="category" dataKey="label" width={210} {...axisProps} tick={{ fill: "var(--ink-2)", fontSize: 12 }} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => fmt(v)} cursor={{ fill: "var(--paper-3)" }} />
          <Bar dataKey="value" fill="var(--series-1)" barSize={16} radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {rows.some((r) => r.err) && <ErrorBar dataKey="err" width={0} stroke="var(--ink-2)" strokeWidth={1} direction="x" />}
            <LabelList dataKey="value" position="right" formatter={fmt} style={{ fill: "var(--ink-2)", fontSize: 11 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
