import type { Metadata } from "next";
import { getErrorExamples, getSummary } from "@/lib/data";
import { configLabel, ERROR_CLASSES, errorLabel } from "@/lib/labels";
import { pct } from "@/lib/format";
import { Empty, LeanBlock, PageHeader, Section } from "@/components/ui";
import { HBarChart } from "@/components/charts/HBarChart";

export const metadata: Metadata = { title: "Failure taxonomy" };

export default function Errors() {
  const s = getSummary();
  const ex = getErrorExamples();
  const total = s ? Object.entries(s.errors.total).sort((a, b) => b[1] - a[1]) : [];
  const n = total.reduce((a, [, v]) => a + v, 0);
  const cfgs = s ? Object.keys(s.errors.per_config) : [];
  return (
    <>
      <PageHeader eyebrow="Failure taxonomy" title="How proofs fail">
        <p>Every failed attempt is classified by its first Lean error, using only Lean&apos;s own message. Unknown names are split into hallucinated and wrong-namespace by looking the name up in the full table of 473,141 constants from the pinned Mathlib.</p>
      </PageHeader>
      {s && n ? (<>
        <HBarChart data={total.slice(0, 10).map(([k, v]) => ({ label: errorLabel(k), value: v / n }))} xLabel={`Share of ${n.toLocaleString()} failed attempts`} />
        <Section title="Counts by configuration">
          <div className="table-wrap"><table><thead><tr><th>Error class</th>{cfgs.map((c) => <th key={c} className="r">{configLabel(c)}</th>)}</tr></thead>
            <tbody>{total.map(([k]) => (<tr key={k}><td>{errorLabel(k)}</td>{cfgs.map((c) => {
              const cnt = s.errors.per_config[c][k] ?? 0; const tot = Object.values(s.errors.per_config[c]).reduce((a, b) => a + b, 0);
              return <td key={c} className="r">{cnt}<span className="text-ink-3"> {tot ? pct(cnt / tot) : ""}</span></td>; })}</tr>))}</tbody></table></div>
        </Section>
      </>) : <Empty>No failed attempts have been recorded yet.</Empty>}
      <Section title="Definitions and examples">
        <dl className="space-y-4">
          {Object.entries(ERROR_CLASSES).map(([k, v]) => (
            <div key={k} className="panel">
              <dt className="font-medium">{v.label}</dt><dd className="mt-1 text-sm text-ink-2">{v.rule}</dd>
              {ex[k]?.[0] && <div className="mt-3 grid gap-2 lg:grid-cols-2">
                <LeanBlock code={ex[k][0].proof} label={`Example proof (${ex[k][0].task_id}, ${configLabel(ex[k][0].config)})`} />
                <LeanBlock code={ex[k][0].output} label="Lean output" /></div>}
            </div>))}
        </dl>
      </Section>
    </>
  );
}
