import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTheorem, getTheorems } from "@/lib/data";
import { FAMILY_LABELS, SPLIT_LABELS } from "@/lib/labels";
import { LeanBlock, PageHeader, Section } from "@/components/ui";
import { TheoremTrace } from "@/components/TheoremTrace";

export function generateStaticParams() {
  return getTheorems().map((t) => ({ id: t.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: id };
}

export default async function TheoremPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = getTheorem(id);
  if (!d) notFound();
  const t = d.task;
  const header = `${t.opens ? `open ${t.opens} in\n` : ""}theorem lg_target ${t.statement} := by`;
  const f = t.features as Record<string, number | string | boolean | null>;
  return (
    <>
      <p className="text-xs text-ink-3"><Link href="/theorems" className="underline">Theorems</Link> / <span className="font-mono">{t.id}</span></p>
      <PageHeader title={`${FAMILY_LABELS[t.family] ?? t.family} · ${t.difficulty}`} eyebrow={SPLIT_LABELS[t.split] ?? t.split} />
      <LeanBlock code={header} label="Statement, exactly as the model and Lean see it" />
      <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        {t.split === "mathlib_heldout" ? (<>
          <div><dt className="text-xs text-ink-3">Mathlib declaration</dt><dd className="font-mono text-xs">{t.source}</dd></div>
          <div><dt className="text-xs text-ink-3">Held-out module</dt><dd className="font-mono text-xs">{t.module}</dd></div>
          <div><dt className="text-xs text-ink-3">Banned modules (itself + downstream)</dt><dd>{t.banned_modules.length}</dd></div>
          <div><dt className="text-xs text-ink-3">Reference proof premises (reachable / held-out)</dt><dd>{String(f.gt_premises_reachable ?? "—")} / {Array.isArray(f.gt_premises_heldout) ? (f.gt_premises_heldout as unknown as string[]).length : "—"}</dd></div>
        </>) : (<>
          <div><dt className="text-xs text-ink-3">Source</dt><dd>Written for LeanGraph, reference proof certified</dd></div>
          <div><dt className="text-xs text-ink-3">Premises used by the reference proof</dt><dd>{t.gt_premises.length}</dd></div>
        </>)}
      </dl>
      <Section title="Traces" note="Each configuration's full record: what was retrieved, what the model wrote, what Lean said back.">
        <TheoremTrace runs={d.runs} header={header} />
      </Section>
      <Section title="Reference proof" note={t.split === "mathlib_heldout" ? "Mathlib's own source for this declaration, shown for comparison. It may use lemmas the prover is not allowed to use." : "The proof we wrote and certified before any model ran."}>
        <LeanBlock code={t.reference_proof} />
      </Section>
    </>
  );
}
