"""Turn candidates and authored theorems into the frozen task list.

Every task that enters the benchmark has passed two Lean checks:
its statement elaborates exactly as rendered, and a reference proof of it
passes `verify.certify`.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
from pathlib import Path

from .novel import NOVEL
from .verify import ReplWorker, certify

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"


def verify_novel(worker: ReplWorker, out_path: Path = CORPUS / "novel_verified.jsonl",
                 only: set[str] | None = None) -> list[dict]:
    """Check authored reference proofs in the REPL, then certify the survivors in parallel.

    With `only`, re-verify just those ids and merge into the existing file.
    """
    existing: dict[str, dict] = {}
    if only is not None and out_path.exists():
        existing = {r["id"]: r for r in map(json.loads, out_path.read_text().splitlines())}
    rows = []
    for t in NOVEL:
        if only is not None and t["id"] not in only:
            continue
        r = worker.check(t["statement"], t["proof"], t.get("opens", ""))
        rows.append({**t, "repl_ok": r.ok, "repl_output": r.compiler_output()[:600]})
    todo = [row for row in rows if row["repl_ok"]]
    with cf.ThreadPoolExecutor(2) as ex:
        certs = list(ex.map(lambda row: certify(row["statement"], row["proof"], row.get("opens", "")), todo))
    for row, c in zip(todo, certs):
        row.update(certified=c.verified, cert_reason=c.reason, axioms=c.axioms, used_constants=c.used_constants)
    merged = {**existing, **{r["id"]: r for r in rows}}
    ordered = [merged[t["id"]] for t in NOVEL if t["id"] in merged]
    out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ordered))
    return ordered


def stale_novel(path: Path = CORPUS / "novel_verified.jsonl") -> set[str]:
    """Authored theorems never verified, not certified, or edited since verification."""
    done = {r["id"]: r for r in map(json.loads, path.read_text().splitlines())} if path.exists() else {}
    return {t["id"] for t in NOVEL
            if t["id"] not in done or not done[t["id"]].get("certified")
            or done[t["id"]].get("statement") != t["statement"] or done[t["id"]].get("proof") != t["proof"]
            or done[t["id"]].get("opens", "") != t.get("opens", "")}


# ---------------------------------------------------------------- held-out split

TACTIC_VOCAB = frozenset("""
simp simp_all simpa simp_rw dsimp rw rwa nth_rewrite erw exact exact_mod_cast apply refine refine' intro intros
rintro rcases obtain cases induction constructor use exists left right linarith nlinarith norm_num ring ring_nf
field_simp omega positivity aesop tauto decide have calc gcongr ext funext congr by_contra push_neg contrapose
specialize unfold split split_ifs interval_cases fin_cases subst rfl trivial push_cast norm_cast filter_upwards
measurability continuity fun_prop infer_instance show change conv symm trans grind bound by_cases absurd exfalso
contradiction assumption apply_fun lift zify qify set let suffices wlog choose convert mono polyrith
linear_combination haveI letI exacts all_goals any_goals first repeat iterate refine_lift peel
""".split())


def _source_lines(module: str) -> list[str]:
    from .corpus import module_path
    return module_path(module).read_text(errors="ignore").splitlines()


def reference_features(module: str, start: int, end: int, cache: dict) -> dict:
    """Proof-size proxies from the theorem's own source range in Mathlib."""
    if module not in cache:
        cache[module] = _source_lines(module)
    text = "\n".join(cache[module][max(0, start - 1):end])
    body = text.split(":=", 1)[1] if ":=" in text else text
    lines = [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    words = [w for w in __import__("re").findall(r"[A-Za-z_][A-Za-z0-9_']*", body)]
    tactics = [w for w in words if w in TACTIC_VOCAB]
    return {"ref_proof_lines": max(1, len(lines)), "ref_proof_chars": len(body.strip()),
            "ref_tactic_count": len(tactics), "ref_tactic_diversity": len(set(tactics)),
            "ref_term_mode": "by" not in __import__("re").findall(r"\bby\b", body[:40]) and not tactics,
            "reference_source": text}


def _count_binder_groups(binders: str) -> int:
    depth, groups = 0, 0
    for ch in binders:
        if ch in "([{⦃":
            if depth == 0:
                groups += 1
            depth += 1
        elif ch in ")]}⦄":
            depth -= 1
    return groups


def prefilter_heldout() -> tuple[list[dict], dict]:
    """Drop candidates that cannot be fair tasks; attach ground-truth premises and features."""
    cands = [json.loads(l) for l in (CORPUS / "candidates.jsonl").read_text().splitlines()]
    meta = {m["name"]: m for m in map(json.loads, (CORPUS / "candidates_meta.jsonl").read_text().splitlines())}
    premise_names = set()
    with (CORPUS / "premises.jsonl").open() as f:
        for ln in f:
            premise_names.add(json.loads(ln)["name"])
    kept, reasons, src_cache = [], {}, {}
    for c in cands:
        m = meta.get(c["name"])
        banned = set(c["banned_modules"])
        why = None
        if m is None or m.get("missing"):
            why = "missing_in_env"
        elif not m["has_value"]:
            why = "no_proof_term"
        elif {mod for _, mod in m["type_consts"]} & banned:
            why = "statement_uses_heldout_constant"
        if why:
            reasons[why] = reasons.get(why, 0) + 1
            continue
        proof_premises = [(n, mod) for n, mod in m["proof_consts"] if n in premise_names and n != c["name"]]
        feats = reference_features(c["module"], m["start_line"], m["end_line"], src_cache)
        feats.update({
            "statement_chars": len(c["statement"]),
            "binder_groups": _count_binder_groups(c["binders"]),
            "type_depth": m["type_depth"],
            "gt_premises_reachable": sum(1 for _, mod in proof_premises if mod not in banned),
            "gt_premises_heldout": sum(1 for _, mod in proof_premises if mod in banned),
        })
        kept.append({**c, "gt_premises": [n for n, mod in proof_premises if mod not in banned],
                     "gt_premises_heldout": [n for n, mod in proof_premises if mod in banned],
                     "features": feats})
    return kept, reasons


def roundtrip_heldout(worker: ReplWorker, kept: list[dict]) -> list[dict]:
    """Keep candidates whose rendered statement is, to Lean, the original theorem's type."""
    from .corpus import roundtrip_command
    ok = []
    for c in kept:
        resp = worker.run_command(roundtrip_command(c["binders"], c["type"], c["name"]))
        errs = [m for m in (resp or {}).get("messages", []) if m.get("severity") == "error"]
        c["roundtrip_ok"] = resp is not None and not errs
        c["roundtrip_error"] = errs[0]["data"][:300] if errs else (None if resp else "timeout")
        if c["roundtrip_ok"]:
            ok.append(c)
    return ok


def select_heldout(pool: list[dict], test_per_family: int = 20, dev_per_family: int = 5,
                   max_per_module: int = 3, seed: int = 20260910) -> list[dict]:
    """Balanced sample: per family and split, round-robin over modules so none dominates.

    Selection never looks at whether any prover (including the template
    baseline) can solve a task, so it cannot bias results toward easy tasks.
    """
    import random
    from collections import defaultdict
    from .corpus import FAMILIES

    rng = random.Random(seed)
    out = []
    for fam, _ in FAMILIES:
        for split, quota in (("test", test_per_family), ("dev", dev_per_family)):
            by_mod: dict[str, list[dict]] = defaultdict(list)
            for c in pool:
                if c["family"] == fam and c["split_role"] == split:
                    by_mod[c["module"]].append(c)
            for lst in by_mod.values():
                lst.sort(key=lambda c: c["name"])
                rng.shuffle(lst)
            mods = sorted(by_mod)
            rng.shuffle(mods)
            chosen: list[dict] = []
            for r in range(max_per_module):
                for m in mods:
                    if len(chosen) < quota and r < len(by_mod[m]):
                        chosen.append(by_mod[m][r])
            out.extend(chosen)
    return out


# ---------------------------------------------------------------- assemble tasks.jsonl

HELDOUT_TEST_PER_FAMILY = 20
HELDOUT_DEV_PER_FAMILY = 5
FINAL_MAX_PER_MODULE = 3


def _task_id(prefix: str, family: str, key: str) -> str:
    import hashlib
    return f"{prefix}_{family[:4]}_{hashlib.sha1(key.encode()).hexdigest()[:6]}"


def _difficulty_terciles(rows: list[dict]) -> None:
    """Composite proxy: mean z-score of five size measures; split into terciles."""
    import math
    import statistics as st

    keys = {
        "ref_proof_lines": lambda f: math.log1p(f["ref_proof_lines"]),
        "premises": lambda f: math.log1p(f["gt_premises_reachable"] + f["gt_premises_heldout"]),
        "ref_tactic_diversity": lambda f: f["ref_tactic_diversity"],
        "type_depth": lambda f: f["type_depth"],
        "statement_chars": lambda f: math.log1p(f["statement_chars"]),
    }
    cols = {k: [fn(r["features"]) for r in rows] for k, fn in keys.items()}
    stats = {k: (st.mean(v), st.pstdev(v) or 1.0) for k, v in cols.items()}
    for i, r in enumerate(rows):
        r["features"]["difficulty_score"] = st.mean((cols[k][i] - m) / s for k, (m, s) in stats.items())
    ordered = sorted(r["features"]["difficulty_score"] for r in rows)
    lo, hi = ordered[len(ordered) // 3], ordered[2 * len(ordered) // 3]
    for r in rows:
        s = r["features"]["difficulty_score"]
        r["difficulty"] = "easy" if s < lo else ("medium" if s < hi else "hard")


def assemble_tasks(worker: ReplWorker) -> list:
    from collections import Counter, defaultdict
    from .tasks import Task, save_tasks

    kept, reasons = prefilter_heldout()
    (CORPUS / "prefilter_report.json").write_text(json.dumps({"dropped": reasons, "kept": len(kept)}, indent=1))
    ordered = select_heldout(kept, test_per_family=4 * HELDOUT_TEST_PER_FAMILY,
                             dev_per_family=4 * HELDOUT_DEV_PER_FAMILY, max_per_module=8)
    quota = {"test": HELDOUT_TEST_PER_FAMILY, "dev": HELDOUT_DEV_PER_FAMILY}
    taken: dict[tuple, int] = defaultdict(int)
    per_module: Counter = Counter()
    chosen, rt_fail = [], 0
    for c in ordered:
        g = (c["family"], c["split_role"])
        if taken[g] >= quota[c["split_role"]] or per_module[c["module"]] >= FINAL_MAX_PER_MODULE:
            continue
        if not roundtrip_heldout(worker, [c]):
            rt_fail += 1
            continue
        taken[g] += 1
        per_module[c["module"]] += 1
        chosen.append(c)
    _difficulty_terciles(chosen)

    tasks = []
    for c in chosen:
        f = {k: v for k, v in c["features"].items() if k != "reference_source"}
        f.update(split_role=c["split_role"], downstream=c["downstream"], gt_premises_heldout=c["gt_premises_heldout"])
        tasks.append(Task(
            id=_task_id("mh", c["family"], c["name"]), statement=c["statement"], family=c["family"],
            difficulty=c["difficulty"], split="mathlib_heldout", source=c["name"], module=c["module"],
            reference_proof=c["features"]["reference_source"], banned_modules=frozenset(c["banned_modules"]),
            gt_premises=tuple(c["gt_premises"]), features=f))

    premise_names = set()
    with (CORPUS / "premises.jsonl").open() as fh:
        for ln in fh:
            premise_names.add(json.loads(ln)["name"])
    novel_rows = [json.loads(l) for l in (CORPUS / "novel_verified.jsonl").read_text().splitlines()]
    for r in novel_rows:
        if not r.get("certified"):
            continue
        used = [n for n, _ in r["used_constants"] if n in premise_names]
        lines = [ln for ln in r["proof"].splitlines() if ln.strip()]
        tactics = [w for w in __import__("re").findall(r"[A-Za-z_][A-Za-z0-9_']*", r["proof"]) if w in TACTIC_VOCAB]
        tasks.append(Task(
            id=r["id"], statement=r["statement"], opens=r.get("opens", ""), family=r["family"],
            difficulty=r["difficulty"], split="novel", source="authored", reference_proof=r["proof"],
            gt_premises=tuple(dict.fromkeys(used)),
            features={"split_role": "test", "ref_proof_lines": len(lines), "ref_tactic_count": len(tactics),
                      "ref_tactic_diversity": len(set(tactics)), "statement_chars": len(r["statement"]),
                      "gt_premises_reachable": len(set(used)), "axioms": r["axioms"]}))
    save_tasks(tasks)
    summary = {
        "roundtrip_failures_skipped": rt_fail,
        "counts": Counter(f"{t.split}/{t.features.get('split_role')}/{t.family}" for t in tasks),
        "difficulty": Counter(f"{t.split}/{t.difficulty}" for t in tasks),
        "novel_certified": sum(1 for r in novel_rows if r.get("certified")), "novel_authored": len(novel_rows),
    }
    (CORPUS / "tasks_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=dict))
    return tasks


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else ""
    if cmd not in ("novel", "tasks"):
        raise SystemExit("usage: python -m leangraph.build novel|tasks")
    w = ReplWorker()
    w.start()
    try:
        if cmd == "novel":
            rows = verify_novel(w)
        else:
            redo = stale_novel()
            if redo:
                print("re-verifying authored theorems:", sorted(redo), flush=True)
                verify_novel(w, only=redo)
            assemble_tasks(w)
    finally:
        w.close()
    nv = [json.loads(l) for l in (CORPUS / "novel_verified.jsonl").read_text().splitlines()]
    if cmd == "tasks":
        print(json.loads((CORPUS / "tasks_summary.json").read_text()))
    print("authored certified:", sum(bool(r.get("certified")) for r in nv), "/", len(nv),
          "| not certified:", [(r["id"], r.get("cert_reason") or r.get("repl_output", "")[:120]) for r in nv if not r.get("certified")])


if __name__ == "__main__":
    main(sys.argv[1:])
