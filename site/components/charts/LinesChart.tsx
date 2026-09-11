"use client";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, LabelList } from "recharts";
import { axisProps, DASH, SERIES, tooltipStyle } from "./common";

/** Up to four series; dash pattern first, hue second; value labelled at each line's end. */
export function LinesChart({ data, series, xKey, xLabel, yLabel, logX = false }: {
  data: Record<string, number | string>[]; series: { key: string; label: string }[];
  xKey: string; xLabel: string; yLabel: string; logX?: boolean;
}) {
  const last = data.length - 1;
  return (
    <div className="h-72 w-full panel">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 44, left: 4, bottom: 18 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} scale={logX ? "log" : "auto"} type={logX ? "number" : "category"}
            domain={logX ? ["dataMin", "dataMax"] : undefined} ticks={logX ? data.map((d) => d[xKey] as number) : undefined}
            label={{ value: xLabel, position: "insideBottom", offset: -10, fill: "var(--ink-3)", fontSize: 11 }} />
          <YAxis {...axisProps} domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`}
            label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "var(--ink-3)", fontSize: 11, dy: 50 }} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--ink-2)", paddingTop: 8 }} verticalAlign="top" />
          {series.map((s, i) => (
            <Line key={s.key} dataKey={s.key} name={s.label} stroke={SERIES[i]} strokeWidth={2} strokeDasharray={DASH[i]}
              dot={false} activeDot={{ r: 5, stroke: "var(--paper-2)", strokeWidth: 2 }} isAnimationActive={false}>
              <LabelList dataKey={s.key} content={({ x, y, value, index }) =>
                index === last && typeof value === "number" ? (
                  <text x={Number(x) + 6} y={Number(y)} dy={4} fontSize={11} fill="var(--ink-2)">{`${Math.round(value * 100)}%`}</text>
                ) : null} />
            </Line>
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
