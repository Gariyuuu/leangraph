"""Metrics, paired comparisons, error taxonomy and cost, from traces only.

    python -m leangraph.analyze --run-id main

Every number here is recomputed from `results/runs/<run_id>/*.jsonl` and the
task list; nothing is typed in by hand.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from .errors import CLASSES, classify_attempt
from .stats import holm, mcnemar_exact, paired_diff_ci, wilson
from .tasks import load_tasks

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results" / "runs"
OUT = ROOT / "results" / "analysis"

# Pre-registered contrasts: (name, treatment, control, research question).
CONTRASTS = [
    ("feedback_repair", "repair", "direct", "RQ2 compiler-feedback repair vs one draft"),
    ("repair_vs_equal_budget", "repair", "direct_at4", "RQ2 repair vs independent resampling at equal LLM calls"),
    ("retrieval", "rag", "direct", "RQ1 retrieval, single draft"),
    ("retrieval_with_repair", "rag_repair", "repair", "RQ1 retrieval, with repair"),
    ("planning", "full", "rag_repair", "RQ3 planning on top of retrieval + repair"),
    ("agentic_vs_direct", "full", "direct", "Primary: full agent vs direct generation"),
    ("abl_retrieval", "full", "full_no_retrieval", "Ablation: retrieval"),
    ("abl_feedback", "full", "full_no_feedback", "Ablation: compiler feedback"),
    ("abl_memory", "full", "full_no_memory", "Ablation: memory of earlier attempts"),
    ("abl_skeleton", "full", "full_no_skeleton", "Ablation: proof skeleton"),
    ("bm25_vs_hybrid", "rag_repair_bm25", "rag_repair", "Retriever: BM25 vs hybrid"),
    ("dense_vs_hybrid", "rag_repair_dense", "rag_repair", "Retriever: dense vs hybrid"),
    ("template_vs_direct", "direct", "template", "LLM vs no-LLM automation"),
    ("prompt_direct", "direct_prompt_b", "direct", "Prompt sensitivity: paraphrased prompt, direct"),
    ("prompt_repair", "repair_prompt_b", "repair", "Prompt sensitivity: paraphrased prompt, repair"),
    ("think_direct", "direct_think", "direct", "RQ6/7 reasoning tier, direct"),
    ("think_full", "full_think", "full", "RQ6/7 reasoning tier, full agent"),
]
MAX_CALLS = 5


HARNESS_ERRORS: dict[str, int] = {}


def load_traces(run_id: str) -> dict[str, dict[str, dict]]:
    """Real traces only. A harness-error row (model call failed, crash) is not a proof attempt, so it is
    excluded from every denominator and counted in HARNESS_ERRORS, including rows in sidecar files."""
    out: dict[str, dict[str, dict]] = {}
    HARNESS_ERRORS.clear()
    for p in sorted((RUNS / run_id).glob("*.jsonl")):
        if p.name.endswith(".harness_errors.jsonl"):
            continue
        rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        out[p.stem] = {r["task_id"]: r for r in rows if not r.get("error")}
        side = p.with_name(p.stem + ".harness_errors.jsonl")
        side_ids = {json.loads(l)["task_id"] for l in side.read_text().splitlines() if l.strip()} if side.exists() else set()
        unresolved = ({r["task_id"] for r in rows if r.get("error")} | side_ids) - set(out[p.stem])
        HARNESS_ERRORS[p.stem] = len(unresolved)
    return out


def _calls_to_solve(tr: dict) -> int | None:
    if not tr.get("verified"):
        return None
    if tr.get("config", {}).get("name") == "template":
        return 0
    return tr.get("solved_at", {}).get("llm_calls")


def _retrievable(names) -> set[str]:
    """Ground-truth premises a retriever could return: indexed, not tactic-internal."""
    from .retrieval import is_tactic_internal, user_facing_names
    idx = user_facing_names()
    return {n for n in names if not is_tactic_internal(n) and (idx is None or n in idx)}


def _first_ok(tr: dict) -> bool:
    atts = tr.get("attempts") or []
    return bool(atts) and bool((atts[0].get("certificate") or {}).get("verified"))


def config_metrics(traces: dict[str, dict], tasks: dict) -> dict:
    ids = [i for i in traces if i in tasks]
    ver = [bool(traces[i].get("verified")) for i in ids]
    k, n = sum(ver), len(ids)
    lo, hi = wilson(k, n)
    usage = [traces[i].get("usage", {}) for i in ids]
    calls = [_calls_to_solve(traces[i]) for i in ids]
    solved_calls = [c for c in calls if c is not None]
    attempts = [a for i in ids for a in traces[i].get("attempts", [])]
    cost = sum(u.get("cost_usd", 0.0) for u in usage)
    tokens = sum(u.get("prompt_tokens", 0) + u.get("completion_tokens", 0) for u in usage)
    repairs = any((traces[i].get("config") or {}).get("rounds", 0) > 0 for i in ids)
    first_failed = [i for i in ids if traces[i].get("attempts") and not _first_ok(traces[i])] if repairs else []
    repaired = [i for i in first_failed if traces[i].get("verified")]
    recall = []
    for i in ids:
        gt = _retrievable(tasks[i].gt_premises)
        if gt and traces[i].get("retrieved"):
            recall.append(len(gt & set(traces[i]["retrieved"])) / len(gt))
    proofs = [traces[i]["final_proof"] for i in ids if traces[i].get("final_proof")]
    # Repair stagnation: a repair attempt identical to an earlier attempt in the same sample.
    rep_n = rep_same = 0
    for i in ids:
        seen: dict = {}
        for a in traces[i].get("attempts", []):
            if a.get("round") is None:
                continue
            key = (a.get("sample"), a.get("proof", "").strip())
            if a["round"] > 0:
                rep_n += 1
                rep_same += key in seen
            seen[key] = True
    return {
        "n": n, "verified": k, "rate": k / n if n else float("nan"), "ci": [lo, hi],
        "success_within": {c: sum(1 for x in calls if x is not None and x <= c) / n if n else 0 for c in range(0, MAX_CALLS + 1)},
        "median_calls_to_solve": st.median(solved_calls) if solved_calls else None,
        "llm_calls": sum(u.get("llm_calls", 0) for u in usage),
        "tokens": tokens, "cost_usd": cost,
        "cost_per_verified": cost / k if k else None, "tokens_per_verified": tokens / k if k else None,
        "lean_check_s": sum(u.get("lean_check_s", 0.0) for u in usage),
        "certify_s": sum(u.get("certify_s", 0.0) for u in usage),
        "median_lean_check_s": st.median(ls) if (ls := [a["lean_s"] for a in attempts if a.get("lean_s") is not None]) else None,
        "timeout_rate": (sum(bool(a.get("timed_out")) for a in attempts) / len(attempts)) if attempts else 0.0,
        "repair_success": (len(repaired) / len(first_failed)) if first_failed else None,  # None: config never repairs
        "n_first_failed": len(first_failed),
        "repeat_rate": (rep_same / rep_n) if rep_n else None, "n_repair_attempts": rep_n,
        "mean_retrieval_recall": float(np.mean(recall)) if recall else None,
        "median_proof_lines": st.median([len([l for l in p.splitlines() if l.strip()]) for p in proofs]) if proofs else None,
        "errors_trace": sum(1 for i in ids if traces[i].get("error")),
    }


def breakdown(traces: dict[str, dict], tasks: dict, key) -> dict:
    groups: dict[str, list[bool]] = defaultdict(list)
    for i, tr in traces.items():
        if i in tasks:
            groups[key(tasks[i])].append(bool(tr.get("verified")))
    return {g: {"n": len(v), "verified": sum(v), "rate": sum(v) / len(v), "ci": list(wilson(sum(v), len(v)))}
            for g, v in sorted(groups.items())}


def contrasts(all_traces: dict, tasks: dict) -> list[dict]:
    rows = []
    for name, a, b, rq in CONTRASTS:
        if a not in all_traces or b not in all_traces:
            continue
        common = sorted(set(all_traces[a]) & set(all_traces[b]) & set(tasks))
        if not common:
            continue
        va = [bool(all_traces[a][i].get("verified")) for i in common]
        vb = [bool(all_traces[b][i].get("verified")) for i in common]
        diff, lo, hi = paired_diff_ci(va, vb, seed=7)
        rows.append({"name": name, "treatment": a, "control": b, "question": rq, "n": len(common),
                     "rate_treatment": float(np.mean(va)), "rate_control": float(np.mean(vb)),
                     "diff": diff, "diff_ci": [lo, hi], **mcnemar_exact(va, vb)})
    adj = holm({r["name"]: r["p"] for r in rows})
    for r in rows:
        r["p_holm"] = adj[r["name"]]
    return rows


def error_taxonomy(all_traces: dict) -> dict:
    """Primary class of every failed attempt, and how often the next round then succeeds."""
    per_config: dict[str, Counter] = {}
    next_ok: dict[str, list[bool]] = defaultdict(list)
    examples: dict[str, list[dict]] = defaultdict(list)
    for cfg, traces in all_traces.items():
        c = Counter()
        for tid, tr in traces.items():
            atts = tr.get("attempts", [])
            for j, a in enumerate(atts):
                if (a.get("certificate") or {}).get("verified"):
                    continue
                cls = classify_attempt(a)
                c[cls["primary"]] += 1
                if len(examples[cls["primary"]]) < 6 and a.get("proof"):
                    examples[cls["primary"]].append({"task_id": tid, "config": cfg, "proof": a["proof"][:400],
                                                     "output": a.get("compiler_output", "")[:400]})
                nxt = atts[j + 1] if j + 1 < len(atts) else None
                if nxt is not None and nxt.get("sample") == a.get("sample") and "round" in a:
                    next_ok[cls["primary"]].append(bool((nxt.get("certificate") or {}).get("verified")))
        per_config[cfg] = c
    total = Counter()
    for c in per_config.values():
        total.update(c)
    repair = {k: {"n": len(v), "next_round_verified": sum(v), "rate": sum(v) / len(v)} for k, v in next_ok.items() if v}
    return {"classes": CLASSES, "total": dict(total), "per_config": {k: dict(v) for k, v in per_config.items()},
            "repair_by_class": repair, "examples": examples}


def difficulty_analysis(all_traces: dict, tasks: dict) -> dict:
    """Spearman correlation of each proxy with solve rate across all configurations."""
    solve = defaultdict(list)
    for traces in all_traces.values():
        for i, tr in traces.items():
            if i in tasks:
                solve[i].append(bool(tr.get("verified")))
    ids = [i for i in solve if tasks[i].split == "mathlib_heldout"]
    rate = [np.mean(solve[i]) for i in ids]
    out = {}
    for proxy in ["ref_proof_lines", "ref_tactic_diversity", "gt_premises_reachable", "type_depth",
                  "statement_chars", "difficulty_score", "binder_groups"]:
        x = [tasks[i].features.get(proxy) for i in ids]
        if any(v is None for v in x) or len(set(x)) < 2 or len(set(rate)) < 2:
            continue
        rho, p = spearmanr(x, rate)
        out[proxy] = {"spearman_rho": float(rho), "p": float(p), "n": len(ids)}
    return out


def analyze(run_id: str) -> dict:
    tasks = {t.id: t for t in load_tasks()}
    loaded = load_traces(run_id)
    # A configuration is reported only when it has a real trace for every task in the run. The grid runs every
    # configuration on the same tasks, so the run's task set is the union across configurations. Configurations
    # still running, or holding unresolved harness errors, are listed in configs_partial and feed no metric,
    # breakdown, contrast or Holm family: a partial run must never produce a claim.
    task_set = set().union(*(set(tr) for tr in loaded.values())) if loaded else set()
    all_traces = {c: tr for c, tr in loaded.items() if task_set <= set(tr)}
    result = {"run_id": run_id, "n_tasks": len(task_set), "configs": {}, "by_split": {}, "by_family": {},
              "by_difficulty": {},
              "configs_partial": {c: {"n": len(tr), "harness_errors_unresolved": HARNESS_ERRORS.get(c, 0)}
                                  for c, tr in loaded.items() if c not in all_traces}}
    for cfg, traces in all_traces.items():
        result["configs"][cfg] = {**config_metrics(traces, tasks), "harness_errors_unresolved": HARNESS_ERRORS.get(cfg, 0)}
        result["by_split"][cfg] = breakdown(traces, tasks, lambda t: t.split)
        result["by_family"][cfg] = breakdown(traces, tasks, lambda t: t.family)
        result["by_difficulty"][cfg] = breakdown(traces, tasks, lambda t: f"{t.split}/{t.difficulty}")
    result["contrasts"] = contrasts(all_traces, tasks)
    result["errors"] = error_taxonomy(all_traces)
    result["difficulty_correlations"] = difficulty_analysis(all_traces, tasks)
    out = OUT / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result, indent=1, default=str))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="main")
    r = analyze(ap.parse_args().run_id)
    print(f"{'config':22s} {'n':>4s} {'verified':>9s} {'rate':>6s}  95% CI          cost/verified")
    for cfg, m in sorted(r["configs"].items(), key=lambda kv: -kv[1]["rate"]):
        cpv = f"${m['cost_per_verified']:.4f}" if m["cost_per_verified"] else "-"
        print(f"{cfg:22s} {m['n']:4d} {m['verified']:9d} {m['rate']:6.3f}  [{m['ci'][0]:.3f}, {m['ci'][1]:.3f}]  {cpv}")
    for c in r["contrasts"]:
        print(f"{c['name']:24s} diff={c['diff']:+.3f} [{c['diff_ci'][0]:+.3f},{c['diff_ci'][1]:+.3f}] "
              f"p={c['p']:.3g} holm={c['p_holm']:.3g} (+{c['only_a']}/-{c['only_b']})")


if __name__ == "__main__":
    main()
