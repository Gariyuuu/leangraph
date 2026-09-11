#!/bin/bash
# Run (or resume) the canonical main grid, unattended:
#   1. no-retrieval configurations (template baseline, direct, direct x4, repair, full without retrieval,
#      prompt-variant pair); if a grid process is already running the template on 2 REPL workers, it is
#      allowed to finish the template and is then stopped so the rest runs on 1 worker;
#   2. dense embeddings + retrieval benchmark (resumes from corpus/embeddings/chunk_*.npy);
#   3. retrieval-based configurations.
# Every phase re-runs until each (config, task) pair on the test split has a real trace; harness errors
# (e.g. gateway outages) are retried after 10 minutes, up to 6 attempts, and every attempt first waits (up to
# 4 hours) for the model gateway to answer a trivial chat call. Free-disk guards: 5 GB before a
# grid phase, 6 GB before the embedder (override with LG_MIN_FREE_GB_GRID / LG_MIN_FREE_GB_EMBED). Safe to re-run after an interruption: finished work is skipped.
# Usage: bash scripts/run_main_grid.sh >> results/main_grid.log 2>&1
cd /Users/gariyuu/Projects/leangraph || exit 1
PY=.venv/bin/python
NORET="template direct direct_at4 repair full_no_retrieval direct_prompt_b repair_prompt_b"
RET="rag rag_repair full rag_repair_bm25 rag_repair_dense full_no_feedback full_no_memory full_no_skeleton"
WORKERS=1  # once the model, not Lean, is the bottleneck, a second REPL (~4.7 GB) mostly idles
ts() { date '+%H:%M:%S'; }
free_gb() { df -g /Users/gariyuu | awk 'NR==2{print $4}'; }
wait_disk() {  # $1 = GB required
  for i in $(seq 1 30); do
    [ "$(free_gb)" -ge "$1" ] && return 0
    echo "$(ts) DISK GUARD: $(free_gb) GB free, need $1, waiting"; sleep 60
  done
  echo "$(ts) ABORT: disk never reached $1 GB free"; exit 1
}
gateway_status() {  # HTTP status of a trivial chat call (the chat path needs the upstream model; /models does not)
  $PY - <<'PY'
import sys, httpx; sys.path.insert(0, ".")
from leangraph.llm import llm_config
c = llm_config()
try:
    r = httpx.post(c["base_url"] + "/chat/completions", headers={"Authorization": "Bearer " + c["api_key"]}, timeout=90,
                   json={"model": c["model"], "messages": [{"role": "user", "content": "Reply OK /no_think"}], "max_tokens": 8})
    print(r.status_code)
except Exception:
    print("unreachable")
PY
}
wait_gateway() {  # up to 4 hours, checking every 5 minutes
  for i in $(seq 1 48); do
    s=$(gateway_status); [ "$s" = 200 ] && return 0
    echo "$(ts) GATEWAY DOWN (status $s), checking again in 5 min"; sleep 300
  done
  echo "$(ts) ABORT: gateway down for 4 hours"; exit 1
}
kill_tree() { local p=$1 c; for c in $(pgrep -P "$p" 2>/dev/null); do kill_tree "$c"; done; kill "$p" 2>/dev/null; }
remaining() {
  $PY - "$@" <<'PY'
import sys; sys.path.insert(0, ".")
from leangraph import analyze
from leangraph.tasks import load_tasks
from leangraph.run import select
ids = {t.id for t in select(load_tasks(), "test", None)}
tr = analyze.load_traces("main")
print(sum(len(ids - set(tr.get(c, {}))) for c in sys.argv[1:]))
PY
}
run_until_done() {
  local label=$1; shift
  for attempt in 1 2 3 4 5 6; do
    left=$(remaining "$@"); echo "$(ts) [$label] attempt $attempt: $left (config,task) pairs left"
    case "$left" in ''|*[!0-9]*) echo "$(ts) [$label] remaining() failed: '$left'"; return 1;; esac
    [ "$left" = 0 ] && { echo "$(ts) [$label] complete"; return 0; }
    wait_disk "${LG_MIN_FREE_GB_GRID:-5}"
    wait_gateway
    $PY -m leangraph.run "$@" --split test --run-id main --workers $WORKERS --concurrency 8 2>&1 \
      | grep -viE warning | grep -E "STOPPED|Traceback" | tail -5
    echo "$(ts) [$label] run exited with status ${PIPESTATUS[0]}"
    left=$(remaining "$@"); [ "$left" = 0 ] && { echo "$(ts) [$label] complete"; return 0; }
    echo "$(ts) [$label] $left left after attempt $attempt; retrying in 10 min"; sleep 600
  done
  echo "$(ts) [$label] GAVE UP with $(remaining "$@") pairs left"; return 1
}

echo "$(ts) chain v2 started (model-driven phases on $WORKERS REPL worker)"
G=$(ps -axo pid=,command= | awk '$2 ~ /Python$/ && /leangraph.run template direct/ && /run-id main/ {print $1; exit}')
echo "$(ts) letting grid ${G:-none} finish the template baseline on 2 workers"
while [ -n "$G" ] && kill -0 "$G" 2>/dev/null; do
  n=$(wc -l < results/runs/main/template.jsonl 2>/dev/null | tr -d ' ')
  if [ "${n:-0}" -ge 174 ]; then
    echo "$(ts) template complete (174/174); stopping grid $G and its Lean processes"
    kill_tree "$G"; sleep 5; break
  fi
  sleep 20
done
run_until_done no-retrieval $NORET || { echo "$(ts) CHAIN STOPPED at no-retrieval grid"; exit 1; }

EMB=$(ls corpus/embeddings/bge_small_*.npy 2>/dev/null | grep -v tmp | head -1)
if [ -n "$EMB" ] && [ results/retrieval/summary.json -nt "$EMB" ]; then
  echo "$(ts) retrieval benchmark already up to date; skipping"; rc=0
else
wait_disk "${LG_MIN_FREE_GB_EMBED:-6}"
echo "$(ts) embeddings + retrieval benchmark starting"
$PY -m leangraph.retrieval_eval > /tmp/lg_retrieval_eval.log 2>&1; rc=$?
fi
echo "$(ts) retrieval_eval exited with status $rc"
if [ $rc -ne 0 ] || [ ! -f results/retrieval/summary.json ]; then
  echo "$(ts) CHAIN STOPPED: retrieval benchmark failed; tail:"; tail -5 /tmp/lg_retrieval_eval.log; exit 1
fi
echo "$(ts) retrieval benchmark done"

run_until_done retrieval $RET || { echo "$(ts) CHAIN STOPPED at retrieval grid"; exit 1; }
echo "$(ts) CHAIN DONE"
