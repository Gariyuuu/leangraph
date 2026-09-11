"""Retrieval benchmark, measured independently of proving.

Ground truth for a task is the set of indexed Mathlib theorems its reference
proof uses (held-out: Mathlib's own proof term; novel: our certified proof).
Premises from held-out modules are not in the index, so they count as neither
hits nor misses; recall is over reachable premises only. hit@k (any reachable
ground-truth premise in the top k) is reported alongside recall@k because
ground-truth sets are large and dominated by general-purpose lemmas.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .retrieval import PremiseIndex, load_premises, recall_at_k, reciprocal_rank
from .stats import bootstrap_ci
from .tasks import load_tasks

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "retrieval"
KS = (1, 5, 8, 10, 20, 50)
METHODS = ("bm25", "dense", "hybrid")


def evaluate(index: PremiseIndex | None = None, methods: tuple[str, ...] = METHODS) -> dict:
    tasks = load_tasks()
    if index is None:
        excluded = frozenset().union(*(t.banned_modules for t in tasks))
        index = PremiseIndex(load_premises(), exclude_modules=excluded, dense=any(m != "bm25" for m in methods))
    indexed = {p.name for p in index.premises}
    rows = []
    for t in tasks:
        rel = set(t.gt_premises) & indexed
        if not rel:
            continue
        for m in methods:
            ranked = [p.name for p in index.search(t.statement, m, max(KS))]
            row = {"task_id": t.id, "split": t.split, "family": t.family, "method": m, "n_relevant": len(rel),
                   "rr": reciprocal_rank(ranked, rel), "retrieved": ranked[:20]}
            row.update({f"recall@{k}": recall_at_k(ranked, rel, k) for k in KS})
            row.update({f"hit@{k}": float(bool(set(ranked[:k]) & rel)) for k in KS})
            rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "per_task.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    summary: dict = {"n_tasks_with_ground_truth": len({r["task_id"] for r in rows}), "methods": {}}
    for m in methods:
        for split in ("all", "mathlib_heldout", "novel"):
            sel = [r for r in rows if r["method"] == m and (split == "all" or r["split"] == split)]
            if not sel:
                continue
            entry = {"n": len(sel)}
            for key in ["rr"] + [f"recall@{k}" for k in KS] + [f"hit@{k}" for k in KS]:
                v = np.array([r[key] for r in sel], dtype=float)
                lo, hi = bootstrap_ci(v, seed=1)
                entry[key] = {"mean": float(v.mean()), "ci": [lo, hi]}
            summary["methods"].setdefault(m, {})[split] = entry
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    import sys
    s = evaluate(methods=tuple(sys.argv[1].split(",")) if len(sys.argv) > 1 else METHODS)
    for m, by in s["methods"].items():
        a = by["all"]
        print(f"{m:7s} n={a['n']:3d} MRR={a['rr']['mean']:.3f} R@8={a['recall@8']['mean']:.3f} "
              f"R@20={a['recall@20']['mean']:.3f} R@50={a['recall@50']['mean']:.3f}")
