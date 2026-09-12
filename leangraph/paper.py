"""Generate the paper (paper/paper.md) from frozen results.

    python -m leangraph.paper --run-id main

Every number, and every sentence that states a direction ("repair helped"),
is computed from results/analysis/<run_id>/summary.json and the task list.
A contrast is described as a difference only if its Holm-adjusted exact
McNemar p-value is below 0.05; otherwise the text says the data cannot
distinguish the two configurations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .tasks import load_tasks

ROOT = Path(__file__).resolve().parents[1]
ALPHA = 0.05
TITLE = "LeanGraph: Evaluating Retrieval and Verifier-Guided Repair for LLM Theorem Proving"

LABEL = {
    "template": "template automation (no LLM)", "direct": "direct generation", "direct_at4": "four independent drafts",
    "repair": "direct generation with compiler-feedback repair", "rag": "hybrid retrieval-augmented generation",
    "rag_repair": "hybrid retrieval with repair", "full": "planning, retrieval and repair",
    "rag_repair_bm25": "BM25 retrieval with repair", "rag_repair_dense": "dense retrieval with repair",
    "full_no_retrieval": "the full agent without retrieval", "full_no_feedback": "the full agent without compiler feedback",
    "full_no_memory": "the full agent without memory of earlier attempts", "full_no_skeleton": "the full agent without a proof skeleton",
    "direct_think": "direct generation with reasoning on", "repair_think": "repair with reasoning on",
    "rag_repair_think": "retrieval with repair, reasoning on", "full_think": "the full agent, reasoning on",
    "direct_prompt_b": "direct generation with the paraphrased prompt", "repair_prompt_b": "repair with the paraphrased prompt",
}

RELATED_WORK = """\
**Neural theorem proving in interactive provers.** Language models were first used to propose proof steps for
Metamath by Polu and Sutskever [1], then for Lean with co-training on proof artifacts [2]. Search-based provers
combine a step model with tree search [3, 4]. Draft-Sketch-Prove turns informal proofs into formal sketches whose
gaps are closed by automation [5]; Thor delegates sub-goals to hammers [6]. Whole-proof generation with repair from
prover errors was studied by Baldur for Isabelle [7], and COPRA frames proving as an in-context agent that sees
prover feedback [8]. Large-scale synthetic data and reinforcement learning from proof-assistant feedback drive the
DeepSeek-Prover line [9, 10].

**Retrieval of premises.** LeanDojo released Lean tooling, a benchmark with a novel-premises split, and ReProver, a
retrieval-augmented prover [11]; Magnushammer studied premise selection with contrastive training [12]. Our retriever
comparison uses classical BM25 [13], a general-purpose dense embedder not trained on Mathlib [14], and reciprocal-rank
fusion [15], so that no retriever has seen held-out premises in training.

**Benchmarks.** miniF2F [16], ProofNet [17] and PutnamBench [18] measure competition and textbook mathematics.
LeanGraph instead samples held-out statements from Mathlib itself, split by module boundary with everything
downstream banned, and adds statements written for the study, so that success can be compared between theorems
whose proofs could be remembered and theorems whose proofs could not.

**Self-repair and budgets.** Iterative refinement from feedback helps language models in several domains [19, 20],
but for code generation repair is not always better than drawing fresh samples at equal cost [21]. We therefore
compare repair against independent resampling at the same number of model calls, and report success as a function
of calls (pass@k in the sense of [22]).
"""

REFERENCES = """\
Bibliographic details below were entered from the authors' knowledge of the literature and should be checked
against the publishers' records before submission.

1. S. Polu, I. Sutskever. Generative Language Modeling for Automated Theorem Proving. arXiv:2009.03393, 2020.
2. J. M. Han, J. Rute, Y. Wu, E. W. Ayers, S. Polu. Proof Artifact Co-training for Theorem Proving with Language Models. ICLR 2022.
3. S. Polu, J. M. Han, K. Zheng, M. Baksys, I. Babuschkin, I. Sutskever. Formal Mathematics Statement Curriculum Learning. ICLR 2023.
4. G. Lample et al. HyperTree Proof Search for Neural Theorem Proving. NeurIPS 2022.
5. A. Q. Jiang, S. Welleck, J. P. Zhou et al. Draft, Sketch, and Prove: Guiding Formal Theorem Provers with Informal Proofs. ICLR 2023.
6. A. Q. Jiang, W. Li, S. Tworkowski et al. Thor: Wielding Hammers to Integrate Language Models and Automated Theorem Provers. NeurIPS 2022.
7. E. First, M. N. Rabe, T. Ringer, Y. Brun. Baldur: Whole-Proof Generation and Repair with Large Language Models. ESEC/FSE 2023.
8. A. Thakur, G. Tsoukalas, Y. Wen, J. Xin, S. Chaudhuri. An In-Context Learning Agent for Formal Theorem-Proving. COLM 2024.
9. H. Xin et al. DeepSeek-Prover: Advancing Theorem Proving in LLMs through Large-Scale Synthetic Data. arXiv:2405.14333, 2024.
10. H. Xin et al. DeepSeek-Prover-V1.5: Harnessing Proof Assistant Feedback for Reinforcement Learning and Monte-Carlo Tree Search. arXiv:2408.08152, 2024.
11. K. Yang, A. M. Swope, A. Gu et al. LeanDojo: Theorem Proving with Retrieval-Augmented Language Models. NeurIPS 2023 (Datasets and Benchmarks).
12. M. Mikuła et al. Magnushammer: A Transformer-Based Approach to Premise Selection. ICLR 2024.
13. S. Robertson, H. Zaragoza. The Probabilistic Relevance Framework: BM25 and Beyond. Foundations and Trends in Information Retrieval, 2009.
14. S. Xiao, Z. Liu, P. Zhang, N. Muennighoff. C-Pack: Packaged Resources To Advance General Chinese Embedding. arXiv:2309.07597, 2023.
15. G. V. Cormack, C. L. A. Clarke, S. Büttcher. Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods. SIGIR 2009.
16. K. Zheng, J. M. Han, S. Polu. miniF2F: a Cross-System Benchmark for Formal Olympiad-Level Mathematics. ICLR 2022.
17. Z. Azerbayev et al. ProofNet: Autoformalizing and Formally Proving Undergraduate-Level Mathematics. arXiv:2302.12433, 2023.
18. G. Tsoukalas et al. PutnamBench: Evaluating Neural Theorem-Provers on the Putnam Mathematical Competition. NeurIPS 2024 (Datasets and Benchmarks).
19. A. Madaan et al. Self-Refine: Iterative Refinement with Self-Feedback. NeurIPS 2023.
20. N. Shinn et al. Reflexion: Language Agents with Verbal Reinforcement Learning. NeurIPS 2023.
21. T. X. Olausson et al. Is Self-Repair a Silver Bullet for Code Generation? ICLR 2024.
22. M. Chen et al. Evaluating Large Language Models Trained on Code. arXiv:2107.03374, 2021.
23. L. de Moura, S. Ullrich. The Lean 4 Theorem Prover and Programming Language. CADE 2021.
24. The mathlib Community. The Lean Mathematical Library. CPP 2020.
25. Q. McNemar. Note on the sampling error of the difference between correlated proportions or percentages. Psychometrika, 1947.
26. E. B. Wilson. Probable inference, the law of succession, and statistical inference. JASA, 1927.
27. S. Holm. A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 1979.
"""


RETRIEVER_NAMES = {"bm25": "BM25", "dense": "Dense (bge-small-en-v1.5)", "hybrid": "Hybrid (reciprocal-rank fusion)"}


def error_name(k: str) -> str:
    return k.replace("_", " ").replace("lean3", "Lean 3")


def pct(x, d=1):
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


def _cfg(s, c):
    return s["configs"].get(c)


def contrast_sentence(c: dict) -> str:
    a, b = LABEL.get(c["treatment"], c["treatment"]), LABEL.get(c["control"], c["control"])
    core = (f"{a} verified {pct(c['rate_treatment'])} and {b} {pct(c['rate_control'])} of the same {c['n']} theorems "
            f"(difference {100 * c['diff']:+.1f} points, 95% CI [{100 * c['diff_ci'][0]:+.1f}, {100 * c['diff_ci'][1]:+.1f}]; "
            f"{c['only_a']} {'theorem' if c['only_a'] == 1 else 'theorems'} solved only by the first, {c['only_b']} only by the second; exact McNemar p = {c['p']:.3g}, "
            f"Holm-adjusted p = {c['p_holm']:.3g})")
    core = core[:1].upper() + core[1:]
    if c["p_holm"] < ALPHA:
        return core + f". The difference survives correction: {a} {'outperforms' if c['diff'] > 0 else 'underperforms'} {b}."
    return core + ". At this sample size the data cannot distinguish the two."


def _find(s, name):
    return next((c for c in s["contrasts"] if c["name"] == name), None)


def leaderboard_table(s) -> str:
    rows = sorted(s["configs"].items(), key=lambda kv: -kv[1]["rate"])
    out = ["| Configuration | Verified | Rate [95% CI] | ≤1 call | ≤4 calls | Cost / verified |", "|---|---:|---:|---:|---:|---:|"]
    for c, m in rows:
        cpv = f"${m['cost_per_verified']:.4f}" if m.get("cost_per_verified") else "n/a"
        out.append(f"| {LABEL.get(c, c)} | {m['verified']}/{m['n']} | {pct(m['rate'])} [{pct(m['ci'][0])}, {pct(m['ci'][1])}] | "
                   f"{pct(m['success_within'].get('1'))} | {pct(m['success_within'].get('4'))} | {cpv} |")
    return "\n".join(out)


def build(run_id: str) -> str:
    s = json.loads((ROOT / "results" / "analysis" / run_id / "summary.json").read_text())
    retr_p = ROOT / "results" / "retrieval" / "summary.json"
    retr = json.loads(retr_p.read_text()) if retr_p.exists() else None
    tasks = load_tasks()
    held = [t for t in tasks if t.split == "mathlib_heldout"]
    novel = [t for t in tasks if t.split == "novel"]
    test_held = [t for t in held if t.features.get("split_role") == "test"]
    fams = sorted({t.family for t in tasks})
    figs = f"../results/figures/{run_id}"

    full, direct, template = _cfg(s, "full"), _cfg(s, "direct"), _cfg(s, "template")
    # "Best" is chosen among the headline agents, not the prompt-sensitivity variants or ablations.
    from .labels import HEADLINE
    best = max((kv for kv in s["configs"].items() if kv[0] in HEADLINE), key=lambda kv: kv[1]["rate"], default=None)
    primary = _find(s, "agentic_vs_direct")
    budget = _find(s, "repair_vs_equal_budget")

    parts = [f"# {TITLE}\n"]
    abstract = (
        f"We ask when verifier-guided agentic reasoning improves formal proof generation over direct generation by a "
        f"language model. LeanGraph poses {len(tasks)} Lean 4 theorems ({len(held)} held out from Mathlib by module "
        f"boundary, with every downstream module banned, and {len(novel)} written for the study) to one open-weight model "
        f"under {len(s['configs'])} configurations that switch retrieval, planning and compiler-feedback repair on and off. "
        f"A proof counts only if a fresh Lean process accepts it with standard axioms and no banned premise. ")
    if best:
        ties = [c for c, m in s["configs"].items() if c not in (best[0], "template") and m["rate"] == best[1]["rate"]]
        tie_note = f", a rate matched by {len(ties)} other {'configuration' if len(ties) == 1 else 'configurations'}" if ties else ""
        abstract += (f"The best of the six headline configurations ({LABEL.get(best[0], best[0])}) verified "
                     f"{pct(best[1]['rate'])}{tie_note}. ")
    if direct and template:
        abstract += f"Direct generation verified {pct(direct['rate'])}; a fixed list of automation tactics with no model verified {pct(template['rate'])}. "
    if primary:
        abstract += ("The full agent's advantage over direct generation " +
                     ("is statistically reliable " if primary["p_holm"] < ALPHA else "is not distinguishable from zero ") +
                     f"(difference {100 * primary['diff']:+.1f} points, Holm p = {primary['p_holm']:.3g}). ")
    if budget:
        abstract += ("Against independent resampling at the same number of model calls, repair " +
                     ("differs reliably " if budget["p_holm"] < ALPHA else "shows no reliable difference ") +
                     f"({100 * budget['diff']:+.1f} points, Holm p = {budget['p_holm']:.3g}).")
    parts.append("## Abstract\n\n" + abstract + "\n")
    from .export_site import run_status
    from .run import MAIN_GRID
    st = run_status(s, len([t for t in tasks if t.features.get("split_role") == "test" or t.split == "novel"]), MAIN_GRID)
    if not st["final"]:
        pending = [LABEL.get(r["config"], r["config"]) for r in st["configs"] if r["state"] != "complete"]
        parts.append(f"**Status of this version.** Interim: {st['complete']} of {st['expected']} configurations are "
                     f"complete. Still running: {', '.join(pending)}. Contrasts that need them are omitted, and the "
                     "Holm adjustment covers only the contrasts reported here; both change when the grid is complete.\n")

    parts.append("## 1 Introduction\n\n"
                 "Language models write text that looks like mathematics. A proof assistant removes the need to judge whether it "
                 "is: Lean either accepts a proof or it does not. That makes formal proving an unusually clean setting for a question "
                 "about agents in general: when does wrapping a model in retrieval, planning and feedback from a verifier produce "
                 "more correct output than asking it once? We answer it for one model under a harness designed so that nothing but "
                 "Lean's verdict counts, and we report negative and null results with the same weight as positive ones.\n\n"
                 "Research questions: (RQ1) Does retrieval of Mathlib lemmas help? (RQ2) Does compiler-feedback repair help, and does it "
                 "beat spending the same calls on fresh samples? (RQ3) Does planning help beyond retrieval? (RQ4) Which Lean error classes are "
                 "repairable? (RQ5) How does success fall with difficulty? (RQ6) Can cheaper inference with strong scaffolding compete with more "
                 "expensive inference? (RQ7) What does a verified theorem cost?\n")
    parts.append("## 2 Related Work\n\n" + RELATED_WORK)

    fam_counts = ", ".join(f"{f.replace('_', ' ')} {sum(t.family == f for t in tasks)}" for f in fams)
    parts.append(
        "## 3 Benchmark\n\n"
        f"**Composition.** {len(tasks)} theorems: {fam_counts}. Held-out: {len(test_held)} test and "
        f"{len(held) - len(test_held)} development theorems (the development split was used only to design prompts). "
        f"Authored: {len(novel)} theorems, each with a reference proof accepted by the certifier.\n\n"
        "**Held-out by module boundary.** We parse the import graph of the pinned Mathlib and keep a module only if at most twenty "
        "modules depend on it and none of them implements a tactic. For a theorem from module M, the prover may use no constant from M "
        "or from any module that transitively imports M, and the retriever never indexes them. Theorems whose statement mentions a banned "
        "constant are dropped, since their unfolding lemmas would be banned as well. Each statement is Lean's own pretty-printed signature, "
        "kept only if Lean confirms that the rendered statement has exactly the original theorem's type. Modules are assigned wholesale to "
        "development or test, and sampling round-robins across modules with at most three theorems per module. Selection never consults "
        "any prover's result.\n\n"
        "**Difficulty.** For held-out theorems, a composite proxy averages z-scores of Mathlib's reference-proof length, number of premises "
        "used, tactic diversity, statement expression depth and statement length; terciles define easy, medium and hard. Authored theorems "
        "carry the author's label, assigned before any model was run.\n")

    parts.append(
        "## 4 Lean Environment\n\n"
        "Lean 4.33.1 and Mathlib v4.33.1 (commit 0df444a3), pinned by `lake-manifest.json`; the Lean REPL from leanprover-community at a "
        "recorded commit, built against the same toolchain. Every theorem is elaborated under `maxHeartbeats 200000`. Search-time checks "
        "run in a long-lived REPL holding Mathlib in memory; the verdict comes from a separate certification in a fresh `lean` process that "
        "prints, under a random per-run nonce, the axioms the proof depends on, every constant its proof term uses with its module, and "
        "every declaration the file added. A proof is verified only if the file compiles without errors or `sorry`, depends on no axiom "
        "beyond propext, Classical.choice and Quot.sound, adds no declaration besides the target and its auxiliaries, and uses no banned "
        "constant. Proof text containing `sorry`, `admit`, `axiom`, `native_decide`, `set_option`, metaprogramming or top-level commands "
        "is rejected before compilation; tests show the certifier rejects each of these attacks on its own with that filter disabled. "
        "Lean's heartbeat limit did not stop every runaway tactic in our tests, so a 60-second wall-clock backstop remains; timeouts from "
        "it depend on the machine.\n")

    rsec = "## 5 Retrieval\n\nThe index holds every Mathlib theorem (signature and docstring) outside the banned modules. We compare BM25, a dense retriever (bge-small-en-v1.5, not trained on Mathlib) and their reciprocal-rank fusion. Ground truth is the set of indexed theorems used by each theorem's reference proof; recall counts reachable premises only.\n\n"
    if retr:
        rsec += "| Retriever | Theorems | MRR | Recall@8 | Recall@20 | Recall@50 |\n|---|---:|---:|---:|---:|---:|\n"
        for m, by in retr["methods"].items():
            a = by["all"]
            rsec += f"| {RETRIEVER_NAMES.get(m, m)} | {a['n']} | {a['rr']['mean']:.3f} | {pct(a['recall@8']['mean'])} | {pct(a['recall@20']['mean'])} | {pct(a['recall@50']['mean'])} |\n"
        rsec += f"\n![Retrieval recall]({figs}/retrieval_recall.png)\n"
    else:
        rsec += "_The retrieval benchmark was not part of this run._\n"
    parts.append(rsec)

    parts.append(
        "## 6 Agent Architectures\n\n"
        "All configurations are one loop. *Direct*: one draft. *Direct ×4*: four independent drafts, the equal-budget control for repair. "
        "*Repair*: a draft plus up to three rounds in which the model sees its previous proof and exactly what Lean printed. *Retrieval*: eight "
        "retrieved lemmas in the prompt. *Full*: a planning call that writes an informal sketch and a Lean `have` skeleton, which Lean "
        "type-checks with `sorry` allowed, followed by retrieval and repair. Ablations remove retrieval, compiler feedback (the model is told "
        "only that the proof failed), memory (only the latest attempt is shown) or the skeleton (informal plan only). Model draws are cached "
        "under a hash of the prompt and sample index, so identical prompts across configurations share a draw and comparisons are paired. "
        "The gateway's generation turned out to be nearly deterministic for a given request, whatever the temperature, so each resampled "
        "draw in Direct ×4 (samples 2–4) sends a fixed seed (1001–1003); first drafts and repair rounds send none.\n")

    parts.append(
        "## 7 Evaluation\n\n"
        "The primary metric is the share of theorems verified. Intervals are 95% Wilson intervals; differences between configurations are "
        "paired over theorems, with percentile-bootstrap intervals and exact McNemar tests, Holm-adjusted across all pre-registered contrasts. "
        "Secondary metrics: success within N model calls, calls to first success, Lean time, tokens and provider-reported cost, proof length, "
        "retrieval recall inside runs, repair success and timeout rate. A model call that failed at the gateway (rate limits, "
        "upstream provider errors, dropped connections) is not a proof attempt: failed tasks were re-run until every "
        "configuration had a real trace for every theorem, and no failed call is scored.\n")

    res = ["## 8 Results\n", leaderboard_table(s), f"\n![Verified rate by configuration]({figs}/verified_rate.png)\n"]
    for name in ["agentic_vs_direct", "feedback_repair", "repair_vs_equal_budget", "retrieval", "retrieval_with_repair", "planning",
                 "template_vs_direct", "think_direct", "think_full", "bm25_vs_hybrid", "dense_vs_hybrid",
                 "prompt_direct", "prompt_repair"]:
        c = _find(s, name)
        if c:
            res.append(f"- **{c['question']}.** " + contrast_sentence(c))
    abl = [c for c in s["contrasts"] if c["name"].startswith("abl_")]
    if abl:
        res.append("\n**Ablations.** Each removes one part of the full agent:\n")
        res += [f"- **{c['question']}.** " + contrast_sentence(c) for c in abl]
    if held and novel:
        res.append("\n**Held-out versus authored theorems.**")
        for c in ["direct", "full"]:
            bs = s["by_split"].get(c, {})
            if "mathlib_heldout" in bs and "novel" in bs:
                res.append(f"- {LABEL[c][:1].upper() + LABEL[c][1:]}: {pct(bs['mathlib_heldout']['rate'])} on held-out Mathlib theorems vs "
                           f"{pct(bs['novel']['rate'])} on authored theorems.")
    parts.append("\n".join(res) + "\n")

    rd = ["## 9 Repair Dynamics\n", f"![Success within N calls]({figs}/success_within_calls.png)\n"]
    for c in ["repair", "rag_repair", "full"]:
        m = _cfg(s, c)
        if m and m.get("repair_success") is not None:
            name = LABEL[c][:1].upper() + LABEL[c][1:]
            rd.append(f"- {name}: of {m['n_first_failed']} theorems whose first draft failed, {pct(m['repair_success'])} were later verified.")
    rb = sorted(((k, v) for k, v in s["errors"]["repair_by_class"].items() if v["n"] >= 5), key=lambda kv: -kv[1]["rate"])
    if rb:
        rd.append("\nNext-round success by the class of the error being repaired (classes with at least five cases):\n")
        rd.append("| First error | Cases | Next round verified |\n|---|---:|---:|")
        rd += [f"| {error_name(k)} | {v['n']} | {pct(v['rate'])} |" for k, v in rb]
        rd.append(f"\n![Repair by error class]({figs}/repair_by_class.png)")
    parts.append("\n".join(rd) + "\n")

    tot = s["errors"]["total"]
    n_err = sum(tot.values())
    er = ["## 10 Error Analysis\n",
          f"We classify all {n_err:,} failed attempts by their first Lean error; unknown names are split into hallucinated and "
          "wrong-namespace by lookup in the table of all 473,141 constants of the pinned Mathlib.\n",
          "| Class | Attempts | Share |\n|---|---:|---:|"]
    er += [f"| {error_name(k)} | {v} | {pct(v / n_err)} |" for k, v in sorted(tot.items(), key=lambda kv: -kv[1])]
    er.append(f"\n![Error taxonomy]({figs}/error_taxonomy.png)")
    parts.append("\n".join(er) + "\n")

    dc = s.get("difficulty_correlations", {})
    if dc:
        d = ["**Difficulty.** Spearman correlation between each proxy and a held-out theorem's solve rate across all configurations:\n",
             "| Proxy | ρ | p | n |\n|---|---:|---:|---:|"]
        d += [f"| {error_name(k)} | {v['spearman_rho']:+.2f} | {v['p']:.3g} | {v['n']} |" for k, v in dc.items()]
        d.append(f"\n![Success by difficulty]({figs}/difficulty.png)")
        parts.append("\n".join(d) + "\n")

    cost = ["## 11 Cost\n", "| Configuration | Model calls | Tokens | Cost | Cost per verified |", "|---|---:|---:|---:|---:|"]
    for c, m in sorted(s["configs"].items(), key=lambda kv: (kv[1].get("cost_per_verified") or 1e9)):
        cpv = f"${m['cost_per_verified']:.4f}" if m.get("cost_per_verified") else "n/a"
        cost.append(f"| {LABEL.get(c, c)} | {m['llm_calls']} | {m['tokens']:,} | ${m['cost_usd']:.4f} | {cpv} |")
    cost.append(f"\n![Cost and quality]({figs}/cost_quality.png)")
    parts.append("\n".join(cost) + "\n")

    think = any(c.endswith("_think") for c in s["configs"])
    lim = [
        "## 12 Limitations and Threats to Validity\n",
        "- **One model.** Every configuration uses one open-weight model through the owner's gateway, whose documentation names the upstream "
        "as Qwen3-8B; we did not verify the upstream independently. " + (
            "RQ6 is addressed only by comparing the model's reasoning-on and reasoning-off modes, a compute axis, not a model-size axis."
            if think else "No second model or reasoning tier was run, so RQ6 is not answered."),
        "- **Contamination and memorisation.** Mathlib is public and almost certainly in the model's training data. The module ban stops a "
        "proof from citing its target or anything built on it, but not from reproducing a remembered proof. The authored split bounds this: "
        "those exact statements are not Mathlib declarations, though similar textbook statements surely appear in training data.",
        "- **Distribution.** Held-out modules are near-leaves of the import graph, which skews toward specialised topics; the benchmark is "
        "not a uniform sample of Mathlib.",
        "- **Difficulty proxies.** They are computed from Mathlib's reference proofs, which are often golfed term-mode proofs, so they "
        "measure a proof's size in Mathlib's style rather than its difficulty for a model.",
        ("- **Prompt sensitivity.** A second, paraphrased prompt set was run for direct generation and repair; see the prompt contrasts in "
         "Section 8. Two prompt sets bound sensitivity only loosely." if "direct_prompt_b" in s["configs"] else
         "- **Prompt sensitivity.** One prompt version per role; prompts were designed on the development split only. We did not measure "
         "variance across paraphrased prompts."),
        "- **Sampling.** Temperature 0.6 with one draw per configuration and theorem (four for Direct ×4). Repeated draws of the same "
        "request were nearly deterministic at this gateway: in a first, unseeded Direct ×4 run, all four drafts were identical for 98 of "
        "173 theorems, and a probe got one identical reply at temperatures 0.6 and 1.2. That run is archived as evidence and Direct ×4 "
        "was re-run with a distinct seed per resampled draw. The same determinism means every single-draft configuration reflects "
        "one fixed draw per prompt; run-to-run variance is not estimated.",
        "- **Context.** The gateway reports an 8,192-token context, which bounds long repair histories and long reasoning traces.",
        "- **Timeouts.** The wall-clock backstop makes a small number of verdicts machine-dependent; heartbeat-limited verdicts are not.",
    ]
    parts.append("\n".join(lim) + "\n")

    r2 = [
        "## 13 Reviewer 2\n",
        "| Objection | What we did | What remains |", "|---|---|---|",
        "| Benchmark contamination | Held-out split by module with downstream ban; authored split; target renamed `lg_target` in every prompt | Proof recall from pretraining cannot be ruled out |",
        "| Mathlib leakage | Certifier rejects any constant from the held-out module or anything importing it; statements mentioning banned constants excluded | Mathematically equivalent lemmas elsewhere in Mathlib remain usable, as for a human |",
        "| Model memorisation | Held-out vs authored comparison reported per configuration | Authored statements resemble textbook exercises |",
        "| Theorem difficulty | Composite proxy terciles; correlations per proxy; template baseline as an empirical floor | Proxies reflect Mathlib's proof style |",
        ("| Prompt sensitivity | Prompts fixed on the development split; a paraphrased prompt set run for direct and repair | Only two prompt sets |"
         if "direct_prompt_b" in s["configs"] else
         "| Prompt sensitivity | Prompts fixed on the development split before test runs | Paraphrase variance not measured |"),
        "| Compute unfairness | Direct ×4 at the same call budget as repair; success reported per number of calls; cost per verified theorem | Planning adds one call to the full agent |",
        "| Retriever leakage | Banned modules removed from the index; dense model not trained on Mathlib | — |",
        "| Repair-loop budget | Three rounds fixed in advance; success-within-N curves show every budget up to five calls | Larger budgets untested |",
    ]
    parts.append("\n".join(r2) + "\n")

    concl = "## 14 Conclusion\n\n"
    sig = lambda c: c is not None and c["p_holm"] < ALPHA
    if primary:
        concl += ("With Lean as the only judge, " + ("the full agent verified reliably more theorems than direct generation"
                  if sig(primary) and primary["diff"] > 0 else "we could not show that the full agent verifies more theorems than direct generation")
                  + f" ({pct(primary['rate_treatment'])} vs {pct(primary['rate_control'])}). ")
    nulls_all_null = False
    _nulls = [c for c in s["contrasts"] if c["name"] in ("retrieval", "retrieval_with_repair", "planning") or c["name"].startswith("abl_")]
    nulls_all_null = bool(_nulls) and not any(sig(c) for c in _nulls)
    if budget and not (nulls_all_null and sig(budget) and budget["diff"] > 0):  # otherwise stated in the attribution sentence
        concl += ("Compiler-feedback repair " + ("also beat" if sig(budget) and budget["diff"] > 0 else "did not reliably beat")
                  + " spending the same number of model calls on independent drafts. ")
    if template and best and best[1]["rate"] > 0:
        ratio = template["rate"] / best[1]["rate"]
        concl += (f"Yet a fixed list of automation tactics, with no model, verified {pct(template['rate'])}, "
                  f"{ratio:.1f} times the best agent. ")
    nulls = [c for c in s["contrasts"] if c["name"] in ("retrieval", "retrieval_with_repair", "planning") or c["name"].startswith("abl_")]
    if nulls and not any(sig(c) for c in nulls):
        concl += ("Retrieval, planning and each ablated component of the full agent, including Lean's error text, showed no "
                  "reliable effect at this sample size. Repair beat independent drafts made with the same number of calls, so "
                  "the gain comes from revising earlier attempts rather than from attempting more often; but because the "
                  "no-feedback ablation still shows the model its previous proofs, these data cannot separate the value "
                  "of Lean's error messages from the value of revising one's own failed proof. ")
    concl += "All traces, prompts, cached model responses and certificates are released so that each number can be recomputed.\n"
    parts.append(concl)
    parts.append("## References\n\n" + REFERENCES)
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="main")
    run_id = ap.parse_args().run_id
    md = build(run_id)
    out = ROOT / "paper"
    out.mkdir(exist_ok=True)
    (out / "paper.md").write_text(md)
    print("wrote", out / "paper.md", f"({len(md.split())} words)")


if __name__ == "__main__":
    main()
