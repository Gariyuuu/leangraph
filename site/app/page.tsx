import Link from "next/link";
import { InterimBanner } from "@/components/InterimBanner";
import { getSummary, getTheorems, getTasksSummary } from "@/lib/data";
import { configLabel, HEADLINE_CONFIGS, SPLIT_LABELS } from "@/lib/labels";
import { pct, pval, signed, usd } from "@/lib/format";
import { Empty, PageHeader, Section, StatTile } from "@/components/ui";

const STAGES: [string, string][] = [
  ["Statement", "A Lean 4 theorem, rendered by the harness. The model never writes the header."],
  ["Retrieval", "Mathlib lemmas from an index that excludes every held-out module."],
  ["Model draft", "A tactic proof from the model, optionally after a planning call."],
  ["Lean check", "A long-lived REPL with Mathlib loaded answers in well under a second."],
  ["Error", "Lean's exact output, classified into a fixed taxonomy."],
  ["Repair", "The model sees only what Lean printed, then tries again."],
  ["Certificate", "A fresh Lean process re-checks the proof: axioms, premises, extra declarations."],
];

export default function Home() {
  const s = getSummary();
  const theorems = getTheorems();
  const ts = getTasksSummary() as { counts?: Record<string, number> } | null;
  const configs = s ? Object.entries(s.configs).sort((a, b) => b[1].rate - a[1].rate) : [];
  const best = configs.find(([c]) => HEADLINE_CONFIGS.includes(c));
  const template = s?.configs.template;
  const splits = theorems.reduce<Record<string, number>>((acc, t) => ({ ...acc, [t.split]: (acc[t.split] ?? 0) + 1 }), {});
  return (
    <>
      <PageHeader eyebrow="LeanGraph" title="When does verifier-guided reasoning help an LLM write proofs that Lean accepts?">
        <p>
          LeanGraph measures how often a language model produces a Lean 4 proof that the Lean kernel accepts, and whether
          retrieval of Mathlib lemmas, a planning step, and repair from compiler errors actually raise that rate. Lean is the
          grader: a plausible-looking proof that does not compile scores zero.
        </p>
      </PageHeader>
      <InterimBanner />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Theorems in the benchmark" value={theorems.length ? theorems.length.toLocaleString() : "—"}
          sub={Object.entries(splits).map(([k, v]) => `${v} ${SPLIT_LABELS[k] ?? k}`).join(" · ") || undefined} />
        <StatTile label="Best agent, verified" value={best ? pct(best[1].rate) : "—"} sub={best ? configLabel(best[0]) : "not run yet"} />
        <StatTile label="No-LLM automation, verified" value={template ? pct(template.rate) : "—"} sub="fixed tactic list" />
        <StatTile label="Model cost per verified proof" value={best ? usd(best[1].cost_per_verified) : "—"} sub={best ? configLabel(best[0]) : undefined} />
      </div>

      <Section title="One theorem, end to end" note="Every configuration is the same loop with parts switched on or off.">
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-7">
          {STAGES.map(([name, body], i) => (
            <li key={name} className="panel !p-3">
              <p className="font-mono text-xs text-ink-3">{String(i + 1).padStart(2, "0")}</p>
              <p className="mt-1 text-sm font-medium">{name}</p>
              <p className="mt-1 text-xs leading-snug text-ink-2">{body}</p>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Headline comparisons" note="Paired over the same theorems. p-values are exact McNemar tests, Holm-adjusted across every pre-registered contrast.">
        {s && s.contrasts.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Question</th><th className="r">Treatment</th><th className="r">Control</th><th className="r">Difference</th><th className="r">Holm p</th></tr></thead>
              <tbody>
                {s.contrasts.slice(0, 8).map((c) => (
                  <tr key={c.name}>
                    <td>{c.question}<div className="text-xs text-ink-3">{configLabel(c.treatment)} vs {configLabel(c.control)} · n = {c.n}</div></td>
                    <td className="r">{pct(c.rate_treatment)}</td><td className="r">{pct(c.rate_control)}</td>
                    <td className="r">{signed(c.diff)}<div className="text-xs text-ink-3">[{signed(c.diff_ci[0])}, {signed(c.diff_ci[1])}]</div></td>
                    <td className="r">{pval(c.p_holm)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>No frozen run yet. This table fills in from <code className="font-mono">results/analysis</code> once the benchmark has been run and exported.</Empty>
        )}
      </Section>

      <Section title="What counts as a proof">
        <ul className="grid gap-2 text-sm text-ink-2 sm:grid-cols-2">
          <li className="panel">A fresh <code className="font-mono">lean</code> process, pinned to Lean 4.33.1 and Mathlib v4.33.1, accepts the file with no errors.</li>
          <li className="panel">The proof uses only the standard axioms (propext, Classical.choice, Quot.sound): no <code className="font-mono">sorry</code>, no new axioms.</li>
          <li className="panel">For a Mathlib theorem, the proof uses nothing from the theorem&apos;s own module or any module built on it.</li>
          <li className="panel">The certifier reports under a random per-run nonce, so text written by the model cannot forge its verdict.</li>
        </ul>
        <p className="mt-3 text-sm"><Link href="/methods" className="text-accent underline">Full methods</Link> · <Link href="/theorems" className="text-accent underline">Browse every theorem and trace</Link>{ts?.counts ? "" : ""}</p>
      </Section>
    </>
  );
}
