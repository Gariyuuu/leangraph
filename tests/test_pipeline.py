"""The downstream pipeline on a synthetic run, in a temp directory: analyze -> figures -> paper -> export.

No Lean, no API, and nothing is written under results/: every module's paths are redirected.
"""
import json

import pytest

from leangraph import analyze, export_site, figures, paper
from leangraph import tasks as tasks_mod
from leangraph.tasks import Task, save_tasks

N = 9
CFG_ROUNDS = {"template": 0, "direct": 0, "repair": 3, "full": 3}
# task index -> LLM calls needed to solve (None = never solved)
SOLVE = {
    "template": {0: 0},
    "direct": {0: 1, 1: 1},
    "repair": {0: 1, 1: 1, 2: 2, 3: 2},
    "full": {0: 2, 1: 2, 2: 3, 3: 3, 4: 3},
}
FAIL_MSG = ["unsolved goals\n⊢ False", "Unknown constant `Totally.madeUp_lemma`", "linarith failed to find a contradiction"]


def _attempt(ok: bool, rnd: int, i: int) -> dict:
    return {"sample": 0, "round": rnd, "proof": "simp" if ok else f"bad {i} {rnd}", "latency_s": 1.0, "lean_s": 0.05,
            "completion_tokens": 10, "timed_out": False, "compiler_output": "" if ok else FAIL_MSG[(i + rnd) % 3],
            "messages": [] if ok else [{"severity": "error", "line": 1, "col": 1, "text": FAIL_MSG[(i + rnd) % 3]}],
            "certificate": {"verified": True, "reason": "ok", "axioms": ["propext"]} if ok else None}


def _trace(cfg: str, i: int) -> dict:
    need = SOLVE[cfg].get(i)
    plan = cfg == "full"
    if cfg == "template":
        atts = [_attempt(need is not None, 0, i)]
        calls = 0
    else:
        n_prove = (need - int(plan)) if need is not None else 1 + CFG_ROUNDS[cfg]
        atts = [_attempt(need is not None and r == n_prove - 1, r, i) for r in range(n_prove)]
        calls = n_prove + int(plan)
    tr = {"task_id": f"t{i}", "config": {"name": cfg, "rounds": CFG_ROUNDS[cfg]}, "verified": need is not None,
          "final_proof": "simp" if need is not None else None, "attempts": atts, "retrieved": ["A.b", "C.d"] if cfg == "full" else [],
          "certificate": {"verified": True, "reason": "ok", "axioms": ["propext"]} if need is not None else None,
          "usage": {"llm_calls": calls, "prompt_tokens": 100 * calls, "completion_tokens": 10 * calls,
                    "cost_usd": 0.0001 * calls, "lean_check_s": 0.1, "certify_s": 30.0 if need is not None else 0.0}}
    if need is not None and cfg != "template":
        tr["solved_at"] = {"sample": 0, "round": len(atts) - 1, "llm_calls": calls}
    return tr


@pytest.fixture
def repo(tmp_path, monkeypatch):
    ts = [Task(id=f"t{i}", statement="(a : ℕ) : a = a", family=["algebra", "sets"][i % 2], difficulty=["easy", "medium", "hard"][i % 3],
               split="mathlib_heldout" if i < 6 else "novel", source=f"M.thm{i}", gt_premises=("A.b",),
               features={"split_role": "test", "ref_proof_lines": i + 1, "ref_tactic_diversity": i % 3, "gt_premises_reachable": i,
                         "type_depth": 5 + i, "statement_chars": 20 + i, "difficulty_score": i / 10, "binder_groups": 1})
          for i in range(N)]
    tpath = tmp_path / "corpus" / "tasks.jsonl"
    save_tasks(ts, tpath)
    monkeypatch.setattr(tasks_mod, "TASKS_PATH", tpath)
    runs = tmp_path / "results" / "runs" / "syn"
    runs.mkdir(parents=True)
    for cfg in SOLVE:
        (runs / f"{cfg}.jsonl").write_text("".join(json.dumps(_trace(cfg, i)) + "\n" for i in range(N)))
    monkeypatch.setattr(analyze, "RUNS", tmp_path / "results" / "runs")
    monkeypatch.setattr(analyze, "OUT", tmp_path / "results" / "analysis")
    monkeypatch.setattr(paper, "ROOT", tmp_path)
    monkeypatch.setattr(export_site, "ROOT", tmp_path)
    monkeypatch.setattr(export_site, "SITE_DATA", tmp_path / "site" / "data")
    monkeypatch.setattr(export_site, "SITE_PUBLIC", tmp_path / "site_public")  # never the real site/public
    monkeypatch.setattr(export_site, "ENV_DOC", tmp_path / "docs" / "ENVIRONMENT.md")
    return tmp_path


def test_analyze_metrics_match_the_traces(repo):
    s = analyze.analyze("syn")
    c = s["configs"]
    assert {k: c[k]["verified"] for k in SOLVE} == {"template": 1, "direct": 2, "repair": 4, "full": 5}
    assert c["repair"]["repair_success"] == pytest.approx(2 / 7)  # t2, t3 of the 7 whose first draft failed
    assert c["direct"]["repair_success"] is None and c["template"]["repair_success"] is None
    assert c["repair"]["success_within"][1] == pytest.approx(2 / 9) and c["repair"]["success_within"][2] == pytest.approx(4 / 9)
    for m in c.values():
        sw = [m["success_within"][k] for k in sorted(m["success_within"])]
        assert sw == sorted(sw)
        assert 0 <= m["ci"][0] <= m["rate"] <= m["ci"][1] <= 1
    assert c["full"]["median_calls_to_solve"] == 3
    assert c["repair"]["median_lean_check_s"] == pytest.approx(0.05)
    assert c["repair"]["repeat_rate"] == 0.0 and c["direct"]["repeat_rate"] is None  # synthetic proofs never repeat


def test_contrasts_are_paired_and_corrected(repo):
    s = analyze.analyze("syn")
    by = {x["name"]: x for x in s["contrasts"]}
    fr = by["feedback_repair"]
    assert (fr["only_a"], fr["only_b"], fr["n"]) == (2, 0, N)
    for x in s["contrasts"]:
        assert 0 <= x["p"] <= x["p_holm"] <= 1


def test_error_taxonomy_counts_every_failed_attempt(repo):
    s = analyze.analyze("syn")
    n_failed = sum(1 for cfg in SOLVE for i in range(N) for a in _trace(cfg, i)["attempts"] if a["certificate"] is None)
    assert sum(s["errors"]["total"].values()) == n_failed
    assert set(s["errors"]["total"]) <= {"valid_but_wrong", "hallucinated_theorem", "wrong_tactic"}


def test_figures_paper_and_export(repo):
    s = analyze.analyze("syn")
    out = repo / "figs"
    for fn in (figures.fig_verified_rate, figures.fig_success_within, figures.fig_errors, figures.fig_repair_by_class,
               figures.fig_cost_quality, figures.fig_difficulty):
        fn(s, out)
    for name in ["verified_rate", "success_within_calls", "error_taxonomy", "cost_quality", "difficulty"]:
        assert (out / f"{name}.png").exists() and (out / f"{name}.csv").exists()
    md = paper.build("syn")
    assert paper.TITLE in md and "nan" not in md.lower()
    assert "cannot distinguish" in md  # nine theorems cannot support a significant claim
    data = export_site.export("syn")
    rows = json.loads((data / "theorems.json").read_text())
    assert len(rows) == N and set(rows[0]["solved_by"]) == {"template", "direct", "repair", "full"}
    detail = json.loads((data / "theorem" / "t8.json").read_text())
    assert detail["runs"]["repair"]["attempts"][0]["error_class"] in {"valid_but_wrong", "hallucinated_theorem", "wrong_tactic"}


def test_contrast_sentence_only_claims_a_difference_when_significant():
    base = dict(treatment="repair", control="direct", n=100, rate_treatment=0.4, rate_control=0.2, diff=0.2,
                diff_ci=[0.1, 0.3], only_a=20, only_b=0, p=0.0001)
    assert "survives correction" in paper.contrast_sentence({**base, "p_holm": 0.001})
    assert "cannot distinguish" in paper.contrast_sentence({**base, "p_holm": 0.2})


def test_freeze_detects_any_change(repo, monkeypatch):
    from leangraph import freeze
    monkeypatch.setattr(freeze, "ROOT", repo)
    analyze.analyze("syn")
    freeze.freeze("syn")
    assert freeze.check("syn") == []
    trace = repo / "results" / "runs" / "syn" / "direct.jsonl"
    trace.write_text(trace.read_text().replace('"verified": false', '"verified": true', 1))
    assert any("direct.jsonl" in p for p in freeze.check("syn"))


def test_repeat_rate_counts_identical_resubmissions(repo):
    runs = repo / "results" / "runs" / "syn"
    tr = _trace("repair", 8)  # never solved: rounds 0..3
    for a in tr["attempts"][2:]:
        a["proof"] = tr["attempts"][1]["proof"]  # rounds 2 and 3 resubmit round 1
    (runs / "repair.jsonl").write_text("".join(json.dumps(_trace("repair", i) if i != 8 else tr) + "\n" for i in range(N)))
    m = analyze.analyze("syn")["configs"]["repair"]
    assert m["repeat_rate"] == pytest.approx(2 / m["n_repair_attempts"])


def test_harness_errors_are_retried_excluded_and_block_freezing(repo, monkeypatch):
    from leangraph import freeze, run
    runs = repo / "results" / "runs" / "syn"
    out = runs / "direct.jsonl"
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    rows[8] = {"task_id": "t8", "config": {"name": "direct"}, "error": "RuntimeError('HTTP 530')", "verified": False}
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    # analysis: the errored task leaves the denominator and is reported
    s = analyze.analyze("syn")
    assert "direct" not in s["configs"]  # incomplete: reported nowhere but configs_partial
    assert s["configs_partial"]["direct"] == {"n": N - 1, "harness_errors_unresolved": 1}
    assert all("direct" not in (c["treatment"], c["control"]) for c in s["contrasts"])
    # freezing refuses while the task has no real trace
    monkeypatch.setattr(freeze, "ROOT", repo)
    with pytest.raises(SystemExit):
        freeze.freeze("syn")
    # resume: the errored row moves to the sidecar and the task is no longer "done"
    done = run.completed_task_ids(out)
    assert "t8" not in done and len(done) == N - 1
    assert run.harness_error_path(out).exists() and "t8" in run.harness_error_path(out).read_text()
    assert all(not json.loads(l).get("error") for l in out.read_text().splitlines())
    # once the task has a real trace again, the sidecar row no longer counts
    with out.open("a") as fh:
        fh.write(json.dumps(_trace("direct", 8)) + "\n")
    assert analyze.analyze("syn")["configs"]["direct"]["harness_errors_unresolved"] == 0


def test_pilot_compare_uses_common_tasks_only(repo):
    from leangraph import pilot_compare
    other = repo / "results" / "runs" / "syn2"
    other.mkdir()
    rows = [_trace("repair", i) for i in range(N - 2)]  # two tasks missing in the second run
    (other / "direct.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = pilot_compare.compare("syn", "syn2", "direct")
    assert out["common_tasks"] == N - 2
    assert out["syn"]["verified"] == 2 and out["syn2"]["verified"] == 4
    assert set(out["solved_only_by"]["syn2"]) == {"t2", "t3"} and out["solved_only_by"]["syn"] == []


def test_readme_results_block_is_idempotent(repo, monkeypatch):
    from leangraph import readme_results
    analyze.analyze("syn")
    monkeypatch.setattr(readme_results, "ROOT", repo)
    (repo / "README.md").write_text("# X\n\n## Layout\n\nstuff\n")
    import sys
    monkeypatch.setattr(sys, "argv", ["x", "--run-id", "syn"])
    readme_results.main(); first = (repo / "README.md").read_text()
    readme_results.main(); second = (repo / "README.md").read_text()
    assert first == second and first.count(readme_results.START) == 1 and "## Layout" in first
    assert "| Direct |" in first


def test_error_bars_never_negative_for_zero_successes():
    from leangraph.figures import nonneg_err
    from leangraph.stats import wilson
    lo, hi = wilson(0, 7)
    errs = nonneg_err([[0.0 - lo], [hi - 0.0]])
    assert (errs >= 0).all() and nonneg_err(None) is None


def test_every_configuration_has_a_display_name():
    from leangraph.labels import CONFIG_LABELS
    from leangraph.run import CONFIGS
    assert set(CONFIGS) <= set(CONFIG_LABELS), set(CONFIGS) - set(CONFIG_LABELS)


def test_site_config_labels_match_python():
    import re
    from leangraph.labels import CONFIG_LABELS
    import pathlib
    ts = (pathlib.Path(__file__).resolve().parents[1] / "site" / "lib" / "labels.ts").read_text()
    block = ts[ts.index("export const CONFIG_LABELS"):]
    block = block[:block.index("};")]
    site = dict(re.findall(r'^\s*(\w+): "([^"]*)",', block, re.M))
    assert {k: site.get(k) for k in CONFIG_LABELS} == CONFIG_LABELS


def test_run_status_marks_complete_partial_and_missing():
    from leangraph.export_site import run_status
    summary = {"configs": {"a": {"n": 10}, "b": {"n": 4}}}
    st = run_status(summary, 10, ("a", "b", "c"))
    assert [r["state"] for r in st["configs"]] == ["complete", "partial", "not started"]
    assert st["complete"] == 1 and st["expected"] == 3 and not st["final"]
    assert run_status({"configs": {"a": {"n": 10}}}, 10, ("a",))["final"]


def test_site_export_ignores_harness_error_sidecars(repo, monkeypatch):
    from leangraph import export_site
    runs = repo / "results" / "runs" / "syn"
    (runs / "direct.harness_errors.jsonl").write_text(json.dumps({"task_id": "t0", "error": "HTTP 530", "verified": False}) + "\n")
    monkeypatch.setattr(export_site, "SITE_DATA", repo / "site_data")
    export_site.export("syn")
    detail = json.loads((repo / "site_data" / "theorem" / "t0.json").read_text())
    assert not any("harness_errors" in c for c in detail["runs"]), list(detail["runs"])


def test_site_headline_configs_match_python():
    import pathlib, re
    from leangraph.labels import HEADLINE
    ts = (pathlib.Path(__file__).resolve().parents[1] / "site" / "lib" / "labels.ts").read_text()
    m = re.search(r"HEADLINE_CONFIGS: string\[\] = \[(.*?)\];", ts)
    assert m and tuple(re.findall(r'"(\w+)"', m.group(1))) == tuple(HEADLINE)


def test_site_paper_figure_links_point_at_copied_figures(repo, monkeypatch):
    from leangraph import export_site
    figs = repo / "results" / "figures" / "syn"
    figs.mkdir(parents=True, exist_ok=True)
    (figs / "verified_rate.png").write_bytes(b"png")
    paper = repo / "paper"; paper.mkdir(exist_ok=True)
    (paper / "paper.md").write_text("![Verified](../results/figures/syn/verified_rate.png)\n")
    monkeypatch.setattr(export_site, "SITE_DATA", repo / "site_data")
    monkeypatch.setattr(export_site, "SITE_PUBLIC", repo / "site_public")
    export_site.export("syn")
    site_paper = repo / "site_data" / "paper.md"
    if site_paper.exists():  # only when the exporter copies the paper
        text = site_paper.read_text()
        assert "../results/figures" not in text and "/figures/verified_rate.png" in text
    assert (repo / "site_public" / "figures" / "verified_rate.png").exists()


def test_partial_configuration_feeds_no_metric_or_contrast(repo):
    runs = repo / "results" / "runs" / "syn"
    rows = []
    for i in range(N // 2):  # a half-finished configuration, shaped like repair traces
        tr = _trace("repair", i)
        tr["config"] = {**tr["config"], "name": "rag"}
        rows.append(tr)
    (runs / "rag.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    s = analyze.analyze("syn")
    assert "rag" not in s["configs"] and s["configs_partial"]["rag"]["n"] == N // 2
    assert all("rag" not in (c["treatment"], c["control"]) for c in s["contrasts"])
    assert s["n_tasks"] == N
    from leangraph.export_site import run_status
    st = run_status(s, N, ("direct", "rag"))
    assert [r["state"] for r in st["configs"]] == ["complete", "partial"]


def test_readme_block_marks_interim_runs():
    from leangraph.readme_results import render
    summary = {"n_tasks": 5, "configs": {"direct": {"n": 5, "verified": 1, "rate": 0.2, "ci": [0.0, 0.6],
               "cost_per_verified": 0.01}}, "configs_partial": {"full": {"n": 2}}, "contrasts": []}
    text = render(summary, "x")
    assert "**Interim:**" in text and "(2/5)" in text
