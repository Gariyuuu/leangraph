"""Lean verification for LeanGraph.

Two tiers, deliberately separate:

* ``ReplWorker`` keeps one Lean REPL process alive with Mathlib imported, so a
  proof attempt costs well under a second. It is a *search* tool only.
* ``certify`` compiles a standalone file in a fresh ``lean`` process and
  inspects the finished declaration: axioms, constants used, and any extra
  declarations. It is the *judge*: a proof counts as verified only if it
  passes here.

The model never writes the theorem header. We render it from the benchmark
statement, so the statement cannot be changed. Indentation alone does NOT stop
a model from appending top-level commands (Lean ends a tactic block at a
command keyword), so we (a) reject command keywords in proof text and (b) have
the certifier print its findings under a per-run random nonce, which text the
model wrote before the nonce existed cannot forge.
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import textwrap
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEAN_ENV = ROOT / "lean_env"
REPL_BIN = ROOT / ".lean_repl" / ".lake" / "build" / "bin" / "repl"
ELAN_BIN = Path.home() / ".elan" / "bin"
CERT_DIR = ROOT / "results" / ".certify"

HEADER = "import Mathlib"
TARGET_NAME = "lg_target"
HEARTBEATS = 200_000  # Lean's default budget: deterministic and machine-independent
WALL_TIMEOUT_S = 60.0  # backstop only; the heartbeat limit should fire first
STANDARD_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

_COMMANDS = (
    "example|theorem|lemma|def|abbrev|instance|attribute|namespace|section|noncomputable|"
    "universe|variable|import|structure|class|inductive|opaque|mutual|initialize|builtin_initialize|"
    "export|deriving|omit|include|private|protected"
)

# Tokens that let a proof "succeed" without proving anything, buy extra budget,
# or add commands after the theorem.
FORBIDDEN_PATTERNS = {
    "sorry": r"\bsorry(Ax)?\b",
    "admit": r"\badmit\b",
    "axiom": r"\baxiom\b",
    "native_decide": r"\bnative_decide\b",
    "unsafe": r"\bunsafe\b",
    "implemented_by": r"\bimplemented_by\b",
    "extern": r"@\[\s*extern",
    "set_option": r"\bset_option\b",
    "run_tac": r"\brun_tac\b",
    "metaprogramming": r"\b(elab|elab_rules|macro|macro_rules|syntax|notation|infix|infixl|infixr|postfix|declare_syntax_cat)\b",
    # `open Foo in tac` is a legitimate tactic; a bare `open` line is a command.
    "command": rf"(?m)^\s*(#[A-Za-z_]+|(?:{_COMMANDS})\b|open\b(?!.*\bin\b))",
}


def lean_env_vars() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{ELAN_BIN}:{env.get('PATH', '')}"
    return env


def forbidden_tokens(proof: str, allow_sorry: bool = False) -> list[str]:
    return [
        name for name, pat in FORBIDDEN_PATTERNS.items()
        if not (allow_sorry and name == "sorry") and re.search(pat, proof)
    ]


def clean_proof(raw: str) -> str:
    """Extract a tactic block from model output.

    Strips code fences, a restated theorem header, and a leading ``by``.
    Nothing else is rewritten: the model's tactics reach Lean verbatim.
    """
    text = raw.strip()
    fences = re.findall(r"```[ \t]*(?:lean4?|Lean4?)?[ \t]*\n(.*?)```", text, re.S)
    if fences:
        text = fences[-1]
    header = re.search(r"^\s*(?:theorem|lemma|example)\b.*?:=\s*by\b(.*)$", text, re.S)
    if header:
        text = header.group(1)
    # A restated tail of the header (`:= by`, `:=by`, `by`) is header, not tactics.
    text = re.sub(r"^\s*(?::=\s*)?by\b[ \t]*", "", text, count=1)
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return textwrap.dedent("\n".join(lines))


PREAMBLE_LINES = 2  # the two `set_option ... in` lines emitted by `render`


def render(statement: str, proof: str, opens: str = "", name: str = TARGET_NAME) -> str:
    """Build the theorem source. ``opens`` is a space-separated namespace list."""
    body = "\n".join(("  " + ln) if ln.strip() else "" for ln in proof.splitlines()) or "  skip"
    open_line = f"open {opens} in\n" if opens.strip() else ""
    return (
        f"set_option maxHeartbeats {HEARTBEATS} in\n"
        f"set_option linter.unusedVariables false in\n"
        f"{open_line}theorem {name} {statement} := by\n{body}\n"
    )


@dataclass
class LeanMessage:
    severity: str
    line: int
    col: int
    text: str


@dataclass
class CheckResult:
    ok: bool
    code: str
    messages: list[LeanMessage] = field(default_factory=list)
    has_sorry: bool = False
    forbidden: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    timed_out: bool = False
    crashed: bool = False

    @property
    def errors(self) -> list[LeanMessage]:
        return [m for m in self.messages if m.severity == "error"]

    def compiler_output(self) -> str:
        """Exactly what Lean reported, in `line:col: severity: text` form."""
        if self.forbidden:
            return "rejected before compilation: forbidden token(s): " + ", ".join(self.forbidden)
        if self.timed_out:
            return f"wall-clock timeout after {WALL_TIMEOUT_S:.0f}s"
        if self.crashed:
            return "Lean process crashed"
        return "\n".join(f"{m.line}:{m.col}: {m.severity}: {m.text}" for m in self.messages)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["compiler_output"] = self.compiler_output()
        return d


class ReplWorker:
    """One long-lived Lean REPL with Mathlib imported. Not thread-safe; use one per thread."""

    def __init__(self, header: str = HEADER, wall_timeout: float = WALL_TIMEOUT_S):
        self.header = header
        self.wall_timeout = wall_timeout
        self.proc: subprocess.Popen | None = None
        self.base_env: int | None = None
        self.import_seconds: float | None = None
        self.restarts = 0
        self._lines: queue.Queue[str | None] = queue.Queue()

    def start(self) -> None:
        self.proc = subprocess.Popen(
            ["lake", "env", str(REPL_BIN)],
            cwd=LEAN_ENV,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=lean_env_vars(),
            bufsize=1,
            start_new_session=True,
        )
        self._lines = queue.Queue()
        threading.Thread(target=self._pump, args=(self.proc, self._lines), daemon=True).start()
        t0 = time.time()
        resp = self._send({"cmd": self.header}, timeout=3600)
        if resp is None or "env" not in resp:
            raise RuntimeError(f"REPL failed to import header: {resp}")
        self.base_env = resp["env"]
        self.import_seconds = time.time() - t0

    @staticmethod
    def _pump(proc: subprocess.Popen, out: queue.Queue) -> None:
        for line in proc.stdout:  # type: ignore[union-attr]
            out.put(line)
        out.put(None)

    def _send(self, obj: dict, timeout: float) -> dict | None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(json.dumps(obj) + "\n\n")
        self.proc.stdin.flush()
        deadline = time.time() + timeout
        buf = ""
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                return None
            if line is None:
                raise EOFError("REPL exited")
            if line.strip() == "" and buf.strip():
                return json.loads(buf)
            buf += line

    def restart(self) -> None:
        self.close()
        self.restarts += 1
        self.start()

    def close(self) -> None:
        if self.proc:
            try:
                os.killpg(self.proc.pid, 9)  # lake env spawns the repl as a child
            except ProcessLookupError:
                pass
            self.proc.wait()
            self.proc = None

    def run_command(self, cmd: str, timeout: float | None = None) -> dict | None:
        """Run a trusted command (corpus construction only) in the base environment."""
        if self.proc is None:
            self.start()
        try:
            resp = self._send({"cmd": cmd, "env": self.base_env}, timeout=timeout or self.wall_timeout)
        except (EOFError, BrokenPipeError, json.JSONDecodeError):
            self.restart()
            return None
        if resp is None:
            self.restart()
        return resp

    def check(self, statement: str, proof: str, opens: str = "", allow_sorry: bool = False) -> CheckResult:
        """Search-time check. `allow_sorry` is only for planner skeletons, never for final proofs."""
        code = render(statement, proof, opens)
        forb = forbidden_tokens(proof, allow_sorry=allow_sorry)
        if forb:
            return CheckResult(ok=False, code=code, forbidden=forb)
        if self.proc is None:
            self.start()
        t0 = time.time()
        try:
            resp = self._send({"cmd": code, "env": self.base_env}, timeout=self.wall_timeout)
        except (EOFError, BrokenPipeError, json.JSONDecodeError):
            self.restart()
            return CheckResult(ok=False, code=code, crashed=True, elapsed_s=time.time() - t0)
        elapsed = time.time() - t0
        if resp is None:
            self.restart()
            return CheckResult(ok=False, code=code, timed_out=True, elapsed_s=elapsed)
        msgs = [
            LeanMessage(m.get("severity", "info"), m["pos"]["line"], m["pos"]["column"], m.get("data", ""))
            for m in resp.get("messages", [])
        ]
        has_sorry = bool(resp.get("sorries")) or any("declaration uses 'sorry'" in m.text for m in msgs)
        ok = not any(m.severity == "error" for m in msgs) and (allow_sorry or not has_sorry)
        return CheckResult(ok=ok, code=code, messages=msgs, has_sorry=has_sorry, elapsed_s=elapsed)


def _probe(nonce: str) -> str:
    """Lean code that reports on the finished target under an unforgeable nonce."""
    return f"""
open Lean in
#eval show MetaM Unit from do
  let env ← getEnv
  for (n, _) in env.constants.map₂.toList do
    IO.println s!"{nonce} DECL {{n}}"
  for a in (← collectAxioms `{TARGET_NAME}) do
    IO.println s!"{nonce} AXIOM {{a}}"
  let mut todo : Array Name := #[`{TARGET_NAME}]
  let mut seen : NameSet := {{}}
  while !todo.isEmpty do
    let n := todo.back!
    todo := todo.pop
    if seen.contains n then continue
    seen := seen.insert n
    let some ci := env.find? n | continue
    let some v := ci.value? (allowOpaque := true) | continue
    for c in v.getUsedConstants do
      if (`{TARGET_NAME}).isPrefixOf c then
        todo := todo.push c
      else
        let m := match env.getModuleIdxFor? c with
          | some i => toString (env.header.moduleNames[i.toNat]!)
          | none => "_"
        IO.println s!"{nonce} USES {{c}} {{m}}"
  IO.println "{nonce} DONE"
"""


@dataclass
class Certificate:
    verified: bool
    reason: str
    axioms: list[str]
    used_constants: list[tuple[str, str]]
    banned_used: list[str]
    extra_decls: list[str]
    stdout: str
    elapsed_s: float
    lean_returncode: int

    def to_dict(self) -> dict:
        return asdict(self)


def certify(
    statement: str,
    proof: str,
    opens: str = "",
    banned_modules: frozenset[str] = frozenset(),
    banned_constants: frozenset[str] = frozenset(),
    timeout: float = 600.0,
) -> Certificate:
    """Judge a proof in a fresh Lean process. The only path to `verified=True`."""
    t0 = time.time()
    forb = forbidden_tokens(proof)
    if forb:
        return Certificate(False, "forbidden:" + ",".join(forb), [], [], [], [], "", 0.0, -1)
    nonce = "LG" + uuid.uuid4().hex
    code = f"{HEADER}\n\n{render(statement, proof, opens)}\n{_probe(nonce)}"
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    path = CERT_DIR / f"cert_{nonce}.lean"
    path.write_text(code)
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(path)],
            cwd=LEAN_ENV, capture_output=True, text=True, timeout=timeout, env=lean_env_vars(),
        )
        out, rc = proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return Certificate(False, "timeout", [], [], [], [], "", time.time() - t0, -1)
    finally:
        path.unlink(missing_ok=True)
    elapsed = time.time() - t0

    tagged = [ln[len(nonce) + 1:] for ln in out.splitlines() if ln.startswith(nonce + " ")]
    axioms = [ln.split(" ", 1)[1] for ln in tagged if ln.startswith("AXIOM ")]
    uses = [tuple(ln.split()[1:3]) for ln in tagged if ln.startswith("USES ")]
    decls = [ln.split(" ", 1)[1] for ln in tagged if ln.startswith("DECL ")]
    extra = sorted(d for d in decls if not d.startswith(TARGET_NAME) and not any(p.startswith("_") for p in d.split(".")))
    banned = sorted({c for c, mod in uses if c in banned_constants or mod in banned_modules})

    def fail(reason: str) -> Certificate:
        return Certificate(False, reason, axioms, uses, banned, extra, out, elapsed, rc)

    if re.search(r":\d+:\d+: error", out) or rc != 0:
        return fail("lean_error")
    if "declaration uses 'sorry'" in out:
        return fail("sorry")
    if "DONE" not in tagged or TARGET_NAME not in decls:
        return fail("probe_incomplete")
    if extra:
        return fail("extra_declarations:" + ",".join(extra))
    if not set(axioms) <= STANDARD_AXIOMS:
        return fail("nonstandard_axioms:" + ",".join(sorted(set(axioms) - STANDARD_AXIOMS)))
    if banned:
        return fail("banned_premise:" + ",".join(banned))
    return Certificate(True, "ok", axioms, uses, banned, extra, out, elapsed, rc)
