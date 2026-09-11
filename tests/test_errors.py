from leangraph import errors


def test_classes_from_real_lean_message_shapes(monkeypatch):
    monkeypatch.setattr(errors, "_name_tables", lambda: (frozenset({"Real.sqrt", "sq_nonneg"}),
                        {"real.sqrt": ["Real.sqrt"], "sq_nonneg": ["sq_nonneg"]},
                        {"sqrt": ["Real.sqrt"], "sq_nonneg": ["sq_nonneg"]}))
    c = errors.classify_message
    assert c("Unknown constant `Nat.bogus_lemma`")["class"] == "hallucinated_theorem"
    wn = c("Unknown identifier `real.sqrt`")
    assert wn["class"] == "wrong_namespace" and wn["suggestion"] == "Real.sqrt"
    assert c("Unknown identifier `Nat.sq_nonneg`")["class"] == "wrong_namespace"
    assert c("failed to synthesize\n  OrderedField ℕ")["class"] == "instance_resolution_failure"
    assert c("unsolved goals\na b : ℝ\n⊢ a ≤ b")["class"] == "valid_but_wrong"
    assert c("linarith failed to find a contradiction")["class"] == "wrong_tactic"
    assert c("type mismatch\n  h\nhas type\n  a < b : Prop\nbut is expected to have type")["class"] == "type_mismatch"
    assert c("(deterministic) timeout at `whnf`, maximum number of heartbeats (200000)")["class"] == "timeout"
    assert c("Tactic `rewrite` failed: did not find instance of the pattern")["class"] == "incorrect_rewrite"
    assert c("don't know how to synthesize placeholder")["class"] == "unresolved_metavariable"
    assert c("invalid alternative name 'nil'")["class"] == "bad_induction"
    assert c("unexpected token 'at'; expected command", "begin\n  simp\nend")["class"] == "lean3_syntax"
    assert c("unexpected token 'at'; expected command", "simp at h")["class"] == "syntax_error"
    assert c("something new")["class"] == "other"


def test_classify_attempt_uses_first_error_as_primary():
    att = {"proof": "simp", "messages": [
        {"severity": "warning", "text": "unused"},
        {"severity": "error", "text": "unsolved goals\n⊢ False"},
        {"severity": "error", "text": "linarith failed"}]}
    out = errors.classify_attempt(att)
    assert out["primary"] == "valid_but_wrong" and out["all"] == ["valid_but_wrong", "wrong_tactic"]


def test_classify_attempt_without_messages_uses_output():
    assert errors.classify_attempt({"compiler_output": "(no proof found in the model's reply)"})["primary"] == "no_proof"
    assert errors.classify_attempt({"compiler_output": "rejected before compilation: forbidden token(s): sorry"})["primary"] == "forbidden"


def test_parse_error_takes_precedence_over_earlier_unsolved_goals():
    # Real shape from the demo: Lean reports "unsolved goals" (3:65) before the stray-token parse error (4:2).
    att = {"proof": ":= by apply foo", "messages": [
        {"severity": "error", "text": "unsolved goals\n⊢ Odd p"},
        {"severity": "error", "text": "unexpected token ':='; expected command"}]}
    out = errors.classify_attempt(att)
    assert out["primary"] == "syntax_error" and out["all"] == ["valid_but_wrong", "syntax_error"]


def test_lean3_tactics_namespaces_and_end_are_lean3_syntax():
    c = errors.classify_message
    assert c("unknown tactic", "apply foo;\n  apply_instance")["class"] == "lean3_syntax"
    assert c("unknown tactic", "reflexivity")["class"] == "lean3_syntax"
    assert c("unexpected token ','; expected command", "simp,\nend,")["class"] == "lean3_syntax"
    assert c("unexpected token 'at'", "simp only [measure_theory.norm_sub]")["class"] == "lean3_syntax"
    assert c("unknown tactic", "frobnicate")["class"] == "syntax_error"
    assert c("Invalid simp theorem: Expected a proposition, but found ι → α")["class"] == "type_mismatch"


def test_bare_expected_token_is_a_syntax_error():
    assert errors.classify_message("expected token")["class"] == "syntax_error"
    assert errors.classify_message("expected term")["class"] == "syntax_error"
    # "is expected to have type" stays a type mismatch
    assert errors.classify_message("h is expected to have type ℕ")["class"] == "type_mismatch"
