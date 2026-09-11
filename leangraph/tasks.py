"""Benchmark task schema and loader."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = ROOT / "corpus" / "tasks.jsonl"


@dataclass(frozen=True)
class Task:
    id: str
    statement: str  # binders and type, i.e. everything after the theorem name
    opens: str = ""  # space-separated namespaces opened for this theorem only
    family: str = ""  # algebra | inequalities | sets | functions | number_theory | probability | category_theory
    difficulty: str = ""  # easy | medium | hard
    split: str = ""  # mathlib_heldout | novel
    source: str = ""  # original Mathlib declaration name, or "authored"
    module: str = ""
    reference_proof: str = ""
    banned_modules: frozenset[str] = frozenset()
    banned_constants: frozenset[str] = frozenset()
    gt_premises: tuple[str, ...] = ()  # premises used by the reference proof (retrieval ground truth)
    features: dict = field(default_factory=dict, hash=False, compare=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["banned_modules"] = sorted(self.banned_modules)
        d["banned_constants"] = sorted(self.banned_constants)
        d["gt_premises"] = list(self.gt_premises)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        d = dict(d)
        d["banned_modules"] = frozenset(d.get("banned_modules", ()))
        d["banned_constants"] = frozenset(d.get("banned_constants", ()))
        d["gt_premises"] = tuple(d.get("gt_premises", ()))
        return cls(**d)


def load_tasks(path: Path | None = None) -> list[Task]:
    path = path or TASKS_PATH
    return [Task.from_dict(json.loads(ln)) for ln in path.read_text().splitlines() if ln.strip()]


def save_tasks(tasks: list[Task], path: Path | None = None) -> None:
    path = path or TASKS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(t.to_dict(), ensure_ascii=False) + "\n" for t in tasks))
