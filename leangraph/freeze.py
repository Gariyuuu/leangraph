"""Freeze a run's canonical results, or check that nothing frozen has changed.

    python -m leangraph.freeze --run-id main          # write results/FROZEN_<run_id>.json
    python -m leangraph.freeze --run-id main --check  # exit 1 if any frozen file differs

The manifest pins, by SHA-256: the task list, the authored-proof certificates, every trace
file of the run, the analysis summary, the retrieval summary, and every cached model
response. The response cache is also packed into one archive for release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(run_id: str) -> list[Path]:
    fixed = [ROOT / "corpus" / "tasks.jsonl", ROOT / "corpus" / "novel_verified.jsonl",
             ROOT / "corpus" / "tasks_summary.json", ROOT / "results" / "analysis" / run_id / "summary.json",
             ROOT / "results" / "retrieval" / "summary.json", ROOT / "lean_env" / "lake-manifest.json",
             ROOT / "lean_env" / "lean-toolchain", ROOT / "lean_env" / "repl.commit"]
    runs = sorted(p for p in (ROOT / "results" / "runs" / run_id).glob("*.jsonl") if not p.name.endswith(".harness_errors.jsonl"))
    return [p for p in fixed + runs if p.exists()]


def _cache_digest() -> tuple[int, str]:
    """Order-independent digest of the response cache: hash of sorted (name, sha) pairs."""
    cache = ROOT / "results" / "llm_cache"
    entries = sorted((p.name, _sha(p)) for p in cache.rglob("*.json")) if cache.exists() else []
    return len(entries), hashlib.sha256(json.dumps(entries).encode()).hexdigest()


def manifest(run_id: str) -> dict:
    files = {str(p.relative_to(ROOT)): {"sha256": _sha(p), "lines": sum(1 for _ in p.open())} for p in _files(run_id)}
    n, digest = _cache_digest()
    return {"run_id": run_id, "files": files, "llm_cache": {"responses": n, "digest": digest}}


def unresolved_harness_errors(run_id: str) -> dict[str, int]:
    from . import analyze
    analyze.RUNS = ROOT / "results" / "runs"
    analyze.load_traces(run_id)
    return {k: v for k, v in analyze.HARNESS_ERRORS.items() if v}


def freeze(run_id: str) -> Path:
    bad = unresolved_harness_errors(run_id)
    if bad:
        raise SystemExit(f"refusing to freeze {run_id}: tasks with only harness-error traces: {bad}. Resume the run first.")
    m = manifest(run_id)
    out = ROOT / "results" / f"FROZEN_{run_id}.json"
    out.write_text(json.dumps(m, indent=1, sort_keys=True))
    cache = ROOT / "results" / "llm_cache"
    if cache.exists():
        rel = ROOT / "results" / "release"
        rel.mkdir(parents=True, exist_ok=True)
        with tarfile.open(rel / f"llm_cache_{run_id}.tar.gz", "w:gz") as tar:
            tar.add(cache, arcname="llm_cache")
    return out


def check(run_id: str) -> list[str]:
    frozen = json.loads((ROOT / "results" / f"FROZEN_{run_id}.json").read_text())
    now = manifest(run_id)
    problems = [f"changed: {k}" for k, v in frozen["files"].items() if now["files"].get(k, {}).get("sha256") != v["sha256"]]
    problems += [f"new file not in manifest: {k}" for k in now["files"] if k not in frozen["files"]]
    if now["llm_cache"] != frozen["llm_cache"]:
        problems.append(f"llm cache changed: {frozen['llm_cache']} -> {now['llm_cache']}")
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="main")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        probs = check(a.run_id)
        print("\n".join(probs) or f"FROZEN_{a.run_id}.json matches")
        sys.exit(1 if probs else 0)
    print("wrote", freeze(a.run_id))
