import type { Metadata } from "next";
import { InterimBanner } from "@/components/InterimBanner";
import { getSummary } from "@/lib/data";
import { CONFIG_DESCRIPTIONS, configLabel, FAMILY_LABELS, SPLIT_LABELS } from "@/lib/labels";
import { int, pct, pval, signed, usd } from "@/lib/format";
import { Empty, PageHeader, RateBar, Section } from "@/components/ui";

export const metadata: Metadata = { title: "Leaderboard" };

export default function Benchmark() {
  const s = getSummary();
  if (!s) return (<><PageHeader eyebrow="Leaderboard" title="Verified proof rate by configuration" /><Empty>No frozen run has been exported yet.</Empty></>);
  const rows = Object.entries(s.configs).sort((a, b) => b[1].rate - a[1].rate);
  const groups = (by: Record<string, Record<string, { rate: number; n: number; verified: number }>>, labels: Record<string, string>) => {
    const keys = Array.from(new Set(Object.values(by).flatMap((g) => Object.keys(g)))).sort();
    return { keys, labels };
  };
  const fam = groups(s.by_family, FAMILY_LABELS);
  const spl = groups(s.by_split, SPLIT_LABELS);
  return (
    <>
      <PageHeader eyebrow="Leaderboard" title="Verified proof rate by configuration">
        <p>Share of theorems for which the configuration produced a proof the certifier accepted, with a 95% Wilson interval. The same model and the same theorems throughout; configurations differ only in which parts of the loop are on.</p>
      </PageHeader>
      <InterimBanner />
      <div className="table-wrap">
        <table>
          <thead><tr><th>Configuration</th><th className="r">Verified</th><th>Rate, 95% CI</th><th className="r">≤1 call</th><th className="r">≤2</th><th className="r">≤4</th><th className="r">Median calls</th><th className="r">Cost / verified</th></tr></thead>
          <tbody>
            {rows.map(([c, m], i) => (
              <tr key={c}>
                <td><span className="font-medium">{configLabel(c)}</span>{CONFIG_DESCRIPTIONS[c] && <div className="max-w-sm text-xs text-ink-3">{CONFIG_DESCRIPTIONS[c]}</div>}</td>
                <td className="r">{m.verified}/{m.n}</td>
                <td><div className="flex items-center gap-2"><RateBar rate={m.rate} ci={m.ci} emphasis={i === 0} /><span className="num text-xs">{pct(m.rate, 1)}</span></div></td>
                <td className="r">{pct(m.success_within["1"])}</td><td className="r">{pct(m.success_within["2"])}</td><td className="r">{pct(m.success_within["4"])}</td>
                <td className="r">{m.median_calls_to_solve ?? "—"}</td><td className="r">{usd(m.cost_per_verified)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Section title="Pre-registered contrasts" note="Each row compares two configurations on the theorems both attempted. +a/−b counts theorems only the treatment / only the control solved.">
        {s.contrasts.length === 0 ? <Empty>No pair of configurations has been run on the same theorems yet.</Empty> : <div className="table-wrap"><table>
          <thead><tr><th>Contrast</th><th className="r">n</th><th className="r">Difference [95% CI]</th><th className="r">+a / −b</th><th className="r">p</th><th className="r">Holm p</th></tr></thead>
          <tbody>{s.contrasts.map((c) => (
            <tr key={c.name}><td>{c.question}<div className="text-xs text-ink-3">{configLabel(c.treatment)} vs {configLabel(c.control)}</div></td>
              <td className="r">{c.n}</td><td className="r">{signed(c.diff)} [{signed(c.diff_ci[0])}, {signed(c.diff_ci[1])}]</td>
              <td className="r">+{c.only_a} / −{c.only_b}</td><td className="r">{pval(c.p)}</td><td className="r">{pval(c.p_holm)}</td></tr>))}
          </tbody></table></div>}
      </Section>

      {[["By theorem source", s.by_split, spl], ["By family", s.by_family, fam]].map(([title, by, g]) => {
        const data = by as typeof s.by_split; const { keys, labels } = g as ReturnType<typeof groups>;
        return (
          <Section key={title as string} title={title as string}>
            <div className="table-wrap"><table>
              <thead><tr><th>Configuration</th>{keys.map((k) => <th key={k} className="r">{labels[k] ?? k}</th>)}</tr></thead>
              <tbody>{rows.map(([c]) => (
                <tr key={c}><td>{configLabel(c)}</td>{keys.map((k) => {
                  const v = data[c]?.[k];
                  return <td key={k} className="r">{v ? <>{pct(v.rate)}<span className="text-ink-3"> ({v.verified}/{int(v.n)})</span></> : "—"}</td>;
                })}</tr>))}
              </tbody></table></div>
          </Section>
        );
      })}
    </>
  );
}
