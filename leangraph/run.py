"""Run agent configurations over the benchmark and write one JSONL trace per config.

    python -m leangraph.run <config> [--split test|dev|novel|all] [--tasks id,id] [--run-id main]

Runs are resumable: tasks already present in the output file are skipped.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

from .agent import AgentConfig, WorkerPool, run_task, run_template
from .tasks import Task, load_tasks

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results" / "runs"
MAX_CONSECUTIVE_HARNESS_ERRORS = 5  # e.g. the model gateway is down: stop instead of recording failures

_full = AgentConfig("full", retrieval="hybrid", plan=True, skeleton=True, rounds=3)
CONFIGS: dict[str, AgentConfig | None] = {
    "template": None,
    # mandatory baselines
    "direct": AgentConfig("direct"),
    "direct_at4": AgentConfig("direct_at4", samples=4),  # equal-budget control for repair
    "repair": AgentConfig("repair", rounds=3),
    "rag": AgentConfig("rag", retrieval="hybrid"),
    "rag_repair": AgentConfig("rag_repair", retrieval="hybrid", rounds=3),
    "full": _full,  # planner + retrieval + repair
    # retrieval method comparison (inside rag_repair)
    "rag_repair_bm25": AgentConfig("rag_repair_bm25", retrieval="bm25", rounds=3),
    "rag_repair_dense": AgentConfig("rag_repair_dense", retrieval="dense", rounds=3),
    # ablations of `full` (full minus planning is rag_repair)
    "full_no_retrieval": replace(_full, name="full_no_retrieval", retrieval=None),
    "full_no_feedback": replace(_full, name="full_no_feedback", feedback=False),
    "full_no_memory": replace(_full, name="full_no_memory", memory=False),
    "full_no_skeleton": replace(_full, name="full_no_skeleton", skeleton=False),
}
# prompt sensitivity: same configurations, paraphrased prompt set
CONFIGS["direct_prompt_b"] = AgentConfig("direct_prompt_b", prompt="v2b")
CONFIGS["repair_prompt_b"] = AgentConfig("repair_prompt_b", rounds=3, prompt="v2b")
for _n in ["direct", "repair", "rag_repair", "full"]:
    CONFIGS[f"{_n}_think"] = replace(CONFIGS[_n], name=f"{_n}_think", think=True)


def make_retriever(tasks: list[Task], dense: bool):
    from .retrieval import PremiseIndex, load_premises

    excluded = frozenset().union(*(t.banned_modules for t in tasks)) if tasks else frozenset()
    index = PremiseIndex(load_premises(), exclude_modules=excluded, dense=dense)

    def retrieve(task: Task, method: str, k: int):
        return index.search(task.statement, method, k)

    return retrieve, index


# The canonical reasoning-off grid (`make prove`, scripts/run_main_grid.sh). Reasoning-on configurations exist in
# CONFIGS but were not run (owner decision, 2026-09-10).
MAIN_GRID = ("template", "direct", "direct_at4", "repair", "full_no_retrieval", "direct_prompt_b", "repair_prompt_b",
             "rag", "rag_repair", "full", "rag_repair_bm25", "rag_repair_dense", "full_no_feedback",
             "full_no_memory", "full_no_skeleton")


def harness_error_path(out: Path) -> Path:
    return out.with_name(out.stem + ".harness_errors.jsonl")


def completed_task_ids(out: Path) -> set[str]:
    """Task ids with a real trace. Harness-error rows (a failed model call, a crash) are not results:
    they are moved to the sidecar file so that a resumed run retries those tasks."""
    if not out.exists():
        return set()
    good, bad = [], []
    for line in out.read_text().splitlines():
        if line.strip():
            (bad if json.loads(line).get("error") else good).append(line)
    if bad:
        with harness_error_path(out).open("a") as fh:
            fh.write("".join(l + "\n" for l in bad))
        out.write_text("".join(l + "\n" for l in good))
    return {json.loads(l)["task_id"] for l in good}


def select(tasks: list[Task], split: str, ids: list[str] | None) -> list[Task]:
    if ids:
        want = set(ids)
        return [t for t in tasks if t.id in want]
    if split == "all":
        return tasks
    if split == "novel":
        return [t for t in tasks if t.split == "novel"]
    return [t for t in tasks if t.features.get("split_role") == split or (split == "test" and t.split == "novel")]


def run(config: str, split: str = "test", ids: list[str] | None = None, run_id: str = "main",
        workers: int = 2, concurrency: int = 12, pool: WorkerPool | None = None, retrieve=None,
        offline: bool = False) -> Path:
    all_tasks = load_tasks()
    tasks = select(all_tasks, split, ids)
    cfg = CONFIGS[config]
    out = RUNS / run_id / f"{config}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = completed_task_ids(out)
    todo = [t for t in tasks if t.id not in done]
    print(f"[{config}] {len(todo)} to run ({len(done)} already done)", flush=True)
    if not todo:
        return out
    own_pool = pool is None
    pool = pool or WorkerPool(workers)
    if cfg is not None and cfg.retrieval and retrieve is None:
        retrieve, _ = make_retriever(all_tasks, dense=cfg.retrieval in ("dense", "hybrid"))
    lock = threading.Lock()
    t0, n_ok, n_done, streak = time.time(), 0, 0, 0

    def one(task: Task) -> dict:
        return run_template(task, pool) if cfg is None else run_task(task, cfg, pool, retrieve, offline=offline)

    try:
        with cf.ThreadPoolExecutor(concurrency) as ex:
            futs = {ex.submit(one, t): t for t in todo}
            for f in cf.as_completed(futs):
                task = futs[f]
                try:
                    trace = f.result()
                except Exception as e:  # recorded in the sidecar, never counted as a result
                    trace = {"task_id": task.id, "config": {"name": config}, "error": repr(e), "verified": False}
                with lock:
                    target = harness_error_path(out) if trace.get("error") else out
                    with target.open("a") as fh:
                        fh.write(json.dumps(trace, ensure_ascii=False) + "\n")
                n_done += 1
                n_ok += bool(trace.get("verified"))
                streak = streak + 1 if trace.get("error") else 0
                print(f"[{config}] {n_done}/{len(todo)} {task.id} verified={trace.get('verified')}"
                      f"{' HARNESS ERROR' if trace.get('error') else ''} ({n_ok} ok, {time.time() - t0:.0f}s)", flush=True)
                if streak >= MAX_CONSECUTIVE_HARNESS_ERRORS:
                    for other in futs:
                        other.cancel()
                    print(f"[{config}] STOPPED after {streak} consecutive harness errors; last: {trace['error'][:200]}. "
                          "Resume later: unfinished tasks will be retried.", flush=True)
                    break
    finally:
        if own_pool:
            pool.close()
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="+", choices=list(CONFIGS))
    ap.add_argument("--split", default="test", choices=["test", "dev", "novel", "all"])
    ap.add_argument("--tasks", default="")
    ap.add_argument("--run-id", default="main")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--offline", action="store_true", help="replay cached LLM responses only")
    a = ap.parse_args(argv)
    ids = [s for s in a.tasks.split(",") if s] or None
    pool = WorkerPool(a.workers)
    retrievers: dict[bool, object] = {}
    try:
        for c in a.configs:
            cfg = CONFIGS[c]
            retrieve = None
            if cfg is not None and cfg.retrieval:
                dense = cfg.retrieval in ("dense", "hybrid")
                if dense not in retrievers:
                    retrievers[dense] = make_retriever(load_tasks(), dense=dense)[0]
                retrieve = retrievers[dense]
            run(c, a.split, ids, a.run_id, a.workers, a.concurrency, pool=pool, retrieve=retrieve, offline=a.offline)
    finally:
        pool.close()


if __name__ == "__main__":
    main(sys.argv[1:])
