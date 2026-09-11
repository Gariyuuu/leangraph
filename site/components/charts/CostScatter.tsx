"use client";
import { CartesianGrid, LabelList, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, tooltipStyle } from "./common";

/** One hue; identity comes from the direct label beside each point, not from colour. */
export function CostScatter({ points }: { points: { label: string; cost: number; rate: number }[] }) {
  const data = points.filter((p) => p.cost > 0);
  return (
    <div className="h-80 w-full panel">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 12, right: 32, left: 4, bottom: 20 }}>
          <CartesianGrid stroke="var(--line)" />
          <XAxis type="number" dataKey="cost" name="Cost per theorem" scale="log" domain={["auto", "auto"]} {...axisProps}
            tickFormatter={(v) => `$${v < 0.01 ? v.toFixed(4) : v.toFixed(2)}`}
            label={{ value: "Mean model cost per theorem attempted (USD, log scale)", position: "insideBottom", offset: -12, fill: "var(--ink-3)", fontSize: 11 }} />
          <YAxis type="number" dataKey="rate" name="Verified" domain={[0, "auto"]} {...axisProps} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
          <Tooltip {...tooltipStyle} formatter={(v: number, n: string) => (n === "Verified" ? `${(v * 100).toFixed(1)}%` : `$${v.toFixed(5)}`)} />
          <Scatter data={data} fill="var(--series-1)" stroke="var(--paper-2)" strokeWidth={2} isAnimationActive={false}>
            <LabelList dataKey="label" position="right" style={{ fill: "var(--ink-2)", fontSize: 11 }} />
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
