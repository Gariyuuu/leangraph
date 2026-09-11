"""Proof agents.

Every architecture is one configuration of a single loop, so differences between
conditions are differences in configuration, not in code paths:

  retrieval  lemmas retrieved for the statement are added to the prompt
  plan       a planning call runs before proving (optionally writing a Lean skeleton)
  rounds     compiler-feedback repair rounds after the first draft
  feedback   whether repair prompts include Lean's actual output
  memory     whether repair prompts show every earlier attempt or only the last
  samples    independent restarts; direct@K is the equal-budget control for repair

LLM draws are keyed by (prompt, sample, round), so conditions that send the same
prompt reuse the same draw. Repair's first draft *is* the direct baseline's
draft, which makes comparisons between conditions paired.

A proof counts only when `verify.certify` accepts it.
"""
from __future__ import annotations

import queue
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Callable

from . import llm
from .tasks import Task
from .verify import TARGET_NAME, ReplWorker, certify, clean_proof

PROMPT_VERSION = "v2"
LEAN_VERSION = "4.33.1"
MATHLIB_VERSION = "v4.33.1"
CERT_SEM = threading.BoundedSemaphore(2)

SYSTEM_PROVER = (
    f"You write formal proofs in Lean 4 (version {LEAN_VERSION}) with Mathlib ({MATHLIB_VERSION}). "
    "Use Lean 4 syntax and current Mathlib names; Lean 3 names with lowercase namespaces "
    "(such as `nat.` or `real.`) do not exist. Reply with the tactic proof only, meaning the part that "
    "goes after `:= by`, inside a single ```lean code block. Never use `sorry`."
)
# Prompt sets. "p1" (and its paraphrase "p2") were used for the demo and the first dev pilot and are
# kept so those traces stay interpretable. After that pilot, the primary prompt was revised on the dev
# split to name the Lean 3 habits the model kept using: "v2" is the primary prompt for every canonical
# run and "v2b" its paraphrase. Their text is pinned by tests because cached draws depend on it.
LEAN4_REMINDER = (
    "Lean 3 syntax and tactics do not work here: no `begin … end` blocks, no `assume`, no `λ x, …`, no "
    "`cases h with x y` (use `obtain ⟨x, y⟩ := h` or `rcases`), no `refl`/`reflexivity` (use `rfl`), no "
    "`apply_instance` (use `infer_instance`), no `split` for ∧ or ↔ (use `constructor`), and no lowercase "
    "namespaces such as `nat.` or `real.`."
)
PROMPTS = {
    "p1": {
        "system": None,  # SYSTEM_PROVER
        "ask": "Prove this theorem.",
        "lemmas": "Possibly relevant Mathlib lemmas (retrieved automatically; some may be irrelevant):",
        "failed_many": "Your earlier attempts failed:",
        "failed_one": "Your previous attempt failed:",
        "fix": "Write a corrected proof.",
        "answer": "Answer with the tactic proof only, in one ```lean block.",
    },
    "p2": {
        "system": (
            f"You are proving theorems in Lean 4, version {LEAN_VERSION}, using Mathlib {MATHLIB_VERSION}. "
            "Write Lean 4 code with the current Mathlib naming conventions; lowercase Lean 3 namespaces such as `nat.` "
            "or `real.` are not valid. Give only the tactics that follow `:= by`, wrapped in one ```lean fenced block. "
            "Do not use `sorry`."
        ),
        "ask": "Give a Lean proof of the following statement.",
        "lemmas": "These Mathlib lemmas were found by a search and might be useful (or not):",
        "failed_many": "The following attempts did not compile:",
        "failed_one": "The following attempt did not compile:",
        "fix": "Fix the proof.",
        "answer": "Reply with just the tactic proof inside a single ```lean block.",
    },
}
PROMPTS["v2"] = {**PROMPTS["p1"], "system": (
    f"You write formal proofs in Lean 4 (version {LEAN_VERSION}) with Mathlib ({MATHLIB_VERSION}). "
    "Use Lean 4 syntax and current Mathlib names. " + LEAN4_REMINDER + " Reply with the tactic proof only, meaning "
    "the part that goes after `:= by` (do not repeat `:= by`), inside a single ```lean code block. Never use `sorry`."
)}
PROMPTS["v2b"] = {**PROMPTS["p2"], "system": (
    f"You are proving theorems in Lean 4, version {LEAN_VERSION}, using Mathlib {MATHLIB_VERSION}. "
    "Write Lean 4 code with the current Mathlib naming conventions. " + LEAN4_REMINDER + " Give only the tactics "
    "that follow `:= by`, without repeating `:= by`, wrapped in one ```lean fenced block. Do not use `sorry`."
)}

SYSTEM_PLANNER = (
    f"You plan formal proofs in Lean 4 (version {LEAN_VERSION}) with Mathlib ({MATHLIB_VERSION}). "
    "Use Lean 4 syntax and current Mathlib names."
)

# No-LLM baseline: fixed automation, tried in order.
TEMPLATE_TACTICS = [
    "rfl", "decide", "norm_num", "simp", "ring", "linarith", "nlinarith", "positivity", "omega",
    "field_simp", "tauto", "simp_all", "aesop", "grind", "norm_num <;> linarith", "exact?",
]


MAX_TOKENS_NO_THINK = 2048
RESAMPLE_SEED_BASE = 1000
MAX_TOKENS_THINK = 6000


@dataclass(frozen=True)
class AgentConfig:
    name: str
    retrieval: str | None = None  # None | "bm25" | "dense" | "hybrid"
    k: int = 8
    plan: bool = False
    skeleton: bool = True
    rounds: int = 0
    feedback: bool = True
    memory: bool = True
    samples: int = 1
    think: bool = False
    prompt: str = "v2"

    @property
    def max_tokens(self) -> int:
        """Reply cap. Reasoning-off replies that reach 6,000 tokens are repetition loops and take ~2 minutes,
        past the gateway's ~100 s origin timeout (HTTP 524); 2,048 bounds them to ~40 s (dev pilot, 2026-09-10)."""
        return MAX_TOKENS_THINK if self.think else MAX_TOKENS_NO_THINK

    @property
    def max_llm_calls(self) -> int:
        return self.samples * (1 + self.rounds) + int(self.plan)


class WorkerPool:
    """A few REPL workers (each holds Mathlib in memory) shared by many LLM threads."""

    def __init__(self, n: int):
        self._q: queue.Queue[ReplWorker] = queue.Queue()
        workers = [ReplWorker() for _ in range(n)]
        threads = [threading.Thread(target=w.start) for w in workers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for w in workers:
            self._q.put(w)
        self.workers = workers

    @contextmanager
    def get(self):
        w = self._q.get()
        try:
            yield w
        finally:
            self._q.put(w)

    def close(self) -> None:
        for w in self.workers:
            w.close()


def theorem_header(task: Task) -> str:
    open_line = f"open {task.opens} in\n" if task.opens else ""
    return f"{open_line}theorem {TARGET_NAME} {task.statement} := by"


def _truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n] + "\n... (truncated)"


def _lemma_block(hits) -> str:
    return "\n".join(f"- {_truncate(h.signature, 300)}" for h in hits)


def _user(text: str, think: bool) -> str:
    return text if think else text + "\n/no_think"


def prove_messages(task: Task, cfg: AgentConfig, hits, plan: str | None, history: list[dict]) -> list[dict]:
    P = PROMPTS[cfg.prompt]
    parts = [f"{P['ask']}\n\n```lean\n{theorem_header(task)}\n```"]
    if hits:
        parts.append(P["lemmas"] + "\n" + _lemma_block(hits))
    if plan:
        parts.append(plan)
    if history:
        shown = history if cfg.memory else history[-1:]
        parts.append(P["failed_many"] if len(shown) > 1 else P["failed_one"])
        for a in shown:
            out = a["compiler_output"] if cfg.feedback else "(the proof did not compile)"
            parts.append(f"```lean\n{a['code'].rstrip()}\n```\nLean output:\n```\n{_truncate(out, 1500)}\n```")
        parts.append(P["fix"])
    parts.append(P["answer"])
    return [{"role": "system", "content": P["system"] or SYSTEM_PROVER},
            {"role": "user", "content": _user("\n\n".join(parts), cfg.think)}]


def plan_messages(task: Task, cfg: AgentConfig, hits) -> list[dict]:
    parts = [f"Here is a theorem to prove in Lean 4.\n\n```lean\n{theorem_header(task)}\n```"]
    if hits:
        parts.append("Possibly relevant Mathlib lemmas (retrieved automatically; some may be irrelevant):\n" + _lemma_block(hits))
    if cfg.skeleton:
        parts.append("Do not write the full proof yet. First explain in a few sentences how the proof goes. "
                     "Then give a Lean proof skeleton: a tactic proof whose key intermediate steps are `have` "
                     "statements, each proved by `sorry`, inside one ```lean block.")
    else:
        parts.append("Do not write any Lean code. Explain in a few sentences how the proof goes.")
    return [{"role": "system", "content": SYSTEM_PLANNER},
            {"role": "user", "content": _user("\n\n".join(parts), cfg.think)}]


def _new_usage() -> dict:
    return {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
            "cost_usd": 0.0, "llm_latency_s": 0.0, "lean_checks": 0, "lean_check_s": 0.0, "certify_s": 0.0}


def run_task(
    task: Task,
    cfg: AgentConfig,
    pool: WorkerPool,
    retrieve: Callable[[Task, str, int], list] | None = None,
    offline: bool = False,
) -> dict:
    """Run one agent configuration on one task and return the full trace."""
    t_start = time.time()
    usage = _new_usage()
    trace: dict = {
        "task_id": task.id, "config": {**asdict(cfg), "max_tokens": cfg.max_tokens}, "prompt_version": cfg.prompt,
        "model": llm.llm_config()["model"], "lean": LEAN_VERSION, "mathlib": MATHLIB_VERSION,
        "retrieved": [], "plan": None, "attempts": [], "verified": False, "final_proof": None,
        "certificate": None, "usage": usage,
    }

    def call(messages: list[dict], sample: int) -> llm.Completion:
        # The gateway's generation is nearly deterministic for a given request (DECISIONS 2026-09-11), so a
        # resampled draw (sample index > 0) must send its own seed to be an independent sample. First drafts and
        # repair rounds send no seed, so their requests and cache keys are exactly as before.
        s_idx = sample // 100
        seed = RESAMPLE_SEED_BASE + s_idx if s_idx > 0 else None
        c = llm.chat(messages, sample=sample, offline=offline, max_tokens=cfg.max_tokens, seed=seed)
        usage["llm_calls"] += 1
        usage["prompt_tokens"] += c.prompt_tokens
        usage["completion_tokens"] += c.completion_tokens
        usage["reasoning_tokens"] += c.reasoning_tokens
        usage["cost_usd"] += c.cost_usd or 0.0
        usage["llm_latency_s"] += c.latency_s
        return c

    hits = retrieve(task, cfg.retrieval, cfg.k) if (cfg.retrieval and retrieve) else []
    trace["retrieved"] = [h.name for h in hits]

    plan_text = None
    if cfg.plan:
        c = call(plan_messages(task, cfg, hits), sample=0)
        skeleton = clean_proof(c.text) if (cfg.skeleton and "```" in c.text) else None
        informal = re.sub(r"```.*?```", "", c.text, flags=re.S).strip()
        plan_rec = {"informal": informal, "skeleton": skeleton, "skeleton_ok": None,
                    "skeleton_output": None, "llm_key": c.key}
        plan_text = "Proof plan:\n" + _truncate(informal, 1500)
        if skeleton:
            with pool.get() as w:
                r = w.check(task.statement, skeleton, task.opens, allow_sorry=True)
            usage["lean_checks"] += 1
            usage["lean_check_s"] += r.elapsed_s
            plan_rec.update(skeleton_ok=r.ok, skeleton_output=r.compiler_output())
            status = "Lean accepts this skeleton (only the `sorry` steps remain)." if r.ok else \
                "Lean reports problems with this skeleton:\n" + _truncate(r.compiler_output(), 800)
            plan_text += f"\n\nProof skeleton:\n```lean\n{skeleton}\n```\n{status}\n" \
                         "Your final proof must replace every `sorry` with a real proof."
        trace["plan"] = plan_rec

    for s in range(cfg.samples):
        history: list[dict] = []
        for rnd in range(cfg.rounds + 1):
            c = call(prove_messages(task, cfg, hits, plan_text, history), sample=s * 100 + rnd)
            proof = clean_proof(c.text)
            att = {"sample": s, "round": rnd, "llm_key": c.key, "raw": c.text, "proof": proof,
                   "finish_reason": c.finish_reason, "completion_tokens": c.completion_tokens,
                   "latency_s": c.latency_s, "repl_ok": False, "certificate": None}
            if not proof.strip():
                att.update(code="", compiler_output="(no proof found in the model's reply)", messages=[])
            else:
                with pool.get() as w:
                    r = w.check(task.statement, proof, task.opens)
                usage["lean_checks"] += 1
                usage["lean_check_s"] += r.elapsed_s
                att.update(code=r.code, compiler_output=r.compiler_output(), repl_ok=r.ok, lean_s=r.elapsed_s,
                           messages=[asdict(m) for m in r.messages], timed_out=r.timed_out,
                           forbidden=r.forbidden)
                if r.ok:
                    with CERT_SEM:
                        cert = certify(task.statement, proof, task.opens,
                                       banned_modules=task.banned_modules, banned_constants=task.banned_constants)
                    usage["certify_s"] += cert.elapsed_s
                    cd = cert.to_dict()
                    cd.pop("stdout")
                    att["certificate"] = cd
                    if cert.verified:
                        trace["attempts"].append(att)
                        trace.update(verified=True, final_proof=proof, certificate=cd,
                                     solved_at={"sample": s, "round": rnd, "llm_calls": usage["llm_calls"]})
                        trace["wall_s"] = time.time() - t_start
                        return trace
                    att["compiler_output"] = f"The proof was rejected by the final checker: {cert.reason}"
            trace["attempts"].append(att)
            history.append(att)
    trace["wall_s"] = time.time() - t_start
    return trace


def run_template(task: Task, pool: WorkerPool) -> dict:
    """No-LLM baseline: try each automation tactic; certify the first that passes."""
    t_start = time.time()
    usage = _new_usage()
    trace = {"task_id": task.id, "config": {"name": "template"}, "prompt_version": None, "model": None,
             "lean": LEAN_VERSION, "mathlib": MATHLIB_VERSION, "retrieved": [], "plan": None,
             "attempts": [], "verified": False, "final_proof": None, "certificate": None, "usage": usage}
    for tac in TEMPLATE_TACTICS:
        with pool.get() as w:
            r = w.check(task.statement, tac, task.opens)
        usage["lean_checks"] += 1
        usage["lean_check_s"] += r.elapsed_s
        att = {"proof": tac, "repl_ok": r.ok, "compiler_output": r.compiler_output()[:600], "certificate": None,
               "lean_s": r.elapsed_s, "timed_out": r.timed_out}
        if r.ok:
            with CERT_SEM:
                cert = certify(task.statement, tac, task.opens,
                               banned_modules=task.banned_modules, banned_constants=task.banned_constants)
            usage["certify_s"] += cert.elapsed_s
            cd = cert.to_dict()
            cd.pop("stdout")
            att["certificate"] = cd
            trace["attempts"].append(att)
            if cert.verified:
                trace.update(verified=True, final_proof=tac, certificate=cd)
                break
        else:
            trace["attempts"].append(att)
    trace["wall_s"] = time.time() - t_start
    return trace
