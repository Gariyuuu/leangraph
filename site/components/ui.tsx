import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <header className="mb-8 max-w-3xl">
      {eyebrow && <p className="font-mono text-xs uppercase tracking-wider text-ink-3">{eyebrow}</p>}
      <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      {children && <div className="mt-3 text-[0.95rem] leading-relaxed text-ink-2">{children}</div>}
    </header>
  );
}

export function Section({ title, children, note }: { title: string; children: ReactNode; note?: ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {note && <p className="mt-1 max-w-3xl text-sm text-ink-2">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="panel">
      <p className="text-xs text-ink-3">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-ink-2">{sub}</p>}
    </div>
  );
}

export function Verdict({ ok, label }: { ok: boolean; label?: string }) {
  return ok ? (
    <span className="inline-flex items-center gap-1 rounded bg-ok-wash px-1.5 py-0.5 text-xs font-medium text-ok">
      <span aria-hidden>✓</span>{label ?? "Verified"}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded bg-bad-wash px-1.5 py-0.5 text-xs font-medium text-bad">
      <span aria-hidden>✕</span>{label ?? "Not verified"}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="panel border-dashed text-sm text-ink-2">{children}</div>;
}

export function LeanBlock({ code, label }: { code: string; label?: string }) {
  return (
    <figure>
      {label && <figcaption className="mb-1 text-xs text-ink-3">{label}</figcaption>}
      <pre className="lean">{code}</pre>
    </figure>
  );
}

/** Rate with its 95% interval as a tiny inline SVG: one axis, 0–100%. */
export function RateBar({ rate, ci, emphasis = false }: { rate: number; ci: [number, number]; emphasis?: boolean }) {
  const x = (v: number) => 4 + v * 152;
  const col = emphasis ? "var(--series-1)" : "var(--series-muted)";
  return (
    <svg width="160" height="14" viewBox="0 0 160 14" role="img" aria-label={`${Math.round(rate * 100)}%, 95% interval ${Math.round(ci[0] * 100)}–${Math.round(ci[1] * 100)}%`}>
      <line x1={x(0)} x2={x(1)} y1="7" y2="7" stroke="var(--line)" strokeWidth="1" />
      <line x1={x(ci[0])} x2={x(ci[1])} y1="7" y2="7" stroke={col} strokeWidth="2" strokeLinecap="round" />
      <circle cx={x(rate)} cy="7" r="4" fill={col} stroke="var(--paper-2)" strokeWidth="2" />
    </svg>
  );
}
