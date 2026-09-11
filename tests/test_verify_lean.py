"""Lean-backed tests of both verification tiers. Slow: they start Lean with Mathlib."""
import concurrent.futures as cf
import os

import pytest

from leangraph import verify
from leangraph.verify import ReplWorker, certify

pytestmark = pytest.mark.lean

# Each certification is a fresh Lean process holding Mathlib (~2 GB). CI runners cannot hold seven at once.
WORKERS = int(os.environ.get("LG_TEST_WORKERS", "7"))

COMM = "(a b : ℕ) : a + b = b + a"
INEQ = "(a b : ℝ) (ha : 0 ≤ a) (hb : 0 ≤ b) : a * b ≤ (a ^ 2 + b ^ 2) / 2"
LOOP = "(a b : ℕ) (h : a + b = 3) : a + b = 3 ∨ False"

# Certifier cases run with the normal text filter.
FILTERED = {
    "ring": (dict(statement=COMM, proof="ring"), True, "ok"),
    "real_ineq": (dict(statement=INEQ, proof="nlinarith [sq_nonneg (a - b)]"), True, "ok"),
    "open_in": (dict(statement="(x : ℝ) : Real.exp (Real.log (Real.exp x)) = Real.exp x",
                     proof="rw [log_exp]", opens="Real"), True, "ok"),
    "unknown_ident": (dict(statement=COMM, proof="exact Nat.bogus a b"), False, "lean_error"),
    "banned_constant": (dict(statement=COMM, proof="exact Nat.add_comm a b",
                             banned_constants=frozenset({"Nat.add_comm"})), False, "banned_premise"),
    "banned_module": (dict(statement=INEQ, proof="nlinarith [sq_nonneg (a - b)]",
                           banned_modules=frozenset({"Mathlib.Algebra.Order.Ring.Lemmas"})), None, None),
    "sorry_filtered": (dict(statement=COMM, proof="sorry"), False, "forbidden"),
}

# Defense in depth: with the text filter OFF, the certifier alone must still reject.
UNFILTERED = {
    "sorryAx": dict(statement=COMM, proof="exact sorryAx _ false"),
    "spoofed_axiom_line": dict(statement=COMM, proof="exact sorryAx _ false\n"
                               "#eval IO.println \"'lg_target' depends on axioms: [propext]\""),
    "injected_axiom": dict(statement=COMM, proof="omega\naxiom evil : False"),
    "injected_theorem": dict(statement=COMM, proof="omega\ntheorem helper : True := trivial"),
    "exit_before_probe": dict(statement=COMM, proof="exact sorryAx _ false\n#exit"),
}


@pytest.fixture(scope="module")
def filtered_results():
    with cf.ThreadPoolExecutor(min(WORKERS, len(FILTERED))) as ex:
        futs = {k: ex.submit(certify, **v[0]) for k, v in FILTERED.items()}
        return {k: f.result() for k, f in futs.items()}


@pytest.fixture(scope="module")
def unfiltered_results():
    saved = dict(verify.FORBIDDEN_PATTERNS)
    verify.FORBIDDEN_PATTERNS.clear()
    try:
        with cf.ThreadPoolExecutor(min(WORKERS, len(UNFILTERED))) as ex:
            futs = {k: ex.submit(certify, **v) for k, v in UNFILTERED.items()}
            return {k: f.result() for k, f in futs.items()}
    finally:
        verify.FORBIDDEN_PATTERNS.update(saved)


@pytest.mark.parametrize("name", [k for k, v in FILTERED.items() if v[1] is not None])
def test_certify_filtered(filtered_results, name):
    _, verified, reason = FILTERED[name]
    cert = filtered_results[name]
    assert cert.verified is verified, (cert.reason, cert.stdout[-800:])
    assert cert.reason.startswith(reason), cert.reason


def test_certify_reports_standard_axioms_only(filtered_results):
    assert set(filtered_results["real_ineq"].axioms) == {"propext", "Classical.choice", "Quot.sound"}


def test_certify_module_ban_matches_used_modules(filtered_results):
    cert = filtered_results["banned_module"]
    used_mods = {m for _, m in cert.used_constants}
    assert cert.verified is ("Mathlib.Algebra.Order.Ring.Lemmas" not in used_mods)


@pytest.mark.parametrize("name", list(UNFILTERED))
def test_certifier_alone_rejects_attacks(unfiltered_results, name):
    cert = unfiltered_results[name]
    assert not cert.verified, cert.reason


def test_injected_declarations_are_named(unfiltered_results):
    assert unfiltered_results["injected_axiom"].reason.startswith("extra_declarations")
    assert "helper" in unfiltered_results["injected_theorem"].reason


@pytest.fixture(scope="module")
def worker():
    w = ReplWorker()
    w.start()
    yield w
    w.close()


def test_repl_accepts_and_rejects(worker):
    assert worker.check(COMM, "ring").ok
    bad = worker.check(COMM, "exact Nat.bogus a b")
    assert not bad.ok and "Unknown" in bad.compiler_output()


def test_repl_flags_sorry_in_skeleton_mode(worker):
    r = worker.check(COMM, "have h : a + b = b + a := sorry\nexact h", allow_sorry=True)
    assert r.ok and r.has_sorry
    assert not worker.check(COMM, "have h : a + b = b + a := sorry\nexact h").ok


def test_repl_runaway_tactic_is_stopped_and_worker_recovers(worker):
    # Lean's heartbeat limit does not bound every loop (this one runs until the
    # wall-clock backstop fires), so the property we rely on is: the check ends
    # as a failure, and the worker is usable afterwards.
    r = worker.check(LOOP, "repeat rw [Nat.add_comm] at h")
    assert not r.ok
    assert r.elapsed_s < verify.WALL_TIMEOUT_S + 5
    assert worker.check(COMM, "ring").ok


def test_repl_does_not_leak_state_between_checks(worker):
    worker.check(COMM, "ring")
    # Each check starts from the same base environment, so re-declaring lg_target is fine.
    assert worker.check(COMM, "ring").ok
