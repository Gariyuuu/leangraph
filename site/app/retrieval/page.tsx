import type { Metadata } from "next";
import { getRetrieval, getSummary } from "@/lib/data";
import { configLabel, SPLIT_LABELS } from "@/lib/labels";
import { pct } from "@/lib/format";
import { Empty, PageHeader, Section } from "@/components/ui";
import { LinesChart } from "@/components/charts/LinesChart";

export const metadata: Metadata = { title: "Retrieval" };
const KS = [1, 5, 8, 10, 20, 50];
const M: Record<string, string> = { bm25: "BM25", dense: "Dense (bge-small)", hybrid: "Hybrid (RRF)" };
type Cell = { mean: number; ci: [number, number] };

export default function Retrieval() {
  const r = getRetrieval();
  const s = getSummary();
  const methods = r ? Object.keys(M).filter((m) => r.methods[m]) : [];
  const data = KS.map((k) => ({ k, ...Object.fromEntries(methods.map((m) => [m, (r!.methods[m].all[`recall@${k}`] as Cell).mean])) }));
  return (
    <>
      <PageHeader eyebrow="Retrieval" title="Does the retriever find the lemmas a proof needs?">
        <p>Measured on its own, before any proving. The ground truth for a theorem is the set of indexed Mathlib theorems its reference proof uses. Premises from held-out modules are removed from the index when it is built, so no retriever can return the target or anything downstream of it.</p>
      </PageHeader>
      {r ? (<>
        <LinesChart data={data} series={methods.map((m) => ({ key: m, label: M[m] }))} xKey="k" xLabel="k (number of lemmas retrieved)" yLabel="Recall" logX />
        <Section title="Recall and mean reciprocal rank" note={`${r.n_tasks_with_ground_truth} theorems have at least one reachable ground-truth premise. 95% bootstrap intervals over theorems.`}>
          <div className="table-wrap"><table>
            <thead><tr><th>Retriever</th><th>Theorems</th><th className="r">n</th><th className="r">MRR</th>{KS.map((k) => <th key={k} className="r">R@{k}</th>)}</tr></thead>
            <tbody>{methods.flatMap((m) => Object.entries(r.methods[m]).map(([split, e]) => (
              <tr key={m + split}><td>{M[m]}</td><td>{split === "all" ? "All" : SPLIT_LABELS[split] ?? split}</td><td className="r">{e.n as number}</td>
                <td className="r">{(e.rr as Cell).mean.toFixed(3)}</td>{KS.map((k) => <td key={k} className="r">{pct((e[`recall@${k}`] as Cell).mean)}</td>)}</tr>)))}
            </tbody></table></div>
        </Section>
      </>) : <Empty>The retrieval benchmark has not been run yet (<code className="font-mono">make retrieve</code>).</Empty>}
      {s && (
        <Section title="Recall inside the agent runs" note="Mean share of a theorem's ground-truth premises that appeared in the eight lemmas actually shown to the model.">
          <div className="table-wrap"><table><thead><tr><th>Configuration</th><th className="r">Mean recall@8</th><th className="r">Verified</th></tr></thead>
            <tbody>{Object.entries(s.configs).filter(([, m]) => m.mean_retrieval_recall != null).map(([c, m]) => (
              <tr key={c}><td>{configLabel(c)}</td><td className="r">{pct(m.mean_retrieval_recall)}</td><td className="r">{pct(m.rate)}</td></tr>))}</tbody></table></div>
        </Section>
      )}
    </>
  );
}
