import type { Metadata } from "next";
import { getTheorems } from "@/lib/data";
import { Empty, PageHeader } from "@/components/ui";
import { TheoremsExplorer } from "@/components/TheoremsExplorer";

export const metadata: Metadata = { title: "Theorems" };

export default function Theorems() {
  const rows = getTheorems();
  return (
    <>
      <PageHeader eyebrow="Task browser" title="Every theorem in the benchmark">
        <p>Held-out theorems come from Mathlib modules that almost nothing imports; their proofs may not use anything from that module or from modules built on it. Authored theorems were written for this project and each has a certified reference proof.</p>
      </PageHeader>
      {rows.length ? <TheoremsExplorer rows={rows} /> : <Empty>The task list has not been exported yet.</Empty>}
    </>
  );
}
