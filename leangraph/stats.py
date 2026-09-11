"""Statistics used in every table: Wilson intervals, bootstrap, paired tests."""
from __future__ import annotations

import numpy as np
from scipy.stats import binomtest


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def bootstrap_ci(x, stat=np.mean, n_boot: int = 10_000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    boots = np.array([stat(x[rng.integers(0, len(x), len(x))]) for _ in range(n_boot)])
    return (float(np.quantile(boots, alpha / 2)), float(np.quantile(boots, 1 - alpha / 2)))


def paired_diff_ci(a, b, n_boot: int = 10_000, seed: int = 0) -> tuple[float, float, float]:
    """Mean of (a - b) over paired tasks, with a percentile bootstrap CI."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    lo, hi = bootstrap_ci(d, n_boot=n_boot, seed=seed)
    return float(d.mean()) if len(d) else float("nan"), lo, hi


def mcnemar_exact(a, b) -> dict:
    """Exact McNemar test for paired binary outcomes (a, b solved per task)."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    only_a, only_b = int((a & ~b).sum()), int((~a & b).sum())
    n = only_a + only_b
    p = 1.0 if n == 0 else binomtest(only_a, n, 0.5).pvalue
    return {"only_a": only_a, "only_b": only_b, "p": float(p)}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out
