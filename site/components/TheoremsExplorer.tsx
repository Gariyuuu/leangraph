"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { TheoremRow } from "@/lib/types";
import { FAMILY_LABELS, SPLIT_LABELS } from "@/lib/labels";

const sel = "rounded border border-line bg-paper-2 px-2 py-1.5 text-sm";

export function TheoremsExplorer({ rows }: { rows: TheoremRow[] }) {
  const [q, setQ] = useState(""); const [family, setFamily] = useState(""); const [split, setSplit] = useState("");
  const [difficulty, setDifficulty] = useState(""); const [status, setStatus] = useState("");
  const shown = useMemo(() => rows.filter((r) =>
    (!family || r.family === family) && (!split || r.split === split) && (!difficulty || r.difficulty === difficulty) &&
    (!status || (status === "solved" ? r.solved_by.length > 0 : status === "unsolved" ? r.n_configs > 0 && r.solved_by.length === 0 : r.n_configs === 0)) &&
    (!q || (r.statement + " " + r.id + " " + r.source).toLowerCase().includes(q.toLowerCase()))), [rows, q, family, split, difficulty, status]);
  const opts = (k: keyof TheoremRow) => Array.from(new Set(rows.map((r) => String(r[k])))).sort();
  return (
    <>
      <div className="flex flex-wrap gap-2" role="search">
        <input aria-label="Search statements" placeholder="Search statement, id or Mathlib name" value={q} onChange={(e) => setQ(e.target.value)} className={`${sel} min-w-[16rem] flex-1`} />
        <select aria-label="Family" value={family} onChange={(e) => setFamily(e.target.value)} className={sel}><option value="">All families</option>{opts("family").map((f) => <option key={f} value={f}>{FAMILY_LABELS[f] ?? f}</option>)}</select>
        <select aria-label="Source" value={split} onChange={(e) => setSplit(e.target.value)} className={sel}><option value="">All sources</option>{opts("split").map((f) => <option key={f} value={f}>{SPLIT_LABELS[f] ?? f}</option>)}</select>
        <select aria-label="Difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className={sel}><option value="">All difficulties</option>{["easy", "medium", "hard"].map((f) => <option key={f}>{f}</option>)}</select>
        <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)} className={sel}><option value="">Any status</option><option value="solved">Solved by ≥1 configuration</option><option value="unsolved">Attempted, never solved</option><option value="unrun">Not attempted</option></select>
      </div>
      <p className="mt-3 text-xs text-ink-3" aria-live="polite">{shown.length} of {rows.length} theorems</p>
      <ul className="mt-2 divide-y divide-[var(--line)] rounded-md border border-line bg-paper-2">
        {shown.map((r) => (
          <li key={r.id}>
            <Link href={`/theorem/${r.id}`} className="block px-4 py-3 transition-colors hover:bg-paper-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
                <span className="font-mono text-ink-2">{r.id}</span><span>{FAMILY_LABELS[r.family] ?? r.family}</span><span>{r.difficulty}</span>
                <span>{SPLIT_LABELS[r.split] ?? r.split}{r.role === "dev" ? " · dev" : ""}</span>
                <span className="ml-auto">{r.n_configs === 0 ? "not attempted" : r.solved_by.length ? <span className="text-ok">✓ solved by {r.solved_by.length}/{r.n_configs}</span> : <span className="text-bad">✕ unsolved ({r.n_configs} configs)</span>}</span>
              </div>
              <code className="lean mt-1.5 block truncate rounded bg-transparent font-mono text-[0.8rem]">{r.statement}</code>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
