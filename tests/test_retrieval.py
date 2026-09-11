from leangraph.retrieval import BM25, Premise, PremiseIndex, recall_at_k, reciprocal_rank, tokenize


def P(name, module, sig, doc=None):
    return Premise(name, module, sig, doc, 1)


def test_tokenize_splits_lean_identifiers_and_keeps_symbols():
    toks = tokenize("Nat.Prime.odd_of_ne_two (p : ℕ) : a ≤ b ∧ IsCoprime x y")
    for t in ["nat", "prime", "odd", "of", "ne", "two", "ℕ", "≤", "∧", "is", "coprime", "iscoprime"]:
        assert t in toks, t
    assert ":" not in toks and "(" not in toks


def test_display_strips_universes_and_newlines():
    p = P("Foo.bar", "M", "Foo.bar.{u_1, u_2} {α : Type u_1}\n  (a : α) : a = a")
    assert p.display() == "Foo.bar {α : Type u_1} (a : α) : a = a"


def test_bm25_prefers_matching_document():
    docs = [tokenize("gcd comm nat"), tokenize("set union inter"), tokenize("prime odd two nat")]
    s = BM25(docs).scores(tokenize("odd prime"))
    assert s.argmax() == 2 and s[1] == 0


def test_bm25_unknown_terms_score_zero():
    assert BM25([tokenize("a b")]).scores(["zzz"]).sum() == 0


def test_index_never_returns_excluded_modules():
    ps = [P("A.odd_prime", "Held.Out", "A.odd_prime : odd prime"), P("B.odd_prime", "Kept", "B.odd_prime : odd prime"),
          P("C.other", "Kept", "C.other : set union")]
    idx = PremiseIndex(ps, exclude_modules=frozenset({"Held.Out"}), dense=False)
    assert [h.name for h in idx.bm25("odd prime", 3)] == ["B.odd_prime", "C.other"]


def test_retrieval_metrics():
    assert recall_at_k(["a", "b", "c"], {"b", "z"}, 2) == 0.5
    assert recall_at_k(["a"], set(), 1) is None
    assert reciprocal_rank(["a", "b"], {"b"}) == 0.5
    assert reciprocal_rank(["a"], {"q"}) == 0.0


def test_tactic_internal_lemmas_are_not_premises():
    from leangraph.retrieval import is_tactic_internal
    assert is_tactic_internal("Mathlib.Tactic.Ring.Common.add_pf_add_zero")
    assert is_tactic_internal("Mathlib.Meta.NormNum.isNat_ofNat")
    assert is_tactic_internal("Linarith.lt_irrefl", "Mathlib.Tactic.Linarith.Lemmas")
    assert not is_tactic_internal("Nat.Prime.odd_of_ne_two", "Mathlib.Algebra.Order.Ring.Lemmas")
    assert not is_tactic_internal("sq_nonneg", "Mathlib.Algebra.Order.Ring.Unbundled.Basic")


def test_dense_build_is_safe_under_concurrent_callers(tmp_path, monkeypatch):
    import threading

    import numpy as np

    from leangraph import retrieval

    class FakeModel:
        calls = 0

        def embed(self, texts, batch_size=128):
            FakeModel.calls += 1
            for t in texts:
                yield np.array([len(t), 1.0, 2.0], dtype=np.float32)

    monkeypatch.setattr(retrieval, "EMB_DIR", tmp_path)
    monkeypatch.setattr(retrieval, "DENSE_CHUNK", 3)
    monkeypatch.setattr(retrieval, "_embedder", lambda: FakeModel())
    ps = [P(f"n{i}", "M", f"n{i} : x = x" + "y" * i) for i in range(10)]
    out, errs = [], []

    def run():
        try:
            out.append(retrieval.build_dense_embeddings(ps, log=lambda m: None))
        except Exception as e:  # pragma: no cover - the assertion below reports it
            errs.append(e)

    threads = [threading.Thread(target=run) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errs and len(set(out)) == 1
    m = np.load(out[0])
    assert m.shape == (10, 3) and FakeModel.calls == 4  # four chunks of <=3, embedded exactly once
    assert not list(tmp_path.glob("chunk_*")) and not list(tmp_path.glob("*.tmp.npy"))
