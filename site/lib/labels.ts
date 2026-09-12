export const CONFIG_LABELS: Record<string, string> = {
  // Generated from leangraph/labels.py (tests/test_pipeline.py fails if these drift).
  template: "Template (no LLM)",
  direct: "Direct",
  direct_at4: "Direct ×4",
  repair: "Repair",
  rag: "Hybrid retrieval",
  rag_repair: "Hybrid retrieval + repair",
  full: "Full (plan + retrieval + repair)",
  rag_repair_bm25: "BM25 retrieval + repair",
  rag_repair_dense: "Dense retrieval + repair",
  full_no_retrieval: "Full − retrieval",
  full_no_feedback: "Full − compiler feedback",
  full_no_memory: "Full − memory",
  full_no_skeleton: "Full − skeleton",
  direct_prompt_b: "Direct (paraphrased prompt)",
  repair_prompt_b: "Repair (paraphrased prompt)",
  direct_think: "Direct (reasoning on)",
  repair_think: "Repair (reasoning on)",
  rag_repair_think: "Retrieval + repair (reasoning on)",
  full_think: "Full (reasoning on)",
  demo_rag_repair_bm25: "Demo: BM25 retrieval + repair",
};
export const configLabel = (c: string) => CONFIG_LABELS[c] ?? c;

export const CONFIG_DESCRIPTIONS: Record<string, string> = {
  template: "A fixed list of automation tactics (simp, omega, linarith, nlinarith, positivity, aesop, grind, exact?, …) tried in order. No model.",
  direct: "One model draft, checked once.",
  direct_at4: "Four drafts: the Direct draft plus three resampled with fixed seeds (unseeded repeats were near-identical at this gateway). The equal-budget control for repair: same number of model calls, no feedback.",
  repair: "One draft, then up to three rounds in which the model sees Lean's exact error output.",
  rag: "One draft with eight lemmas retrieved from Mathlib (hybrid retriever) in the prompt.",
  rag_repair: "Retrieval plus up to three compiler-feedback repair rounds.",
  full: "A planning call (informal sketch plus a Lean `have` skeleton that Lean type-checks), then retrieval plus repair.",
  rag_repair_bm25: "Retrieval + repair, with BM25 retrieval only.",
  rag_repair_dense: "Retrieval + repair, with dense retrieval only.",
  full_no_retrieval: "The full agent without retrieved lemmas.",
  full_no_feedback: "The full agent, but a failed round only says the proof failed; Lean's output is withheld.",
  full_no_memory: "The full agent, but each repair round shows only the latest attempt.",
  full_no_skeleton: "The full agent with an informal plan only, no Lean skeleton.",
  direct_prompt_b: "Direct with a paraphrased prompt (prompt-sensitivity check).",
  repair_prompt_b: "Repair with a paraphrased prompt (prompt-sensitivity check).",
};

export const ERROR_CLASSES: Record<string, { label: string; rule: string }> = {
  hallucinated_theorem: { label: "Hallucinated theorem", rule: "Lean reports an unknown name, and no constant with that name exists in the pinned Mathlib under any namespace or capitalisation." },
  wrong_namespace: { label: "Wrong namespace", rule: "Unknown name, but a constant with the same name exists under another namespace or capitalisation — often a Lean 3 name such as `real.sqrt` for `Real.sqrt`." },
  lean3_syntax: { label: "Lean 3 syntax", rule: "A parse error in a proof written with Lean 3 constructs (`begin … end`, `assume`, `λ x, …`, `cases h with …`)." },
  syntax_error: { label: "Syntax error", rule: "Any other parse error." },
  type_mismatch: { label: "Type mismatch", rule: "A term's type differs from the one expected." },
  unresolved_metavariable: { label: "Unresolved metavariable", rule: "Lean cannot fill a placeholder or implicit argument." },
  instance_resolution_failure: { label: "Instance resolution failure", rule: "Type-class synthesis failed (`failed to synthesize …`)." },
  incorrect_rewrite: { label: "Incorrect rewrite", rule: "`rw` found no instance of the pattern, or the motive was not type-correct." },
  bad_induction: { label: "Bad induction", rule: "Invalid or missing induction/cases alternatives, or induction on a non-inductive target." },
  wrong_tactic: { label: "Wrong tactic", rule: "An automation or closing tactic ran and failed on this goal (linarith, omega, simp made no progress, …)." },
  valid_but_wrong: { label: "Valid but mathematically wrong", rule: "The proof elaborates, but goals remain unsolved: well-formed Lean that does not prove the statement." },
  timeout: { label: "Timeout", rule: "Heartbeat or recursion limit, or the 60-second wall-clock backstop." },
  forbidden: { label: "Forbidden token", rule: "Rejected before compilation: `sorry`, `admit`, axioms, `native_decide`, `set_option`, metaprogramming or top-level commands." },
  no_proof: { label: "No proof", rule: "The model's reply contained no tactic block." },
  checker_rejected: { label: "Rejected by certifier", rule: "Passed the fast REPL check but the independent certifier rejected it: a banned premise, extra declarations, or non-standard axioms." },
  other: { label: "Other", rule: "Any Lean error the rules above do not match." },
};
export const errorLabel = (c: string) => ERROR_CLASSES[c]?.label ?? c;

export const FAMILY_LABELS: Record<string, string> = {
  algebra: "Algebra", inequalities: "Inequalities", sets: "Sets", functions: "Functions",
  number_theory: "Number theory", probability: "Probability", category_theory: "Category theory",
};
export const SPLIT_LABELS: Record<string, string> = { mathlib_heldout: "Mathlib held-out", novel: "Authored" };

// Headline agent configurations (mirrors HEADLINE in leangraph/labels.py; tests check they match).
export const HEADLINE_CONFIGS: string[] = ["direct", "direct_at4", "repair", "rag", "rag_repair", "full"];
