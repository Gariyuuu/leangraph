"""End-to-end walk-through on a few theorems, printed stage by stage.

    python -m leangraph.demo novel_nt_03 novel_ineq_02 ...

statement -> retrieved lemmas -> model draft -> Lean output (classified)
-> repair -> certificate. Uses BM25 retrieval so it runs without the dense
index. Traces go to results/runs/demo/.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path

from .agent import AgentConfig, WorkerPool, run_task, theorem_header
from .errors import classify_attempt
from .retrieval import PremiseIndex, load_premises
from .tasks import TASKS_PATH, Task, load_tasks

ROOT = Path(__file__).resolve().parents[1]
CFG = AgentConfig("demo_rag_repair_bm25", retrieval="bm25", k=8, rounds=3)


def _tasks() -> list[Task]:
    if TASKS_PATH.exists():
        return load_tasks()
    rows = [json.loads(l) for l in (ROOT / "corpus" / "novel_verified.jsonl").read_text().splitlines()]
    return [Task(id=r["id"], statement=r["statement"], opens=r.get("opens", ""), family=r["family"],
                 difficulty=r["difficulty"], split="novel", source="authored", reference_proof=r["proof"])
            for r in rows if r.get("certified")]


def show(task: Task, tr: dict) -> str:
    out = [f"\n{'=' * 78}\n{task.id}  [{task.family}/{task.difficulty}]\n{theorem_header(task)}",
           "retrieved: " + ", ".join(tr["retrieved"])]
    for a in tr["attempts"]:
        cert = a.get("certificate") or {}
        cls = "VERIFIED" if cert.get("verified") else classify_attempt(a)["primary"]
        out.append(f"--- round {a['round']} ({a['completion_tokens']} tok, {a['latency_s']:.1f}s) -> {cls}")
        out.append("  proof: " + (a["proof"] or "<none>").replace("\n", "\n         "))
        if not cert.get("verified"):
            out.append("  lean:  " + a["compiler_output"][:500].replace("\n", "\n         "))
    c = tr.get("certificate") or {}
    out.append(f"RESULT verified={tr['verified']}" + (f"  axioms={c.get('axioms')}" if c else "")
               + f"  calls={tr['usage']['llm_calls']}  cost=${tr['usage']['cost_usd']:.5f}")
    return "\n".join(out)


def main(ids: list[str]) -> None:
    tasks = {t.id: t for t in _tasks()}
    chosen = [tasks[i] for i in ids if i in tasks]
    missing = [i for i in ids if i not in tasks]
    if missing:
        print("not available (uncertified or unknown):", missing)
    all_tasks = list(tasks.values())
    excluded = frozenset().union(*(t.banned_modules for t in all_tasks))  # same rule as run.make_retriever
    index = PremiseIndex(load_premises(), exclude_modules=excluded, dense=False)
    retrieve = lambda t, m, k: index.search(t.statement, m, k)
    pool = WorkerPool(1)
    out = ROOT / "results" / "runs" / "demo" / f"{CFG.name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with cf.ThreadPoolExecutor(len(chosen) or 1) as ex:
            traces = list(ex.map(lambda t: run_task(t, CFG, pool, retrieve), chosen))
    finally:
        pool.close()
    with out.open("w") as f:
        for tr in traces:
            f.write(json.dumps(tr, ensure_ascii=False) + "\n")
    for t, tr in zip(chosen, traces):
        print(show(t, tr))
    print(f"\n{sum(tr['verified'] for tr in traces)}/{len(traces)} verified; traces in {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
