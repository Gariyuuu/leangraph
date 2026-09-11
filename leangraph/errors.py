"""Error taxonomy for failed proof attempts, derived only from Lean's messages.

Each error message gets one class. An attempt's primary class is that of its
first parse error if it has one (the rest of its errors follow from Lean not
parsing what the model wrote), otherwise that of its first error. Unknown names are split into *wrong namespace* (the name exists in
Mathlib under another namespace or capitalisation, e.g. Lean 3 `real.sqrt` for
`Real.sqrt`) and *hallucinated theorem* (nothing close exists), by lookup in the
full constant table dumped from the pinned Mathlib, never by guesswork.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES_PATH = ROOT / "corpus" / "all_names.txt"

CLASSES = [
    "hallucinated_theorem", "wrong_namespace", "lean3_syntax", "syntax_error", "type_mismatch",
    "unresolved_metavariable", "instance_resolution_failure", "incorrect_rewrite", "bad_induction",
    "wrong_tactic", "valid_but_wrong", "timeout", "forbidden", "no_proof", "checker_rejected", "other",
]

# First match wins. Patterns were written against Lean 4.33 message text.
_PATTERNS: list[tuple[str, str]] = [
    ("timeout", r"deterministic\) timeout|maximum number of heartbeats|wall-clock timeout|maximum recursion depth"),
    ("forbidden", r"^rejected before compilation"),
    ("no_proof", r"^\(no proof found"),
    ("checker_rejected", r"^The proof was rejected by the final checker"),
    ("unknown_name", r"[Uu]nknown (identifier|constant)|does not contain|unknown namespace"),
    ("syntax_error", r"(?<!un)expected token|unexpected token|unexpected identifier|expected term|expected ':='|unknown tactic|"
                     r"unterminated|missing end of|expected '\)'|expected command"),
    ("instance_resolution_failure", r"failed to synthesize"),
    ("incorrect_rewrite", r"did not find instance of the pattern|motive is not type correct|"
                          r"equality or iff proof expected|rewrite.*failed|did not find.*pattern"),
    ("unresolved_metavariable", r"don't know how to synthesize|typeclass instance problem is stuck|"
                                r"contains metavariables|can't synthesize"),
    ("bad_induction", r"invalid alternative name|alternative '.*' (has not been provided|is not needed)|"
                      r"unused alternative|index in target's type is not a variable|induction.*failed|"
                      r"major premise type is not an inductive type"),
    ("type_mismatch", r"type mismatch|application type mismatch|has type.*but is expected to have type|"
                      r"is expected to have type|function expected|invalid field notation|Invalid simp theorem|"
                      r"Expected a proposition"),
    ("wrong_tactic", r"linarith failed|nlinarith failed|omega could not|simp made no progress|positivity failed|"
                     r"norm_num failed|ring failed|ring_nf failed|decide failed|failed to prove|aesop: failed|"
                     r"rfl.*failed|grind failed|could not close|failed to close|no progress|exact\? could not|"
                     r"Tactic `.*` failed|tactic '.*' failed|not a positivity goal|The rfl tactic"),
    ("valid_but_wrong", r"unsolved goals"),
]
_COMPILED = [(c, re.compile(p, re.S)) for c, p in _PATTERNS]
PARSE_CLASSES = ("lean3_syntax", "syntax_error")
# Lean 3 markers: block syntax, term syntax, tactic names that no longer exist, lowercase Mathlib 3 namespaces.
_LEAN3 = re.compile(
    r"\bbegin\b|^\s*end\s*,?\s*$|\bassume\b|λ\s*[\w\s]+,|\bcases\s+\S+\s+with\s+\w|\{\s*(norm_num|simp|linarith)\b.*\}"
    r"|\b(apply_instance|reflexivity|refl|symmetry|transitivity|existsi|dec_trivial|library_search|tidy|finish|obviously|unfold_coes)\b"
    r"|\b(nat|int|real|rat|complex|finset|set|list|multiset|measure_theory|topological_space|category_theory|linear_map|polynomial"
    r"|filter|metric|function)\.[a-z_]", re.M)
_NAME_IN_MSG = re.compile(r"[Uu]nknown (?:identifier|constant) [`'‘]?([^\s`'’]+)|does not contain [`'‘]?([^\s`'’]+)")


@lru_cache(maxsize=1)
def _name_tables() -> tuple[frozenset[str], dict[str, list[str]], dict[str, list[str]]]:
    names = frozenset(NAMES_PATH.read_text().split()) if NAMES_PATH.exists() else frozenset()
    lower: dict[str, list[str]] = {}
    last: dict[str, list[str]] = {}
    for n in names:
        lower.setdefault(n.lower(), []).append(n)
        last.setdefault(n.rsplit(".", 1)[-1], []).append(n)
    return names, lower, last


def resolve_unknown(name: str) -> tuple[str, str | None]:
    """Classify an unknown name and return the real constant it was probably meant to be."""
    names, lower, last = _name_tables()
    name = name.strip("`'‘’.,:")
    if name.lower() in lower:
        return "wrong_namespace", lower[name.lower()][0]
    tail = name.rsplit(".", 1)[-1]
    if "." in name and tail in last:
        return "wrong_namespace", sorted(last[tail], key=len)[0]
    if tail.lower() in lower:
        return "wrong_namespace", lower[tail.lower()][0]
    return "hallucinated_theorem", None


def classify_message(text: str, proof: str = "") -> dict:
    for cls, rx in _COMPILED:
        if rx.search(text):
            if cls == "unknown_name":
                m = _NAME_IN_MSG.search(text)
                missing = (m.group(1) or m.group(2)) if m else ""
                resolved_cls, suggestion = resolve_unknown(missing) if missing else ("hallucinated_theorem", None)
                return {"class": resolved_cls, "missing_name": missing, "suggestion": suggestion}
            if cls == "syntax_error" and _LEAN3.search(proof):
                return {"class": "lean3_syntax"}
            return {"class": cls}
    return {"class": "other"}


def classify_attempt(attempt: dict) -> dict:
    """Primary class (first error) plus every error's class for one attempt in a trace."""
    proof = attempt.get("proof", "")
    msgs = [m for m in attempt.get("messages", []) if m.get("severity") == "error"]
    if not msgs:
        out = attempt.get("compiler_output", "")
        info = classify_message(out, proof) if out else {"class": "other"}
        return {"primary": info["class"], "all": [info["class"]], "details": [info]}
    details = [classify_message(m["text"], proof) for m in msgs]
    classes = [d["class"] for d in details]
    # A parse error means Lean never elaborated the proof the model wrote; later errors (typically
    # "unsolved goals") are its consequences, so it takes precedence over position order.
    parse = next((c for c in classes if c in PARSE_CLASSES), None)
    return {"primary": parse or classes[0], "all": classes, "details": details}
