"""Build the LeanGraph benchmark.

Two splits of formal statements:

* ``mathlib_heldout``: theorems taken from Mathlib modules that almost nothing
  else imports. For a task from module M, every constant from M and from any
  module that (transitively) imports M is banned: the prover may not use it and
  the retriever never indexes it. Choosing near-leaf modules keeps that ban
  cheap for the prover while ruling out restated or generalised copies of the
  target living downstream of it.
* ``novel``: statements written for this project, each with a reference proof
  that the certifier accepts (see ``novel.py``).

Modules go to dev or test as whole units, so no module feeds both splits.
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATHLIB_DIR = ROOT / "lean_env" / ".lake" / "packages" / "mathlib"
CORPUS = ROOT / "corpus"
SEED = 20260910
MAX_DOWNSTREAM = 20  # modules that may (transitively) import a held-out module
MAX_STATEMENT_CHARS = 300
DEV_MODULE_FRACTION = 0.2

# First matching family wins, so the more specific prefixes come first.
FAMILIES: list[tuple[str, tuple[str, ...]]] = [
    ("category_theory", ("Mathlib.CategoryTheory.",)),
    ("probability", ("Mathlib.Probability.",)),
    ("functions", ("Mathlib.Logic.Function.", "Mathlib.Logic.Equiv.", "Mathlib.Data.Set.Function",
                   "Mathlib.Order.Monotone.", "Mathlib.Order.Hom.")),
    ("inequalities", ("Mathlib.Analysis.MeanInequalities", "Mathlib.Algebra.Order.",
                      "Mathlib.Analysis.SpecialFunctions.Pow.", "Mathlib.Analysis.SpecialFunctions.Log.",
                      "Mathlib.Analysis.Convex.SpecificFunctions.")),
    ("sets", ("Mathlib.Data.Set.", "Mathlib.Data.Finset.", "Mathlib.Data.Fintype.", "Mathlib.Data.Multiset.",
              "Mathlib.Order.SetNotation", "Mathlib.Order.BooleanAlgebra")),
    ("number_theory", ("Mathlib.NumberTheory.", "Mathlib.Data.Nat.", "Mathlib.Data.Int.", "Mathlib.Data.ZMod.",
                       "Mathlib.Data.Rat.")),
    ("algebra", ("Mathlib.Algebra.", "Mathlib.GroupTheory.")),
]

_IMPORT = re.compile(r"^\s*(?:(?:public|private|meta)\s+)*import\s+(?:all\s+)?([A-Za-z0-9_.']+)", re.M)


def family_of(module: str) -> str | None:
    for fam, prefixes in FAMILIES:
        if module.startswith(prefixes):
            return fam
    return None


def module_path(module: str) -> Path:
    return MATHLIB_DIR / (module.replace(".", "/") + ".lean")


def import_graph() -> dict[str, list[str]]:
    """module -> Mathlib modules it imports, parsed from each file's header."""
    graph: dict[str, list[str]] = {}
    for path in (MATHLIB_DIR / "Mathlib").rglob("*.lean"):
        mod = ".".join(path.relative_to(MATHLIB_DIR).with_suffix("").parts)
        head = "\n".join(path.read_text(errors="ignore").splitlines()[:400])
        graph[mod] = [m for m in _IMPORT.findall(head) if m.startswith("Mathlib.")]
    return graph


def reverse_graph(graph: dict[str, list[str]]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = defaultdict(list)
    for mod, imps in graph.items():
        for imp in imps:
            rev[imp].append(mod)
    return rev


def downstream(rev: dict[str, list[str]], module: str, cap: int | None = None) -> set[str]:
    """Modules that transitively import `module`. Stops early past `cap`."""
    seen: set[str] = set()
    q = deque(rev.get(module, ()))
    while q:
        m = q.popleft()
        if m in seen:
            continue
        seen.add(m)
        if cap is not None and len(seen) > cap:
            break
        q.extend(rev.get(m, ()))
    return seen


def split_signature(name: str, signature: str) -> tuple[str, str] | None:
    """`Name.{u} (a : A) [C a] : T` -> ("(a : A) [C a]", "T"), whitespace-normalised."""
    if not signature.startswith(name):
        return None
    rest = signature[len(name):]
    if rest.startswith(".{"):
        close = rest.find("}")
        if close < 0:
            return None
        rest = rest[close + 1:]
    rest = re.sub(r"\s*\n\s*", " ", rest).strip()
    depth = 0
    for i, ch in enumerate(rest):
        if ch in "([{⦃⟨":
            depth += 1
        elif ch in ")]}⦄⟩":
            depth -= 1
        elif ch == ":" and depth == 0 and not rest.startswith(":=", i):
            return rest[:i].strip(), rest[i + 1:].strip()
    return None


def statement_of(binders: str, typ: str) -> str:
    return f"{binders} : {typ}" if binders else f": {typ}"


def roundtrip_command(binders: str, typ: str, name: str) -> str:
    """Lean command that type-checks only if the rendered statement is the original theorem's type."""
    forall = f"∀ {binders}, {typ}" if binders else typ
    return f"example : {forall} := @{name}"


def _is_tactic_module(module: str) -> bool:
    """Tactic implementation modules. Umbrella files (`Mathlib`, `Mathlib.Tactic`) declare nothing."""
    return module.startswith("Mathlib.Tactic.")


def _ok_name(name: str) -> bool:
    last = name.rsplit(".", 1)[-1]
    return not (last.startswith("_") or "._" in name or re.search(r"\.(eq|proof|match)_\d+$", name))


def build_candidates(premises_path: Path = CORPUS / "premises.jsonl") -> dict:
    """Pick near-leaf modules per family and sample candidate theorems from them."""
    graph = import_graph()
    rev = reverse_graph(graph)
    by_module: dict[str, list[dict]] = defaultdict(list)
    with premises_path.open() as f:
        for ln in f:
            d = json.loads(ln)
            fam = family_of(d["module"])
            if fam is None or not _ok_name(d["name"]):
                continue
            parts = split_signature(d["name"], d["signature"])
            if parts is None:
                continue
            stmt = statement_of(*parts)
            if len(stmt) > MAX_STATEMENT_CHARS or "⋯" in stmt or "sorry" in stmt:
                continue
            by_module[d["module"]].append({**d, "family": fam, "binders": parts[0], "type": parts[1],
                                           "statement": stmt})

    rng = random.Random(SEED)
    eligible: dict[str, list[str]] = defaultdict(list)
    down_sizes: dict[str, int] = {}
    for mod, thms in by_module.items():
        if len(thms) < 4:
            continue
        down = downstream(rev, mod, cap=MAX_DOWNSTREAM)
        if len(down) <= MAX_DOWNSTREAM and not any(_is_tactic_module(m) for m in down):
            eligible[thms[0]["family"]].append(mod)
            down_sizes[mod] = len(down)

    # Every eligible module goes to dev or test as a unit; all its theorems stay candidates.
    # Balanced sampling happens later (build.select_heldout), after Lean-side filtering.
    candidates, module_split = [], {}
    for fam, _ in FAMILIES:
        mods = sorted(eligible[fam])
        rng.shuffle(mods)
        n_dev = round(len(mods) * DEV_MODULE_FRACTION) if len(mods) >= 3 else 0
        for i, mod in enumerate(mods):
            split = "dev" if i < n_dev else "test"
            banned = sorted({mod} | downstream(rev, mod))
            for d in sorted(by_module[mod], key=lambda d: d["name"]):
                candidates.append({**d, "split_role": split, "banned_modules": banned,
                                   "downstream": down_sizes[mod]})
            module_split[mod] = split
    return {"candidates": candidates, "module_split": module_split,
            "eligible_counts": {f: len(m) for f, m in eligible.items()},
            "n_modules_total": len(graph)}


if __name__ == "__main__":
    out = build_candidates()
    CORPUS.mkdir(exist_ok=True)
    with (CORPUS / "candidates.jsonl").open("w") as f:
        for c in out["candidates"]:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    (CORPUS / "candidates.txt").write_text("".join(c["name"] + "\n" for c in out["candidates"]))
    (CORPUS / "module_split.json").write_text(json.dumps(out["module_split"], indent=1, sort_keys=True))
    fams = defaultdict(lambda: defaultdict(int))
    for c in out["candidates"]:
        fams[c["family"]][c["split_role"]] += 1
    print("modules in Mathlib:", out["n_modules_total"])
    print("eligible near-leaf modules per family:", out["eligible_counts"])
    print("candidates:", len(out["candidates"]), {f: dict(v) for f, v in fams.items()})
