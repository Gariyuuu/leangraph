"""OpenAI-compatible chat client with a content-addressed response cache.

Every call is cached on disk under a hash of (model, messages, params, sample).
Re-running the benchmark replays cached responses, so frozen results are
reproducible and nothing is billed twice.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "results" / "llm_cache"


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def llm_config() -> dict[str, str]:
    """LG_LLM_* env vars win; else repo `.env`; else the workspace `.env.local` YUU_AI_* keys."""
    file_env = _read_env_file(ROOT / ".env")
    ws_env = _read_env_file(ROOT.parent / ".env.local")

    def pick(lg: str, yuu: str) -> str:
        return os.environ.get(lg) or file_env.get(lg) or ws_env.get(yuu, "")

    return {
        "base_url": pick("LG_LLM_BASE_URL", "YUU_AI_BASE_URL").rstrip("/"),
        "api_key": pick("LG_LLM_API_KEY", "YUU_AI_API_KEY"),
        "model": pick("LG_LLM_MODEL", "YUU_AI_MODEL"),
    }


# The gateway allows 60 requests per minute across all of its clients. Stay under it in this process
# (override with LG_LLM_RPM; 0 disables). Cached responses never count.
RPM = int(os.environ.get("LG_LLM_RPM", "30"))
_rl_lock = threading.Lock()
_rl_times: deque[float] = deque()


def _throttle() -> None:
    """Sliding-window limit on outgoing requests, shared by every thread in the process."""
    if RPM <= 0:
        return
    while True:
        with _rl_lock:
            now = time.time()
            while _rl_times and now - _rl_times[0] >= 60:
                _rl_times.popleft()
            if len(_rl_times) < RPM:
                _rl_times.append(now)
                return
            wait = 60 - (now - _rl_times[0])
        time.sleep(max(wait, 0.05))


def _retry_after(r) -> float | None:
    """Seconds from a Retry-After header, if the server sent one (capped at 10 minutes)."""
    try:
        return min(600.0, max(1.0, float(r.headers.get("retry-after", ""))))
    except ValueError:
        return None

@dataclass
class Completion:
    text: str
    reasoning: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cost_usd: float | None
    latency_s: float
    finish_reason: str
    provider: str
    key: str
    cached: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def cache_key(model: str, messages: list[dict], params: dict, sample: int) -> str:
    blob = json.dumps({"model": model, "messages": messages, "params": params, "sample": sample},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / key[:2] / f"{key}.json"


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int = 6000,
    temperature: float = 0.6,
    seed: int | None = None,
    sample: int = 0,
    # The gateway sometimes accepts a connection and never answers; a long timeout then blocks a worker for
    # minutes per attempt (measured: 17.8 min of wall time for 2 calls worth 6 s of latency). Fail fast, retry.
    timeout: float = 120.0,
    retries: int = 6,
    offline: bool = False,
) -> Completion:
    """One chat completion. `sample` distinguishes independent draws of the same prompt."""
    cfg = llm_config()
    model = model or cfg["model"]
    params = {"max_tokens": max_tokens, "temperature": temperature}
    if seed is not None:  # only when given, so requests and cache keys without a seed are unchanged
        params["seed"] = seed
    key = cache_key(model, messages, params, sample)
    path = _cache_path(key)
    if path.exists():
        c = Completion(**json.loads(path.read_text()))
        c.cached = True
        return c
    if offline:
        raise LookupError(f"offline mode and no cached response for {key}")

    body = {"model": model, "messages": messages, **params}
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        _throttle()
        t0 = time.time()
        try:
            r = httpx.post(f"{cfg['base_url']}/chat/completions", json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as e:  # network error or timeout: retry
            last_err = e
            time.sleep(min(60, 3 * 2 ** attempt))
            continue
        if r.status_code in (429, 503):  # rate limited: other projects share the gateway's budget
            last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            time.sleep(_retry_after(r) or min(300, 30 * 2 ** attempt))
            continue
        if r.status_code >= 500:
            last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            time.sleep(min(60, 3 * 2 ** attempt))
            continue
        if r.status_code >= 400:
            # This gateway returns transient 400s under load: in the main run the same prompts that got a 400
            # later succeeded, and prompts of 11k tokens are accepted, so a 400 is not a length limit here.
            # Retry with backoff, and keep the body so the reason is visible if it persists.
            last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
            time.sleep(min(60, 3 * 2 ** attempt))
            continue
        try:
            d = r.json()
        except json.JSONDecodeError as e:
            last_err = e
            time.sleep(min(60, 3 * 2 ** attempt))
            continue
        latency = time.time() - t0
        break
    else:
        raise RuntimeError(f"LLM call failed after {retries + 1} attempts: {last_err}")

    choice = d["choices"][0]
    msg = choice.get("message", {})
    usage = d.get("usage", {}) or {}
    c = Completion(
        text=msg.get("content") or "",
        reasoning=msg.get("reasoning") or "",
        prompt_tokens=int(usage.get("prompt_tokens", 0)),
        completion_tokens=int(usage.get("completion_tokens", 0)),
        reasoning_tokens=int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0),
        cost_usd=usage.get("cost"),
        latency_s=latency,
        finish_reason=choice.get("finish_reason") or "",
        provider=d.get("provider") or "",
        key=key,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(c.to_dict(), ensure_ascii=False))
    return c
