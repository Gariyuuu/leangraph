"""Export frozen results as static JSON for the web app (site/public/data).

    python -m leangraph.export_site --run-id main

The site never computes a number: it renders these files. Every value comes
from the task list, the traces and the analysis summary.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .analyze import analyze, load_traces
from .errors import classify_attempt
from .tasks import load_tasks

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "data"
SITE_PUBLIC = ROOT / "site" / "public"
ENV_DOC = ROOT / "docs" / "ENVIRONMENT.md"


def _slim_attempt(a: dict) -> dict:
    cert = a.get("certificate") or {}
    return {
        "sample": a.get("sample"), "round": a.get("round"), "proof": a.get("proof", ""),
        "compiler_output": a.get("compiler_output", "")[:4000], "repl_ok": a.get("repl_ok"),
        "verified": bool(cert.get("verified")), "cert_reason": cert.get("reason"),
        "error_class": None if cert.get("verified") else classify_attempt(a)["primary"],
        "completion_tokens": a.get("completion_tokens"), "latency_s": a.get("latency_s"),
        "timed_out": a.get("timed_out", False),
    }


def run_status(summary: dict, n_tasks: int, grid: tuple[str, ...]) -> dict:
    """Which main-grid configurations are complete (a real trace for every test task), partial or not started."""
    rows = []
    for c in grid:
        m = summary["configs"].get(c) or summary.get("configs_partial", {}).get(c)
        done = m["n"] if m else 0
        rows.append({"config": c, "done": done, "total": n_tasks,
                     "state": "complete" if done >= n_tasks else ("partial" if done else "not started")})
    complete = sum(r["state"] == "complete" for r in rows)
    return {"configs": rows, "complete": complete, "expected": len(grid), "final": complete == len(grid)}


def export(run_id: str) -> Path:
    tasks = load_tasks()
    summary = analyze(run_id)
    # The analysis loader skips harness-error sidecars and error rows, so the site shows exactly what was scored.
    traces = load_traces(run_id)

    if SITE_DATA.exists():
        shutil.rmtree(SITE_DATA)
    (SITE_DATA / "theorem").mkdir(parents=True)

    index = []
    for t in tasks:
        per_cfg = {c: bool(tr[t.id].get("verified")) for c, tr in traces.items() if t.id in tr}
        index.append({"id": t.id, "family": t.family, "difficulty": t.difficulty, "split": t.split,
                      "role": t.features.get("split_role"), "statement": t.statement, "opens": t.opens,
                      "source": t.source, "solved_by": [c for c, v in per_cfg.items() if v], "n_configs": len(per_cfg)})
        detail = {
            "task": {**t.to_dict(), "features": {k: v for k, v in t.features.items() if k != "axioms"}},
            "runs": {c: {
                "verified": tr[t.id].get("verified"), "final_proof": tr[t.id].get("final_proof"),
                "retrieved": tr[t.id].get("retrieved", []), "plan": tr[t.id].get("plan"),
                "usage": tr[t.id].get("usage"), "certificate": {k: v for k, v in (tr[t.id].get("certificate") or {}).items()
                                                               if k in ("verified", "reason", "axioms", "elapsed_s")},
                "attempts": [_slim_attempt(a) for a in tr[t.id].get("attempts", [])],
                "error": tr[t.id].get("error"),
            } for c, tr in traces.items() if t.id in tr},
        }
        (SITE_DATA / "theorem" / f"{t.id}.json").write_text(json.dumps(detail, ensure_ascii=False))
    (SITE_DATA / "theorems.json").write_text(json.dumps(index, ensure_ascii=False))
    summary_slim = {k: v for k, v in summary.items() if k != "errors"}
    summary_slim["errors"] = {k: v for k, v in summary["errors"].items() if k != "examples"}
    (SITE_DATA / "summary.json").write_text(json.dumps(summary_slim, default=str))
    # Aliased: importing `load_tasks` by its own name inside this function would make every earlier use of the
    # module-level name in export() a reference to an unassigned local (UnboundLocalError).
    from .run import MAIN_GRID as _MAIN_GRID, select as _select
    from .tasks import load_tasks as _load_tasks
    status = run_status(summary, len(_select(_load_tasks(), "test", None)), _MAIN_GRID)
    (SITE_DATA / "status.json").write_text(json.dumps(status))
    (SITE_DATA / "error_examples.json").write_text(json.dumps(summary["errors"]["examples"], ensure_ascii=False))
    retr = ROOT / "results" / "retrieval" / "summary.json"
    if retr.exists():
        shutil.copy(retr, SITE_DATA / "retrieval.json")
    if ENV_DOC.exists():
        (SITE_DATA / "environment.md").write_text(ENV_DOC.read_text())
    paper = ROOT / "paper" / "paper.md"
    if paper.exists():
        (SITE_DATA / "paper.md").write_text(paper.read_text())
    tsum = ROOT / "corpus" / "tasks_summary.json"
    if tsum.exists():
        shutil.copy(tsum, SITE_DATA / "tasks_summary.json")
    # The paper links figures repo-relatively (../results/figures/<run>/x.png). On the site those paths do not exist,
    # so copy the figures into public/figures/ and point the site's copy of the paper there.
    figs = ROOT / "results" / "figures" / run_id
    pub = SITE_PUBLIC / "figures"
    if pub.exists():
        shutil.rmtree(pub)
    if figs.exists():
        pub.mkdir(parents=True)
        for f in figs.glob("*.png"):
            shutil.copy(f, pub / f.name)
    site_paper = SITE_DATA / "paper.md"
    if site_paper.exists():
        site_paper.write_text(site_paper.read_text().replace(f"../results/figures/{run_id}/", "/figures/"))
    return SITE_DATA


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="main")
    print("exported to", export(ap.parse_args().run_id))
