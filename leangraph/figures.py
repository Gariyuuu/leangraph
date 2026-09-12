"""Paper figures, rendered from analysis JSON only.

    python -m leangraph.figures --run-id main

Colour follows the validated reference palette (dataviz skill, slots 1-4,
light mode: every hard gate passes; slots 3-4 sit below 3:1 on the surface, so
every figure direct-labels its marks and ships a CSV table twin). Line series
are told apart by dash pattern first and hue second, per the portfolio design
system. One y-axis per chart, always.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "results" / "analysis"
RETRIEVAL = ROOT / "results" / "retrieval" / "summary.json"

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
DASHES = [(None, None), (6, 4), (1, 4), (10, 4, 2, 4)]
DEEMPH = "#c3c2b7"
from .labels import CONFIG_LABELS as LABELS, HEADLINE  # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 9, "axes.edgecolor": AXIS, "axes.linewidth": 1.0, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": INK2, "text.color": INK, "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "grid.linestyle": "-", "axes.axisbelow": True, "legend.frameon": False,
})


def error_display(k: str) -> str:
    """Error-class key as printed in figures and the paper (e.g. lean3_syntax -> Lean 3 syntax)."""
    return k.replace("_", " ").replace("lean3", "Lean 3")


def _save(fig, out: Path, name: str, rows: list[dict]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    if rows:
        with (out / f"{name}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def fig_verified_rate(s: dict, out: Path, emphasis: str = "full") -> None:
    """Dot + 95% Wilson interval per configuration; the full agent is the emphasised series."""
    items = sorted(s["configs"].items(), key=lambda kv: kv[1]["rate"])
    if emphasis not in s["configs"]:  # before the full agent has run, emphasise the best model configuration
        llm = [(c, m) for c, m in items if c != "template"]
        emphasis = max(llm, key=lambda kv: kv[1]["rate"])[0] if llm else ""
    fig, ax = plt.subplots(figsize=(6.2, 0.32 * len(items) + 0.9))
    for y, (cfg, m) in enumerate(items):
        col = SERIES[0] if cfg == emphasis else MUTED
        ax.plot(m["ci"], [y, y], color=col, lw=2, solid_capstyle="round")
        ax.scatter([m["rate"]], [y], s=42, color=col, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.text(m["ci"][1] + 0.01, y, f"{m['rate']:.1%}  ({m['verified']}/{m['n']})", va="center", color=INK2, fontsize=8)
    ax.set_yticks(range(len(items)), [LABELS.get(c, c) for c, _ in items])
    ax.set_xlim(0, min(1.0, max(m["ci"][1] for _, m in items) + 0.2))
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Verified proof rate (95% Wilson interval)")
    ax.grid(axis="y", visible=False)
    _save(fig, out, "verified_rate", [{"config": c, "rate": m["rate"], "ci_low": m["ci"][0], "ci_high": m["ci"][1],
                                       "verified": m["verified"], "n": m["n"]} for c, m in items])


def fig_success_within(s: dict, out: Path, configs=("direct", "repair", "rag_repair", "full")) -> None:
    present = [c for c in configs if c in s["configs"]]
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    rows = []
    for i, cfg in enumerate(present):
        sw = s["configs"][cfg]["success_within"]
        xs = sorted(int(k) for k in sw)[1:]
        ys = [sw[str(x)] if str(x) in sw else sw[x] for x in xs]
        ax.plot(xs, ys, color=SERIES[i], lw=2, dashes=DASHES[i] if DASHES[i][0] else (None, None),
                solid_capstyle="round", label=LABELS.get(cfg, cfg))
        ax.scatter([xs[-1]], [ys[-1]], s=36, color=SERIES[i], edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(f"{ys[-1]:.0%}", (xs[-1], ys[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", color=INK2, fontsize=8)
        rows += [{"config": cfg, "llm_calls": x, "success": y} for x, y in zip(xs, ys)]
    ax.set_xlabel("LLM calls allowed per theorem")
    ax.set_ylabel("Share of theorems verified")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", fontsize=8, handlelength=3)
    _save(fig, out, "success_within_calls", rows)


def nonneg_err(errs):
    """Error-bar lengths clipped at 0. A Wilson interval for k = 0 can put its lower bound a few 1e-17 above the
    point estimate, which matplotlib rejects; clipping removes only that floating-point noise."""
    return None if errs is None else np.clip(np.asarray(errs, dtype=float), 0.0, None)


def _hbar(ax, labels, values, fmt, errs=None):
    ys = range(len(labels))
    e = nonneg_err(errs)
    ax.barh(ys, values, height=0.55, color=SERIES[0], xerr=e, error_kw={"ecolor": INK2, "lw": 1, "capsize": 0})
    for i, (y, v) in enumerate(zip(ys, values)):
        x = v + (e[1][i] if e is not None else 0.0)  # past the interval, so the label never sits on its line
        ax.text(x, y, "  " + fmt(v), va="center", color=INK2, fontsize=8)
    ax.set_yticks(list(ys), labels)
    ax.grid(axis="y", visible=False)


def fig_errors(s: dict, out: Path, top: int = 8) -> None:
    total = s["errors"]["total"]
    items = sorted(total.items(), key=lambda kv: -kv[1])
    head, tail = items[:top], sum(v for _, v in items[top:])
    if tail:
        head.append(("other classes", tail))
    head = head[::-1]
    n = sum(total.values()) or 1
    fig, ax = plt.subplots(figsize=(5.6, 0.3 * len(head) + 0.9))
    _hbar(ax, [error_display(k) for k, _ in head], [v / n for _, v in head], lambda v: f"{v:.0%}")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel(f"Share of failed attempts (n = {n}), by first Lean error")
    _save(fig, out, "error_taxonomy", [{"class": k, "count": v, "share": v / n} for k, v in items])


def fig_repair_by_class(s: dict, out: Path, min_n: int = 5) -> None:
    from .stats import wilson
    rb = {k: v for k, v in s["errors"]["repair_by_class"].items() if v["n"] >= min_n}
    items = sorted(rb.items(), key=lambda kv: kv[1]["rate"])
    if not items:
        return
    fig, ax = plt.subplots(figsize=(5.6, 0.3 * len(items) + 0.9))
    rates = [v["rate"] for _, v in items]
    cis = [wilson(v["next_round_verified"], v["n"]) for _, v in items]
    errs = [[r - lo for r, (lo, _) in zip(rates, cis)], [hi - r for r, (_, hi) in zip(rates, cis)]]
    _hbar(ax, [f"{error_display(k)} (n={v['n']})" for k, v in items], rates, lambda v: f"{v:.0%}", errs)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Next repair round verified, given this error (95% Wilson interval)")
    _save(fig, out, "repair_by_class", [{"class": k, **v} for k, v in items])


def fig_cost_quality(s: dict, out: Path) -> None:
    items = [(c, m) for c, m in s["configs"].items() if m["n"] and m["llm_calls"]]
    if not items:
        return
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    xs = [m["cost_usd"] / m["n"] for _, m in items]
    ys = [m["rate"] for _, m in items]
    for (c, _), x, y in zip(items, xs, ys):
        key = c in HEADLINE
        ax.scatter([x], [y], s=42 if key else 22, color=SERIES[0] if key else MUTED, edgecolor=SURFACE,
                   linewidth=1.5, zorder=3)
        if key:
            ax.annotate(LABELS.get(c, c), (x, y), xytext=(5, 3), textcoords="offset points", fontsize=7, color=INK2)
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:g}"))
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    if len(items) > len([c for c, _ in items if c in HEADLINE]):
        ax.set_title("Small grey points: ablations and variants (values in cost_quality.csv)", fontsize=7,
                     color=MUTED, loc="left")
    ax.set_xlabel("Mean model cost per theorem attempted (USD, log scale)")
    ax.set_ylabel("Verified proof rate")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    _save(fig, out, "cost_quality", [{"config": c, "cost_per_task": x, "rate": y,
                                      "cost_per_verified": m["cost_per_verified"]}
                                     for (c, m), x, y in zip(items, xs, ys)])


def fig_difficulty(s: dict, out: Path, configs=("template", "direct", "full")) -> None:
    present = [c for c in configs if c in s["by_difficulty"]]
    tiers = ["mathlib_heldout/easy", "mathlib_heldout/medium", "mathlib_heldout/hard"]
    if not present:
        return
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    width = 0.8 / len(present)
    rows = []
    for i, cfg in enumerate(present):
        vals = [s["by_difficulty"][cfg].get(t, {}).get("rate", 0.0) for t in tiers]
        xs = [j + (i - (len(present) - 1) / 2) * width for j in range(len(tiers))]
        ax.bar(xs, vals, width=width * 0.9, color=SERIES[i], label=LABELS.get(cfg, cfg))
        for x, v in zip(xs, vals):
            ax.text(x, v, f"{v:.0%}", ha="center", va="bottom", fontsize=7, color=INK2)
        rows += [{"config": cfg, "tier": t, "rate": v} for t, v in zip(tiers, vals)]
    ax.set_xticks(range(len(tiers)), ["easy", "medium", "hard"])
    ax.set_xlabel("Held-out difficulty tier (composite proxy terciles)")
    ax.set_ylabel("Verified proof rate")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=8)
    _save(fig, out, "difficulty", rows)


def fig_retrieval(out: Path) -> None:
    if not RETRIEVAL.exists():
        return
    s = json.loads(RETRIEVAL.read_text())
    ks = [1, 5, 8, 10, 20, 50]
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    rows = []
    for i, m in enumerate(["bm25", "dense", "hybrid"]):
        a = s["methods"].get(m, {}).get("all")
        if not a:
            continue
        ys = [a[f"recall@{k}"]["mean"] for k in ks]
        ax.plot(ks, ys, color=SERIES[i], lw=2, dashes=DASHES[i] if DASHES[i][0] else (None, None), label=m.upper() if m == "bm25" else m)
        ax.annotate(f"{ys[-1]:.0%}", (ks[-1], ys[-1]), xytext=(6, 0), textcoords="offset points", fontsize=8, color=INK2, va="center")
        rows += [{"method": m, "k": k, "recall": y} for k, y in zip(ks, ys)]
    ax.set_xscale("log")
    ax.set_xticks(ks, [str(k) for k in ks])
    ax.set_xlabel("k (log scale)")
    ax.set_ylabel("Recall of reference-proof premises")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=8, handlelength=3)
    _save(fig, out, "retrieval_recall", rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="main")
    run_id = ap.parse_args().run_id
    s = json.loads((ANALYSIS / run_id / "summary.json").read_text())
    out = ROOT / "results" / "figures" / run_id
    for fn in (fig_verified_rate, fig_success_within, fig_errors, fig_repair_by_class, fig_cost_quality, fig_difficulty):
        fn(s, out)
    fig_retrieval(out)
    print("figures in", out)


if __name__ == "__main__":
    main()
