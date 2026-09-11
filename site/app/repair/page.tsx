import type { Metadata } from "next";
import { getSummary } from "@/lib/data";
import { configLabel, errorLabel } from "@/lib/labels";
import { pct, wilson } from "@/lib/format";
import { Empty, PageHeader, Section } from "@/components/ui";
import { LinesChart } from "@/components/charts/LinesChart";
import { HBarChart } from "@/components/charts/HBarChart";

export const metadata: Metadata = { title: "Repair loop" };
const CURVE = ["direct_at4", "repair", "rag_repair", "full"];

export default function Repair() {
  const s = getSummary();
  if (!s) return (<><PageHeader eyebrow="Repair loop" title="Does feeding Lean's errors back help?" /><Empty>No frozen run has been exported yet.</Empty></>);
  const present = CURVE.filter((c) => s.configs[c]);
  const data = [1, 2, 3, 4, 5].map((n) => ({ calls: n, ...Object.fromEntries(present.map((c) => [c, s.configs[c].success_within[String(n)] ?? 0])) }));
  const rb = Object.entries(s.errors.repair_by_class).filter(([, v]) => v.n >= 5).sort((a, b) => b[1].rate - a[1].rate)
    .map(([k, v]) => { const [lo, hi] = wilson(v.next_round_verified, v.n); return { label: `${errorLabel(k)} (n=${v.n})`, value: v.rate, lo, hi }; });
  return (
    <>
      <PageHeader eyebrow="Repair loop" title="Does feeding Lean's errors back help?">
        <p>A repair round shows the model its previous proof and exactly what Lean printed, nothing more. The fair comparison is against spending the same number of calls on independent fresh drafts (Direct ×4), not against a single draft.</p>
      </PageHeader>
      {present.length > 0 && <LinesChart data={data} series={present.map((c) => ({ key: c, label: configLabel(c) }))} xKey="calls" xLabel="Model calls allowed per theorem" yLabel="Verified" />}
      <Section title="Repair success" note="Among theorems whose first draft failed, the share later verified within the same run.">
        <div className="table-wrap"><table><thead><tr><th>Configuration</th><th className="r">First draft failed</th><th className="r">Later verified</th></tr></thead>
          <tbody>{Object.entries(s.configs).filter(([, m]) => m.repair_success != null).map(([c, m]) => (
            <tr key={c}><td>{configLabel(c)}</td><td className="r">{m.n_first_failed}</td><td className="r">{pct(m.repair_success)}</td></tr>))}</tbody></table></div>
      </Section>
      <Section title="Which errors get repaired" note="For each class of first error, how often the very next round in the same run produced a verified proof. Classes with fewer than five cases are omitted; 95% Wilson intervals.">
        {rb.length ? <HBarChart data={rb} xLabel="Next round verified" /> : <Empty>Not enough repair rounds yet.</Empty>}
      </Section>
    </>
  );
}
