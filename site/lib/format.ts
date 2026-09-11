export const pct = (x: number | null | undefined, digits = 0) =>
  x == null || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`;
export const usd = (x: number | null | undefined) =>
  x == null ? "—" : x < 0.01 ? `$${x.toFixed(5)}` : `$${x.toFixed(3)}`;
export const int = (x: number | null | undefined) => (x == null ? "—" : Math.round(x).toLocaleString("en-US"));
export const pval = (p: number) => (p < 0.001 ? "<0.001" : p.toFixed(3));
export const signed = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)} pts`;
export function wilson(k: number, n: number, z = 1.959964): [number, number] {
  if (!n) return [NaN, NaN];
  const p = k / n, d = 1 + (z * z) / n, c = p + (z * z) / (2 * n);
  const h = z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n));
  return [(c - h) / d, (c + h) / d];
}
