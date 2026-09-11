"""Premise retrieval over the Mathlib theorem dump.

Three retrievers over the same documents (signature + docstring):
BM25 (sparse-matrix implementation), dense (bge-small-en-v1.5 via fastembed),
and hybrid (reciprocal-rank fusion of the two). The dense model is
general-purpose and was not trained on Mathlib, so it cannot have memorised
held-out premises.

Premises from held-out modules are removed when the index is built, so no
retriever can return a target theorem, anything from its module, or anything
from a module that depends on it.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
PREMISES_PATH = ROOT / "corpus" / "premises.jsonl"
EMB_DIR = ROOT / "corpus" / "embeddings"
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
DENSE_CHUNK = 20_000
RRF_K = 60
BM25_K1, BM25_B = 1.2, 0.75

_UNIVERSES = re.compile(r"^([^\s]+?)\.\{[^}]*\}")


@dataclass(frozen=True)
class Premise:
    name: str
    module: str
    signature: str
    doc: str | None
    line: int

    def display(self) -> str:
        """Signature without universe annotations, on one line."""
        return re.sub(r"\s*\n\s*", " ", _UNIVERSES.sub(r"\1", self.signature))

    def text(self) -> str:
        return self.display() + (f"  -- {self.doc.strip()}" if self.doc else "")


TACTIC_INTERNAL_PREFIXES = ("Mathlib.Tactic.", "Mathlib.Meta.")


def is_tactic_internal(name: str, module: str = "") -> bool:
    """Lemmas that automation (ring, norm_num, positivity, linarith, ...) inserts into proof
    terms. They appear in elaborated proofs but are not premises anyone cites, so they are
    excluded from the index and from retrieval ground truth."""
    return name.startswith(TACTIC_INTERNAL_PREFIXES) or module.startswith("Mathlib.Tactic.")


def load_premises(path: Path = PREMISES_PATH, user_facing: bool = True) -> list[Premise]:
    out = []
    with path.open() as f:
        for ln in f:
            d = json.loads(ln)
            if user_facing and is_tactic_internal(d["name"], d["module"]):
                continue
            out.append(Premise(d["name"], d["module"], d["signature"], d.get("doc"), int(d.get("line", 0))))
    return out


@lru_cache(maxsize=1)
def user_facing_names() -> frozenset[str] | None:
    """Names of indexable premises, or None when the premise dump is absent (e.g. in CI)."""
    return frozenset(p.name for p in load_premises()) if PREMISES_PATH.exists() else None


_WORD = re.compile(r"[A-Za-z0-9_.']+")
_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")
_SKIP = set("()[]{},:")


def tokenize(text: str) -> list[str]:
    """Lean-aware tokens: split dotted/snake/camel identifiers, keep math symbols."""
    toks: list[str] = []
    for m in re.finditer(r"[A-Za-z0-9_.']+|\S", text):
        piece = m.group(0)
        if _WORD.fullmatch(piece):
            for part in re.split(r"[._']+", piece):
                if not part:
                    continue
                subs = _CAMEL.findall(part)
                toks.extend(s.lower() for s in subs)
                if len(subs) > 1:
                    toks.append(part.lower())
        elif piece not in _SKIP:
            toks.append(piece)
    return toks


class BM25:
    """Okapi BM25 with Lucene's non-negative idf, precomputed into one sparse matrix."""

    def __init__(self, docs: list[list[str]], k1: float = BM25_K1, b: float = BM25_B):
        self.vocab: dict[str, int] = {}
        rows, cols, tfs = [], [], []
        for i, toks in enumerate(docs):
            for t, n in Counter(toks).items():
                rows.append(i)
                cols.append(self.vocab.setdefault(t, len(self.vocab)))
                tfs.append(n)
        rows_a = np.asarray(rows, dtype=np.int32)
        cols_a = np.asarray(cols, dtype=np.int32)
        tf = np.asarray(tfs, dtype=np.float32)
        n_docs, n_terms = len(docs), len(self.vocab)
        dl = np.bincount(rows_a, weights=tf, minlength=n_docs)
        df = np.bincount(cols_a, minlength=n_terms)
        idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
        weight = idf[cols_a] * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl[rows_a] / dl.mean()))
        self.matrix = sparse.csc_matrix((weight, (rows_a, cols_a)), shape=(n_docs, n_terms))

    def scores(self, query: list[str]) -> np.ndarray:
        q = Counter(t for t in query if t in self.vocab)
        if not q:
            return np.zeros(self.matrix.shape[0], dtype=np.float32)
        idx = np.fromiter((self.vocab[t] for t in q), dtype=np.int64)
        return np.asarray(self.matrix[:, idx] @ np.fromiter(q.values(), dtype=np.float32)).ravel()


def _embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(DENSE_MODEL, cache_dir=str(ROOT / ".cache" / "fastembed"), threads=8)


def build_dense_embeddings(premises: list[Premise], log=print) -> Path:
    """Embed every premise in resumable chunks; returns the path of the full matrix.

    Safe to call from several processes at once: an exclusive lock makes later callers wait
    and then reuse the finished matrix, and every file is written to a temp name and renamed.
    """
    import fcntl
    import os

    EMB_DIR.mkdir(parents=True, exist_ok=True)
    final = EMB_DIR / f"bge_small_{len(premises)}.npy"
    if final.exists():
        return final
    with open(EMB_DIR / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if final.exists():
            return final
        model = _embedder()
        chunks = []
        for start in range(0, len(premises), DENSE_CHUNK):
            path = EMB_DIR / f"chunk_{start:07d}.npy"
            if not path.exists():
                texts = [p.text()[:1000] for p in premises[start:start + DENSE_CHUNK]]
                vecs = np.asarray(list(model.embed(texts, batch_size=128)), dtype=np.float32)
                vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
                tmp = path.with_name(path.stem + ".tmp.npy")
                np.save(tmp, vecs.astype(np.float16))
                os.replace(tmp, path)
                log(f"embedded {min(start + DENSE_CHUNK, len(premises))}/{len(premises)}")
            chunks.append(path)
        tmp = final.with_name(final.stem + ".tmp.npy")
        np.save(tmp, np.concatenate([np.load(c) for c in chunks]))
        os.replace(tmp, final)
        for c in chunks:
            c.unlink()
    return final


class PremiseIndex:
    """All three retrievers over one filtered premise list."""

    def __init__(self, premises: list[Premise], exclude_modules: frozenset[str] = frozenset(), dense: bool = True):
        keep = np.array([p.module not in exclude_modules for p in premises])
        self.premises = [p for p, k in zip(premises, keep) if k]
        self.excluded_modules = exclude_modules
        self._bm25 = BM25([tokenize(p.text()) for p in self.premises])
        self._emb: np.ndarray | None = None
        self._model = None
        if dense:
            full = np.load(build_dense_embeddings(premises))
            self._emb = np.asarray(full[keep], dtype=np.float32)
            self._model = _embedder()

    @staticmethod
    def _top(scores: np.ndarray, k: int) -> np.ndarray:
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        return top[np.argsort(-scores[top], kind="stable")]

    def bm25(self, query: str, k: int) -> list[Premise]:
        return [self.premises[i] for i in self._top(self._bm25.scores(tokenize(query)), k)]

    def dense(self, query: str, k: int) -> list[Premise]:
        assert self._emb is not None and self._model is not None, "dense index not loaded"
        q = np.asarray(next(iter(self._model.query_embed([query]))), dtype=np.float32)
        return [self.premises[i] for i in self._top(self._emb @ (q / np.linalg.norm(q)), k)]

    def hybrid(self, query: str, k: int, pool: int = 100) -> list[Premise]:
        fused: dict[str, float] = {}
        by_name: dict[str, Premise] = {}
        for ranked in (self.bm25(query, pool), self.dense(query, pool)):
            for rank, p in enumerate(ranked):
                fused[p.name] = fused.get(p.name, 0.0) + 1.0 / (RRF_K + rank + 1)
                by_name[p.name] = p
        return [by_name[n] for n in sorted(fused, key=lambda n: (-fused[n], n))[:k]]

    def search(self, query: str, method: str, k: int) -> list[Premise]:
        return {"bm25": self.bm25, "dense": self.dense, "hybrid": self.hybrid}[method](query, k)


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float | None:
    if not relevant:
        return None
    for i, name in enumerate(retrieved):
        if name in relevant:
            return 1.0 / (i + 1)
    return 0.0
