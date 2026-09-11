"""Fast tests: no Lean process."""
from leangraph.verify import FORBIDDEN_PATTERNS, clean_proof, forbidden_tokens, render


def test_clean_proof_strips_fence_and_by():
    raw = "Here you go:\n```lean\nby\n  nlinarith [sq_nonneg (a - b)]\n```"
    assert clean_proof(raw) == "nlinarith [sq_nonneg (a - b)]"


def test_clean_proof_strips_restated_header():
    raw = "```lean\ntheorem t (a : ℕ) : a = a := by\n  rfl\n```"
    assert clean_proof(raw) == "rfl"


def test_clean_proof_takes_last_fence():
    raw = "```lean\nsimp\n```\nActually better:\n```lean\nomega\n```"
    assert clean_proof(raw) == "omega"


def test_clean_proof_keeps_multiline_indentation():
    raw = "```lean\ninduction n with\n| zero => simp\n| succ k ih =>\n  rw [ih]\n```"
    assert clean_proof(raw).splitlines() == ["induction n with", "| zero => simp", "| succ k ih =>", "  rw [ih]"]


def test_render_indents_and_scopes_opens():
    code = render("(x : ℝ) : x = x", "rfl", opens="Real")
    assert "open Real in\ntheorem lg_target (x : ℝ) : x = x := by\n  rfl\n" in code
    assert code.startswith("set_option maxHeartbeats 200000 in\n")


def test_forbidden_catches_escape_hatches():
    cases = {
        "sorry": "sorry", "exact sorryAx _ false": "sorry", "admit": "admit",
        "native_decide": "native_decide", "set_option maxHeartbeats 0 in simp": "set_option",
        "trivial\naxiom evil : False": "axiom", "simp\n#eval 1": "command",
        "exact h\nexample : True := trivial -- in": "command", "open Real": "command",
        "exact h\ntheorem helper : True := trivial": "command",
    }
    for proof, tag in cases.items():
        assert tag in forbidden_tokens(proof), proof


def test_forbidden_allows_legitimate_proofs():
    for proof in ["open Real in simp", "nlinarith [sq_nonneg (a - b)]", "rw [List.prefix_append]",
                  "exact ⟨#[1], rfl⟩", "induction n with\n| zero => simp\n| succ k ih => omega",
                  "intro x hx\nexact hx.le"]:
        assert forbidden_tokens(proof) == [], proof


def test_allow_sorry_only_relaxes_sorry():
    assert forbidden_tokens("have h : 1 = 1 := sorry\nexact h", allow_sorry=True) == []
    assert "axiom" in forbidden_tokens("sorry\naxiom x : False", allow_sorry=True)


def test_every_pattern_is_named():
    assert all(isinstance(k, str) and k for k in FORBIDDEN_PATTERNS)


def test_clean_proof_strips_restated_assignment_and_by():
    # Seen in real model output: the reply repeats the tail of the header.
    assert clean_proof(":= by apply Nat.Prime.odd_of_ne_two hp h2") == "apply Nat.Prime.odd_of_ne_two hp h2"
    assert clean_proof(":= by\n  have h := hf 0 0\n  simp at h") == "have h := hf 0 0\nsimp at h"
    assert clean_proof(":=by simp") == "simp"
    # A `:=` inside the proof is untouched.
    assert clean_proof("have h : a = a := rfl\nexact h") == "have h : a = a := rfl\nexact h"


def test_lean3_end_is_left_to_lean_not_the_filter():
    # `end` cannot inject anything; rejecting it pre-compilation mislabelled Lean 3 proofs as cheating.
    assert forbidden_tokens("simp,\nend,") == []
