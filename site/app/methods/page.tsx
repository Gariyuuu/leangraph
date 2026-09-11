import type { Metadata } from "next";
import { getEnvironment, getTasksSummary } from "@/lib/data";
import { CONFIG_DESCRIPTIONS, configLabel } from "@/lib/labels";
import { Markdown } from "@/components/Markdown";
import { PageHeader, Section } from "@/components/ui";

export const metadata: Metadata = { title: "Methods" };

export default function Methods() {
  const env = getEnvironment();
  const ts = getTasksSummary();
  return (
    <>
      <PageHeader eyebrow="Methods" title="How LeanGraph is built">
        <p>The design decisions behind every number, stated so they can be checked against the code.</p>
      </PageHeader>
      <div className="prose prose-sm max-w-3xl text-ink-2 dark:prose-invert">
        <h2>Benchmark</h2>
        <p><strong>Mathlib held-out.</strong> From every Mathlib module, we compute how many modules import it, directly or transitively, by parsing file headers. A module is eligible only if at most 20 modules depend on it and none of those is a tactic implementation. For a theorem from module M, the proof may not use any constant from M or from anything built on M, and the retriever never indexes them. Theorems whose statement itself mentions a constant from a banned module are dropped, because their definitions&apos; unfolding lemmas would be banned too. Each statement is rendered from Lean&apos;s own signature and kept only if Lean confirms it is exactly the original theorem&apos;s type. Whole modules are assigned to a development split (prompt design) or the test split, never both; sampling round-robins across modules so no module contributes more than three theorems. Selection never looks at whether any prover can solve a theorem.</p>
        <p><strong>Authored.</strong> Theorems written for this project, each with a reference proof that passes the certifier. They measure how much held-out success depends on remembering Mathlib&apos;s own theorems.</p>
        <h2>Verification</h2>
        <p>A search-time check runs in a long-lived Lean REPL with Mathlib loaded. The verdict comes from a second, independent check: a fresh <code>lean</code> process compiles the proof as a file and a probe reports the axioms it depends on, every constant its proof term uses, and every declaration the file added, each line tagged with a random nonce generated after the proof was written. Proofs containing <code>sorry</code>, <code>admit</code>, axioms, <code>native_decide</code>, <code>set_option</code>, metaprogramming or top-level commands are rejected before compilation, and the certifier rejects them again independently if that filter is switched off (tested).</p>
        <h2>Agents</h2>
        <p>Every configuration is the same loop with parts switched on or off. Model draws are cached under a hash of the prompt and sample index, so two configurations that send the same prompt use the same draw: repair&apos;s first draft is the direct baseline&apos;s draft. The gateway&apos;s generation proved nearly deterministic for a given request, whatever the temperature, so the resampled drafts of Direct ×4 (samples 2–4) each send a fixed seed; a first, unseeded run, in which the four drafts were identical for 98 of 173 theorems, is kept as evidence.</p>
      </div>
      <Section title="Configurations">
        <div className="table-wrap"><table><tbody>{Object.entries(CONFIG_DESCRIPTIONS).map(([c, d]) => <tr key={c}><td className="font-medium">{configLabel(c)}</td><td className="text-ink-2">{d}</td></tr>)}</tbody></table></div>
      </Section>
      {ts && <Section title="Task list build"><pre className="lean">{JSON.stringify(ts, null, 2)}</pre></Section>}
      {env && <Section title="Environment"><Markdown source={env} /></Section>}
    </>
  );
}
