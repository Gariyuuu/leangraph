import { getStatus } from "@/lib/data";
import { configLabel } from "@/lib/labels";

export function InterimBanner() {
  const st = getStatus();
  if (!st || st.final) return null;
  const pending = st.configs.filter((c) => c.state !== "complete");
  return (
    <div role="status" className="mb-6 rounded-md border border-line bg-paper-2 px-4 py-3 text-sm text-ink-2">
      <strong className="text-ink">Interim release.</strong> {st.complete} of {st.expected} agent configurations are complete;{" "}
      {pending.length} are still running ({pending.map((c) => `${configLabel(c.config)} ${c.done}/${c.total}`).join(", ")}). Comparisons that need
      them are not shown yet, and every number here will be recomputed when the grid finishes.
    </div>
  );
}
