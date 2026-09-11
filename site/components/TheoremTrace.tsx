"use client";
import { useState } from "react";
import type { RunTrace } from "@/lib/types";
import { configLabel, errorLabel } from "@/lib/labels";
import { usd } from "@/lib/format";
import { LeanBlock, Verdict } from "./ui";

export function TheoremTrace({ runs, header }: { runs: Record<string, RunTrace>; header: string }) {
  const order = Object.keys(runs).sort((a, b) => Number(runs[b].verified) - Number(runs[a].verified) || a.localeCompare(b));
  const [cfg, setCfg] = useState(order[0]);
  if (!order.length) return <p className="text-sm text-ink-2">No configuration has attempted this theorem yet.</p>;
  const r = runs[cfg];
  return (
    <div>
      <div role="tablist" aria-label="Configuration" className="flex flex-wrap gap-1.5">
        {order.map((c) => (
          <button key={c} role="tab" aria-selected={c === cfg} onClick={() => setCfg(c)}
            className={`rounded border px-2.5 py-1 text-xs transition-colors ${c === cfg ? "border-accent bg-accent-wash text-ink" : "border-line text-ink-2 hover:bg-paper-3"}`}>
            <span aria-hidden className={runs[c].verified ? "text-ok" : "text-bad"}>{runs[c].verified ? "✓ " : "✕ "}</span>{configLabel(c)}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="mt-4 space-y-5">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Verdict ok={r.verified} />
          <span className="text-ink-2">{r.usage?.llm_calls ?? 0} model calls · {r.usage?.lean_checks ?? 0} Lean checks · {usd(r.usage?.cost_usd)}</span>
          {r.error && <span className="text-bad">harness error: {r.error}</span>}
        </div>
        {r.retrieved.length > 0 && (
          <div><h3 className="text-sm font-semibold">Retrieved lemmas</h3>
            <ol className="mt-1 grid gap-x-4 font-mono text-xs text-ink-2 sm:grid-cols-2">{r.retrieved.map((n, i) => <li key={n}>{i + 1}. {n}</li>)}</ol></div>
        )}
        {r.plan && (
          <div className="space-y-2"><h3 className="text-sm font-semibold">Plan</h3>
            <p className="whitespace-pre-wrap text-sm text-ink-2">{r.plan.informal}</p>
            {r.plan.skeleton && <LeanBlock code={r.plan.skeleton} label={`Skeleton — ${r.plan.skeleton_ok ? "Lean accepts it with only sorry steps left" : "Lean reported problems"}`} />}
          </div>
        )}
        <div><h3 className="text-sm font-semibold">Attempts</h3>
          <ol className="mt-2 space-y-4">
            {r.attempts.map((a, i) => (
              <li key={i} className="panel space-y-2">
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3">
                  <span className="font-mono">{a.sample != null ? `sample ${a.sample} · round ${a.round}` : `attempt ${i + 1}`}</span>
                  {a.verified ? <Verdict ok /> : <Verdict ok={false} label={errorLabel(a.error_class ?? "other")} />}
                  {a.latency_s != null && <span>{a.latency_s.toFixed(1)} s model time</span>}
                </div>
                <LeanBlock code={a.proof || "(no proof in the reply)"} label="Proof" />
                {!a.verified && a.compiler_output && <LeanBlock code={a.compiler_output} label="What Lean printed (this is all the model sees on repair)" />}
              </li>
            ))}
          </ol>
        </div>
        {r.verified && r.final_proof && (
          <div><h3 className="text-sm font-semibold">Verified proof</h3>
            <LeanBlock code={`${header}\n${r.final_proof.split("\n").map((l) => "  " + l).join("\n")}`} />
            {r.certificate?.axioms && <p className="mt-1 text-xs text-ink-3">Axioms used: {r.certificate.axioms.length ? r.certificate.axioms.join(", ") : "none"}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
