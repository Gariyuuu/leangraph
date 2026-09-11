-- CI fixture: one real theorem, checked by the pinned Lean + Mathlib.
import Mathlib

theorem lg_fixture (a b : ℝ) (ha : 0 ≤ a) (hb : 0 ≤ b) : a * b ≤ (a ^ 2 + b ^ 2) / 2 := by
  nlinarith [sq_nonneg (a - b)]

#print axioms lg_fixture
