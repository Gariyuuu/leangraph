import type { Metadata } from "next";
import { getSummary } from "@/lib/data";
import { configLabel } from "@/lib/labels";
import { int, pct, usd } from "@/lib/format";
import { Empty, PageHeader, Section } from "@/components/ui";
import { CostScatter } from "@/components/charts/CostScatter";

export const metadata: Metadata = { title: "Cost" };

export default function Cost() {
  const s = getSummary();
  if (!s) return (<><PageHeader eyebrow="Cost" title="What does a verified theorem cost?" /><Empty>No frozen run has been exported yet.</Empty></>);
  const rows = Object.entries(s.configs).sort((a, b) => (a[1].cost_per_verified ?? Infinity) - (b[1].cost_per_verified ?? Infinity));
  return (
    <>
      <PageHeader eyebrow="Cost" title="What does a verified theorem cost?">
        <p>Model cost is the provider-reported charge for every call, including calls replayed from the response cache (so each configuration is priced as if run alone). Lean time is the fast REPL checks plus the independent certification of every candidate proof.</p>
      </PageHeader>
      <CostScatter points={rows.filter(([c]) => c !== "template").map(([c, m]) => ({ label: configLabel(c), cost: m.cost_usd / Math.max(1, m.n), rate: m.rate }))} />
      <Section title="Budget by configuration">
        <div className="table-wrap"><table>
          <thead><tr><th>Configuration</th><th className="r">Verified</th><th className="r">Model calls</th><th className="r">Tokens</th><th className="r">Cost</th><th className="r">Cost / verified</th><th className="r">Tokens / verified</th><th className="r">Lean check s</th><th className="r">Certify s</th><th className="r">Timeouts</th></tr></thead>
          <tbody>{rows.map(([c, m]) => (
            <tr key={c}><td>{configLabel(c)}</td><td className="r">{pct(m.rate)}</td><td className="r">{int(m.llm_calls)}</td><td className="r">{int(m.tokens)}</td>
              <td className="r">{usd(m.cost_usd)}</td><td className="r">{usd(m.cost_per_verified)}</td><td className="r">{int(m.tokens_per_verified)}</td>
              <td className="r">{int(m.lean_check_s)}</td><td className="r">{int(m.certify_s)}</td><td className="r">{pct(m.timeout_rate, 1)}</td></tr>))}</tbody>
        </table></div>
      </Section>
    </>
  );
}
