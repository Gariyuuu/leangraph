"""Theorems written for LeanGraph (the `novel` split).

These statements were written for this project rather than copied from Mathlib,
to measure how much of the held-out success comes from recalling Mathlib's own
theorems. They are textbook-style, so similar statements surely exist in
training data; the claim is only that these exact formal statements are not
Mathlib declarations.

`difficulty` is the author's label before any model was run. Each reference
proof must pass `verify.certify`; entries that do not are dropped when the
corpus is built and never reported.
"""
from __future__ import annotations

NOVEL: list[dict] = [
    # algebra
    dict(id="novel_alg_01", family="algebra", difficulty="easy",
         statement="(a b : ℝ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2", proof="ring"),
    dict(id="novel_alg_02", family="algebra", difficulty="medium",
         statement="(x : ℝ) (hx : x ≠ 1) : (x ^ 3 - 1) / (x - 1) = x ^ 2 + x + 1",
         proof="have h : x - 1 ≠ 0 := sub_ne_zero.mpr hx\nfield_simp\nring"),
    dict(id="novel_alg_03", family="algebra", difficulty="easy",
         statement="(a b c : ℚ) (h₁ : a + b = 5) (h₂ : b + c = 7) (h₃ : a + c = 6) : a = 2", proof="linarith"),
    dict(id="novel_alg_04", family="algebra", difficulty="medium",
         statement="(x y : ℝ) (h₁ : x + y = 10) (h₂ : x - y = 4) : x * y = 21",
         proof="have hx : x = 7 := by linarith\nhave hy : y = 3 := by linarith\nsubst hx hy\nnorm_num"),
    dict(id="novel_alg_05", family="algebra", difficulty="medium",
         statement="(n : ℕ) : ∑ i ∈ Finset.range (n + 1), (2 * i + 1) = (n + 1) ^ 2",
         proof="induction n with\n| zero => simp\n| succ k ih =>\n  rw [Finset.sum_range_succ, ih]\n  ring"),
    dict(id="novel_alg_06", family="algebra", difficulty="medium",
         statement="(x : ℝ) (h : x ^ 2 - 5 * x + 6 = 0) : x = 2 ∨ x = 3",
         proof="have h' : (x - 2) * (x - 3) = 0 := by ring_nf; linarith\n"
               "rcases mul_eq_zero.mp h' with h1 | h1\n· left; linarith\n· right; linarith"),
    dict(id="novel_alg_07", family="algebra", difficulty="medium",
         statement="(f : ℕ → ℕ) (h0 : f 0 = 1) (hs : ∀ n, f (n + 1) = 2 * f n) (n : ℕ) : f n = 2 ^ n",
         proof="induction n with\n| zero => simp [h0]\n| succ k ih => rw [hs, ih, pow_succ]; ring"),
    dict(id="novel_alg_08", family="algebra", difficulty="hard",
         statement="(n : ℕ) : ∑ i ∈ Finset.range (n + 1), (i : ℚ) = n * (n + 1) / 2",
         proof="induction n with\n| zero => simp\n| succ k ih =>\n  rw [Finset.sum_range_succ, ih]\n  push_cast\n  ring"),
    dict(id="novel_alg_09", family="algebra", difficulty="medium",
         statement="(x : ℝ) (hx : 0 < x) : Real.log (x ^ 3) = 3 * Real.log x",
         proof="rw [Real.log_pow]\nnorm_num"),
    dict(id="novel_alg_10", family="algebra", difficulty="easy",
         statement="{G : Type*} [Group G] (a b : G) : (a * b)⁻¹ = b⁻¹ * a⁻¹", proof="simp"),
    # inequalities
    dict(id="novel_ineq_01", family="inequalities", difficulty="easy",
         statement="(a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2", proof="nlinarith [sq_nonneg (a - b)]"),
    dict(id="novel_ineq_02", family="inequalities", difficulty="medium",
         statement="(x : ℝ) (hx : 0 < x) : x + 1 / x ≥ 2",
         proof="have key : x + 1 / x - 2 = (x - 1) ^ 2 / x := by field_simp; ring\n"
               "have : 0 ≤ (x - 1) ^ 2 / x := by positivity\nlinarith"),
    dict(id="novel_ineq_03", family="inequalities", difficulty="easy",
         statement="(a b c : ℝ) : a * b + b * c + c * a ≤ a ^ 2 + b ^ 2 + c ^ 2",
         proof="nlinarith [sq_nonneg (a - b), sq_nonneg (b - c), sq_nonneg (c - a)]"),
    dict(id="novel_ineq_04", family="inequalities", difficulty="medium",
         statement="(a b : ℝ) (ha : 0 < a) (hb : 0 < b) : (a + b) * (1 / a + 1 / b) ≥ 4",
         proof="have h : (a + b) * (1 / a + 1 / b) = 2 + a / b + b / a := by field_simp; ring\n"
               "have h2 : a / b + b / a ≥ 2 := by\n  rw [ge_iff_le, div_add_div _ _ hb.ne' ha.ne', le_div_iff₀ (by positivity)]\n"
               "  nlinarith [sq_nonneg (a - b)]\nlinarith"),
    dict(id="novel_ineq_05", family="inequalities", difficulty="easy",
         statement="(x y : ℝ) (hx : 0 ≤ x) (hy : 0 ≤ y) (h : x + y = 2) : x * y ≤ 1",
         proof="nlinarith [sq_nonneg (x - y)]"),
    dict(id="novel_ineq_06", family="inequalities", difficulty="hard",
         statement="(a b c : ℝ) (ha : 0 < a) (hb : 0 < b) (hc : 0 < c) : a / b + b / c + c / a ≥ 3",
         proof="rw [ge_iff_le, div_add_div _ _ hb.ne' hc.ne', div_add_div _ _ (by positivity) ha.ne', le_div_iff₀ (by positivity)]\n"
               "nlinarith [sq_nonneg (a - b), sq_nonneg (b - c), sq_nonneg (c - a), mul_pos ha hb, mul_pos hb hc,\n"
               "  mul_pos ha hc, mul_pos (mul_pos ha hb) hc, sq_nonneg (a * c - b * b), sq_nonneg (a * b - c * c),\n"
               "  sq_nonneg (b * c - a * a)]"),
    dict(id="novel_ineq_07", family="inequalities", difficulty="easy",
         statement="(x : ℝ) : Real.cos x ^ 2 ≤ 1", proof="nlinarith [Real.sin_sq_add_cos_sq x, sq_nonneg (Real.sin x)]"),
    dict(id="novel_ineq_08", family="inequalities", difficulty="easy",
         statement="(n : ℕ) (hn : 3 ≤ n) : n ^ 2 ≥ 2 * n + 3", proof="nlinarith"),
    dict(id="novel_ineq_09", family="inequalities", difficulty="medium",
         statement="(n : ℕ) (hn : 1 ≤ n) : n + 1 ≤ 2 ^ n",
         proof="induction n, hn using Nat.le_induction with\n| base => norm_num\n| succ k hk ih => rw [pow_succ]; omega"),
    dict(id="novel_ineq_10", family="inequalities", difficulty="easy",
         statement="(p : ℝ) (h0 : 0 ≤ p) (h1 : p ≤ 1) : p * (1 - p) ≤ 1 / 4", proof="nlinarith [sq_nonneg (p - 1 / 2)]"),
    # number theory
    dict(id="novel_nt_01", family="number_theory", difficulty="hard",
         statement="(n : ℕ) : 6 ∣ n * (n + 1) * (n + 2)",
         proof="have h : n % 6 < 6 := Nat.mod_lt _ (by norm_num)\n"
               "interval_cases hn : n % 6 <;> simp [Nat.dvd_iff_mod_eq_zero, Nat.mul_mod, Nat.add_mod, hn]"),
    dict(id="novel_nt_02", family="number_theory", difficulty="medium",
         statement="(n : ℕ) : Nat.gcd (2 * n + 1) (n + 1) = 1",
         proof="have : 2 * n + 1 = n + (n + 1) := by ring\nrw [this, Nat.gcd_add_self_left]\nsimp"),
    dict(id="novel_nt_03", family="number_theory", difficulty="easy",
         statement="(p : ℕ) (hp : p.Prime) (h2 : p ≠ 2) : Odd p", proof="exact hp.odd_of_ne_two h2"),
    dict(id="novel_nt_04", family="number_theory", difficulty="easy",
         statement="(x : ℤ) (h : 3 ∣ x) : 9 ∣ x ^ 2", proof="obtain ⟨k, rfl⟩ := h\nexact ⟨k ^ 2, by ring⟩"),
    dict(id="novel_nt_05", family="number_theory", difficulty="medium",
         statement="(n : ℕ) : (n ^ 2 + n) % 2 = 0",
         proof="have h : n ^ 2 + n = n * (n + 1) := by ring\nrw [h]\nexact Nat.even_iff.mp (Nat.even_mul_succ_self n)"),
    dict(id="novel_nt_06", family="number_theory", difficulty="hard",
         statement="(n : ℕ) : ¬ 3 ∣ n ^ 2 + 1",
         proof="intro h\nhave hn : n % 3 < 3 := Nat.mod_lt _ (by norm_num)\n"
               "interval_cases hr : n % 3 <;> simp [Nat.dvd_iff_mod_eq_zero, Nat.add_mod, Nat.pow_mod, hr] at h"),
    dict(id="novel_nt_07", family="number_theory", difficulty="medium",
         statement="(a b : ℤ) (h : a ≡ b [ZMOD 5]) : a ^ 2 ≡ b ^ 2 [ZMOD 5]", proof="exact h.pow 2"),
    dict(id="novel_nt_08", family="number_theory", difficulty="hard",
         statement="(a b : ℕ) (h : a * b = 12) (ha : a > b) (hb : b > 2) : a = 4",
         proof="have hb4 : b < 4 := by nlinarith\ninterval_cases b\nomega"),
    dict(id="novel_nt_09", family="number_theory", difficulty="easy",
         statement="(a : ℤ) : a ^ 2 % 4 = 0 ∨ a ^ 2 % 4 = 1",
         proof="rcases Int.even_or_odd' a with ⟨k, rfl | rfl⟩\n· left; ring_nf; omega\n· right; ring_nf; omega"),
    dict(id="novel_nt_10", family="number_theory", difficulty="easy",
         statement=": Nat.choose 10 3 = 120", proof="decide"),
    # sets
    dict(id="novel_set_01", family="sets", difficulty="easy",
         statement="{α : Type*} (A B C : Set α) : A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C)",
         proof="ext x\nsimp only [Set.mem_inter_iff, Set.mem_union]\ntauto"),
    dict(id="novel_set_02", family="sets", difficulty="easy",
         statement="{α : Type*} (A B : Set α) (h : A ⊆ B) : A ∪ B = B", proof="exact Set.union_eq_right.mpr h"),
    dict(id="novel_set_03", family="sets", difficulty="medium",
         statement="{α : Type*} (A B C : Set α) (h₁ : A ⊆ B) (h₂ : B ⊆ C) : A \\ C = ∅",
         proof="ext x\nsimp only [Set.mem_diff, Set.mem_empty_iff_false, iff_false, not_and, not_not]\n"
               "intro hx\nexact h₂ (h₁ hx)"),
    dict(id="novel_set_04", family="sets", difficulty="easy",
         statement="{α : Type*} (A B : Set α) : (A ∪ B)ᶜ = Aᶜ ∩ Bᶜ", proof="exact Set.compl_union A B"),
    dict(id="novel_set_05", family="sets", difficulty="medium",
         statement="{α : Type*} (s : Set α) (f : α → α) (hf : ∀ x, f (f x) = x) : f '' (f '' s) = s",
         proof="rw [Set.image_image]\nsimp [hf]"),
    dict(id="novel_set_06", family="sets", difficulty="easy",
         statement="(S : Set ℕ) (hS : S = {n | n % 2 = 0}) : 4 ∈ S ∧ 3 ∉ S", proof="subst hS\nconstructor <;> simp"),
    dict(id="novel_set_07", family="sets", difficulty="medium",
         statement=": (Finset.filter (fun n => n % 3 = 0) (Finset.range 30)).card = 10", proof="decide"),
    dict(id="novel_set_08", family="sets", difficulty="medium",
         statement="{α : Type*} (A B : Set α) : A ⊆ B ↔ A ∩ B = A",
         proof="constructor\n· intro h; exact Set.inter_eq_left.mpr h\n· intro h; rw [← h]; exact Set.inter_subset_right"),
    # functions
    dict(id="novel_fun_01", family="functions", difficulty="easy",
         statement="{α β γ : Type*} (f : α → β) (g : β → γ) (hf : Function.Injective f) (hg : Function.Injective g) : "
                   "Function.Injective (g ∘ f)", proof="exact hg.comp hf"),
    dict(id="novel_fun_02", family="functions", difficulty="easy",
         statement="{α β : Type*} (f : α → β) (g : β → α) (h : ∀ x, g (f x) = x) : Function.Injective f",
         proof="intro a b hab\nrw [← h a, ← h b, hab]"),
    dict(id="novel_fun_03", family="functions", difficulty="easy",
         statement="(f : ℝ → ℝ) (hf : ∀ x, f x = 3 * x + 2) : Function.Injective f",
         proof="intro a b h\nrw [hf, hf] at h\nlinarith"),
    dict(id="novel_fun_04", family="functions", difficulty="medium",
         statement="(f : ℝ → ℝ) (hf : ∀ x y, f (x + y) = f x + f y) : f 0 = 0",
         proof="have h := hf 0 0\nsimp at h\nlinarith"),
    dict(id="novel_fun_05", family="functions", difficulty="medium",
         statement="(f : ℕ → ℕ) (hf : StrictMono f) (n : ℕ) : n ≤ f n", proof="exact hf.id_le n"),
    dict(id="novel_fun_06", family="functions", difficulty="hard",
         statement="(f : ℝ → ℝ) (hf : ∀ x y, f (x + y) = f x + f y) (x : ℝ) : f (-x) = -f x",
         proof="have h0 : f 0 = 0 := by\n  have h := hf 0 0\n  simp at h\n  linarith\n"
               "have h := hf x (-x)\nsimp [h0] at h\nlinarith"),
    dict(id="novel_fun_07", family="functions", difficulty="medium",
         statement="{α β : Type*} (f : α → β) (hf : Function.Surjective f) (g h : β → α) "
                   "(hg : g ∘ f = h ∘ f) : g = h", proof="exact hf.injective_comp_right hg"),
    # probability
    dict(id="novel_prob_01", family="probability", difficulty="medium",
         statement="(p : NNReal) (h : p ≤ 1) : PMF.bernoulli p h true = (p : ENNReal)",
         proof="simp [PMF.bernoulli_apply]"),
    dict(id="novel_prob_02", family="probability", difficulty="easy",
         statement="{Ω : Type*} [MeasurableSpace Ω] (μ : MeasureTheory.Measure Ω) "
                   "[MeasureTheory.IsProbabilityMeasure μ] (s : Set Ω) : μ s ≤ 1",
         proof="exact MeasureTheory.prob_le_one"),
    dict(id="novel_prob_03", family="probability", difficulty="medium",
         statement="{Ω : Type*} [MeasurableSpace Ω] (μ : MeasureTheory.Measure Ω) "
                   "[MeasureTheory.IsProbabilityMeasure μ] (A : Set Ω) (hA : MeasurableSet A) : μ Aᶜ = 1 - μ A",
         proof="exact MeasureTheory.prob_compl_eq_one_sub hA"),
    dict(id="novel_prob_04", family="probability", difficulty="medium",
         statement="(n : ℕ) : ∑ k ∈ Finset.range (n + 1), Nat.choose n k = 2 ^ n",
         proof="exact Nat.sum_range_choose n"),
    # category theory
    dict(id="novel_cat_01", family="category_theory", difficulty="easy", opens="CategoryTheory",
         statement="{C : Type*} [Category C] {X Y : C} (α : X ≅ Y) : α.hom ≫ α.inv = 𝟙 X", proof="simp"),
    dict(id="novel_cat_02", family="category_theory", difficulty="medium", opens="CategoryTheory",
         statement="{C : Type*} [Category C] {X Y Z : C} (f : X ⟶ Y) (g : Y ⟶ Z) [IsIso f] [IsIso g] : IsIso (f ≫ g)",
         proof="infer_instance"),
    dict(id="novel_cat_03", family="category_theory", difficulty="medium", opens="CategoryTheory",
         statement="{C : Type*} [Category C] {X Y Z : C} (f : X ⟶ Y) [Mono f] (g h : Z ⟶ X) (w : g ≫ f = h ≫ f) : g = h",
         proof="exact (cancel_mono f).mp w"),
    dict(id="novel_cat_04", family="category_theory", difficulty="hard", opens="CategoryTheory",
         statement="{C : Type*} [Category C] {X Y Z : C} (f : X ⟶ Y) (g : Y ⟶ Z) [Mono f] [Mono g] : Mono (f ≫ g)",
         proof="constructor\nintro W a b h\nsimp only [← Category.assoc] at h\nexact (cancel_mono f).mp ((cancel_mono g).mp h)"),
]
