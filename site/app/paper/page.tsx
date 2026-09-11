import type { Metadata } from "next";
import { getPaper } from "@/lib/data";
import { Markdown } from "@/components/Markdown";
import { Empty, PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Paper" };

export default function Paper() {
  const p = getPaper();
  return p ? <div className="max-w-3xl"><Markdown source={p} /></div> : (
    <><PageHeader eyebrow="Paper" title="LeanGraph: Evaluating Retrieval and Verifier-Guided Repair for LLM Theorem Proving" />
      <Empty>The paper is generated from the frozen results (<code className="font-mono">make paper</code>) and appears here once the benchmark has been run.</Empty></>
  );
}
