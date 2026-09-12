import json

import pytest

from leangraph import llm
from leangraph.agent import AgentConfig, prove_messages, plan_messages
from leangraph.retrieval import Premise
from leangraph.tasks import Task, load_tasks, save_tasks

T = Task(id="t1", statement="(a b : ℕ) : a + b = b + a", family="algebra", difficulty="easy", split="novel",
         banned_modules=frozenset({"M.X"}), gt_premises=("Nat.add_comm",), features={"k": 1})


def test_task_roundtrip(tmp_path):
    p = tmp_path / "tasks.jsonl"
    save_tasks([T], p)
    (back,) = load_tasks(p)
    assert back == T and back.features == {"k": 1} and back.banned_modules == frozenset({"M.X"})


def test_cache_key_is_deterministic_and_sample_sensitive():
    m = [{"role": "user", "content": "x"}]
    k = llm.cache_key("m", m, {"t": 1}, 0)
    assert k == llm.cache_key("m", m, {"t": 1}, 0) and k != llm.cache_key("m", m, {"t": 1}, 1)


def test_offline_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "llm_config", lambda: {"base_url": "x", "api_key": "k", "model": "m"})
    msgs = [{"role": "user", "content": "hi"}]
    with pytest.raises(LookupError):
        llm.chat(msgs, offline=True)
    key = llm.cache_key("m", msgs, {"max_tokens": 6000, "temperature": 0.6}, 0)
    path = tmp_path / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(text="ring", reasoning="", prompt_tokens=1, completion_tokens=1, reasoning_tokens=0,
                                    cost_usd=0.0, latency_s=0.1, finish_reason="stop", provider="p", key=key)))
    c = llm.chat(msgs, offline=True)
    assert c.cached and c.text == "ring"


def test_prompt_switches():
    hits = [Premise("Nat.add_comm", "M", "Nat.add_comm (n m : ℕ) : n + m = m + n", None, 1)]
    hist = [{"code": "theorem lg_target ... := by\n  simp", "compiler_output": "1:1: error: first", "proof": "simp"},
            {"code": "theorem lg_target ... := by\n  omega", "compiler_output": "1:1: error: second", "proof": "omega"}]
    user = lambda cfg, h=hits, hs=hist: prove_messages(T, cfg, h, None, hs)[1]["content"]
    base = AgentConfig("x", rounds=3)
    assert user(base).endswith("/no_think") and not user(AgentConfig("x", think=True)).endswith("/no_think")
    assert "Nat.add_comm (n m : ℕ)" in user(base)
    assert "first" in user(base) and "second" in user(base)
    no_mem = user(AgentConfig("x", memory=False))
    assert "first" not in no_mem and "second" in no_mem
    no_fb = user(AgentConfig("x", feedback=False))
    assert "error" not in no_fb and "did not compile" in no_fb
    assert "lg_target" in user(base, [], []) and "Possibly relevant" not in user(base, [], [])


def test_planner_skeleton_switch():
    with_sk = plan_messages(T, AgentConfig("p", plan=True), [])[1]["content"]
    without = plan_messages(T, AgentConfig("p", plan=True, skeleton=False), [])[1]["content"]
    assert "skeleton" in with_sk and "Do not write any Lean code" in without


def test_budget_accounting():
    assert AgentConfig("f", plan=True, rounds=3).max_llm_calls == 5
    assert AgentConfig("d", samples=4).max_llm_calls == 4


def test_primary_prompt_is_pinned_and_variant_differs():
    from leangraph.agent import LEAN4_REMINDER, PROMPTS, SYSTEM_PROVER
    msgs = prove_messages(T, AgentConfig("x"), [], None, [])
    assert AgentConfig("x").prompt == "v2" and msgs[0]["content"] == PROMPTS["v2"]["system"]
    assert LEAN4_REMINDER in msgs[0]["content"] and "do not repeat `:= by`" in msgs[0]["content"]
    assert msgs[1]["content"] == ("Prove this theorem.\n\n```lean\ntheorem lg_target (a b : ℕ) : a + b = b + a := by\n```\n\n"
                                  "Answer with the tactic proof only, in one ```lean block.\n/no_think")
    # The original p1 prompt is still reproducible for the demo and first-pilot traces.
    assert prove_messages(T, AgentConfig("o", prompt="p1"), [], None, [])[0]["content"] == SYSTEM_PROVER
    alt = prove_messages(T, AgentConfig("y", prompt="v2b"), [], None, [])
    assert alt[0]["content"] != msgs[0]["content"] and LEAN4_REMINDER in alt[0]["content"]
    assert alt[1]["content"] != msgs[1]["content"] and "lg_target (a b : ℕ) : a + b = b + a := by" in alt[1]["content"]


def test_rate_limiter_waits_once_the_window_is_full(monkeypatch):
    from leangraph import llm
    clock = {"t": 1000.0}
    slept = []
    monkeypatch.setattr(llm.time, "time", lambda: clock["t"])
    monkeypatch.setattr(llm.time, "sleep", lambda s: (slept.append(s), clock.__setitem__("t", clock["t"] + s)))
    monkeypatch.setattr(llm, "RPM", 2)
    llm._rl_times.clear()
    llm._throttle(); llm._throttle()
    assert slept == []
    llm._throttle()  # third request in the same minute must wait for the window to slide
    assert slept and abs(sum(slept) - 60) < 0.2
    llm._rl_times.clear()


def test_reply_cap_depends_on_reasoning_tier(monkeypatch):
    from leangraph import agent
    assert AgentConfig("x").max_tokens == agent.MAX_TOKENS_NO_THINK == 2048
    assert AgentConfig("y", think=True).max_tokens == agent.MAX_TOKENS_THINK
    seen = {}
    def fake_chat(messages, **kw):
        seen.update(kw)
        raise RuntimeError("stop after capturing kwargs")
    monkeypatch.setattr(agent.llm, "chat", fake_chat)
    import pytest as _pt
    with _pt.raises(RuntimeError):
        agent.run_task(T, AgentConfig("x"), pool=None)
    assert seen["max_tokens"] == 2048


class _FakeResp:
    def __init__(self, status, text="", headers=None, data=None):
        self.status_code, self.text, self.headers, self._data = status, text, headers or {}, data

    def json(self):
        return self._data


def _ok_payload():
    return {"choices": [{"message": {"content": "```lean\nrfl\n```"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "cost": 1e-6}, "provider": "x"}


def test_client_error_is_retried_and_reported_with_body(monkeypatch, tmp_path):
    from leangraph import llm
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "RPM", 0)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: calls.append(1) or _FakeResp(400, "upstream said no"))
    monkeypatch.setattr(llm, "llm_config", lambda: {"base_url": "http://x", "api_key": "k", "model": "m"})
    with pytest.raises(RuntimeError, match="HTTP 400: upstream said no"):
        llm.chat([{"role": "user", "content": "hi"}], sample=991, retries=2)
    assert len(calls) == 3


def test_transient_400_then_success(monkeypatch, tmp_path):
    from leangraph import llm
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "RPM", 0)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm, "llm_config", lambda: {"base_url": "http://x", "api_key": "k", "model": "m"})
    seq = [_FakeResp(400, "busy"), _FakeResp(200, data=_ok_payload())]
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: seq.pop(0))
    assert llm.chat([{"role": "user", "content": "hi"}], sample=993).text.startswith("```lean")


def test_rate_limit_waits_for_retry_after_then_succeeds(monkeypatch, tmp_path):
    from leangraph import llm
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "RPM", 0)
    monkeypatch.setattr(llm, "llm_config", lambda: {"base_url": "http://x", "api_key": "k", "model": "m"})
    seq = [_FakeResp(429, "slow down", {"retry-after": "7"}), _FakeResp(200, data=_ok_payload())]
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: seq.pop(0))
    slept = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    c = llm.chat([{"role": "user", "content": "hi"}], sample=992)
    assert c.text.startswith("```lean") and slept == [7.0]


def test_resampled_draws_get_distinct_seeds_and_first_draw_is_unchanged(monkeypatch):
    from leangraph import agent, llm
    seen = []
    def fake_chat(messages, **kw):
        seen.append(kw.get("seed"))
        return llm.Completion(text="", reasoning="", prompt_tokens=0, completion_tokens=0, reasoning_tokens=0,
                              cost_usd=0.0, latency_s=0.0, finish_reason="stop", provider="", key="k")
    monkeypatch.setattr(agent.llm, "chat", fake_chat)
    agent.run_task(T, AgentConfig("d4", samples=4), pool=None)
    assert seen == [None, 1001, 1002, 1003]
    seen.clear()
    agent.run_task(T, AgentConfig("rep", rounds=3), pool=None)
    assert seen == [None, None, None, None]  # repair rounds keep their seedless requests


def test_seed_changes_request_and_key_only_when_given(monkeypatch, tmp_path):
    from leangraph import llm
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "RPM", 0)
    monkeypatch.setattr(llm, "llm_config", lambda: {"base_url": "http://x", "api_key": "k", "model": "m"})
    bodies = []
    monkeypatch.setattr(llm.httpx, "post", lambda url, json=None, **k: bodies.append(json) or _FakeResp(200, data=_ok_payload()))
    msgs = [{"role": "user", "content": "seed test"}]
    c0 = llm.chat(msgs, sample=0)
    c1 = llm.chat(msgs, sample=0, seed=1001)
    assert "seed" not in bodies[0] and bodies[1]["seed"] == 1001
    assert c0.key == llm.cache_key("m", msgs, {"max_tokens": 6000, "temperature": 0.6}, 0) and c1.key != c0.key


def test_client_error_is_retried_then_reported_with_body(monkeypatch, tmp_path):
    """The gateway relays intermittent upstream failures as HTTP 400 ("Provider returned error"), so 4xx is retried."""
    from leangraph import llm
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "RPM", 0)
    monkeypatch.setattr(llm, "llm_config", lambda: {"base_url": "http://x", "api_key": "k", "model": "m"})
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    seq = [_FakeResp(400, "Provider returned error"), _FakeResp(200, data=_ok_payload())]
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: seq.pop(0))
    assert llm.chat([{"role": "user", "content": "hi"}], sample=993).text.startswith("```lean")
    calls = []
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: calls.append(1) or _FakeResp(400, "maximum context length exceeded"))
    with pytest.raises(RuntimeError, match="failed after 7 attempts.*HTTP 400.*maximum context length"):
        llm.chat([{"role": "user", "content": "hi"}], sample=994)
    assert len(calls) == 7
