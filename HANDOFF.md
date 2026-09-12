# Handoff

Last updated: 2026-09-10. Everything below was checked in this session; nothing is aspirational.

## State

| Piece | Status |
|---|---|
| Lean 4.33.1 + Mathlib v4.33.1 (`lean_env/`, 7.4 GB `.lake`) | installed, `lake build` OK |
| Lean REPL (`.lean_repl/`, commit in `lean_env/repl.commit`) | built against 4.33.1; ~40 s warm import, ~4.7 GB RSS per worker, 0.01–0.2 s per check |
| Verifier (`leangraph/verify.py`) | 16/17 Lean tests passed on first run; the one failure was a wrong test assumption (see gotchas), test fixed, not yet re-run |
| Premise dump | 262,216 theorems, 7,772 modules (`corpus/premises.jsonl`, not committed, 113 MB) |
| Name table | 473,141 constants (`corpus/all_names.txt`, not committed) |
| Tasks | 203 in `corpus/tasks.jsonl`: 150 held-out (121 test / 29 dev), 53 authored (all certified) |
| BM25 | sparse implementation, 33 s build, 7 ms/query |
| Dense embeddings | not built: the first attempt was killed to relieve memory before any 20k chunk was saved; rerun `build_dense_embeddings` |
| Agent runs | demo (`results/runs/demo/`, prompt p1, pre-extraction-fix) and dev pilots (`pilot/` = prompt p1, `pilot_v2/` = prompt v2); main grid not run. **Prompt v2 is canonical**; p1/p2 exist only to reproduce demo and pilot-1 traces. 19 configurations registered in `leangraph/run.py`, including a paraphrased-prompt pair (`direct_prompt_b`, `repair_prompt_b`) for prompt sensitivity |
| Site | builds (`next build` exit 0) with empty data; not yet checked with real data in a browser; not deployed |
| Git | `git init` only; nothing committed; no remote |
| Tests | 45 fast tests pass (`make test`), including a synthetic end-to-end pipeline test, a freeze-integrity test and a concurrent-embedding test. Lean suite: 16/17 on first run; the failing test's assumption was wrong and it was rewritten; not yet re-run |
| Freezing | `make freeze RUN_ID=main` pins every result file and the response cache by SHA-256; `python -m leangraph.freeze --check` fails on any change |

## Model

One model is available: the owner's gateway `api.gariyuuu.com/v1`, model id `Yuu no Sekai`. The gateway's own docs
(gariyuuu-web) say the upstream is OpenRouter `qwen/qwen3-8b`; responses report provider "Alibaba" and a real cost.
Reasoning on: ~100 s and ~$0.003 per call. `/no_think`: ~4 s and ~$0.00007. RQ6 (model scale) needs a second
model the owner has to supply; until then it is answered only by the reasoning-on/off tier.

## Gotchas found here

* **A statement with no binders must start with `: `** (`": 1 + 1 = 2"`). Otherwise `theorem lg_target (Finset…` parses the
  parenthesis as a binder.
* **Indentation does not stop command injection.** Lean ends a tactic block at a command keyword. The command filter and the
  certifier's nonce probe handle it; tests cover both independently.
* **Heartbeats do not bound every loop.** `repeat rw [Nat.add_comm] at h` runs until the 60 s wall-clock backstop; the worker
  restarts (~40 s). Wall-clock verdicts are machine-dependent.
* **Mathlib uses the module system** (`module`, `public import`, `public meta import`); proof bodies are still visible from a
  non-module file that does `import Mathlib`.
* **Machine limits.** 24 GB RAM, disk ~97–100 % full (swap files grow on the same volume). Other sessions run heavy jobs
  (e.g. an `extract_persons.py --workers 8`) that are not ours — do not kill them. Keep at most 2 REPL workers.
* `cd` inside a Bash call persists for later calls in the same shell; always use absolute paths.
* A background command launched in the same batch as a foreground command that `cd`s can start in the new directory.
  The first dense-embedding rebuild failed this way (`.venv/bin/python` not found) and still reported exit 0 because its
  output was piped through `grep`. Start every command with `cd <abs path> &&` and use `set -o pipefail`.
* **Partial configurations are never reported** (DECISIONS 2026-09-11): `analyze` only reports configurations
  with a trace for every task; the rest sit in `configs_partial`. Do not bypass this when adding outputs.
* **Disk guards in `scripts/run_main_grid.sh` are configurable**: `LG_MIN_FREE_GB_GRID` (default 5) before each grid
  attempt, `LG_MIN_FREE_GB_EMBED` (default 6) before the embedder. The retrieval phase of the main run was launched
  with `LG_MIN_FREE_GB_GRID=4` at 11:31 on 2026-09-11 (4.8 GB free, nothing else heavy running; the disk monitor alarms
  at 3 and 2 GB). The retrieval benchmark step is skipped when `results/retrieval/summary.json` is newer than the
  embedding matrix, so re-running the script never redoes it needlessly.
* **2026-09-11 ~03:00: the gateway went fully down** (`api.gariyuuu.com` returns HTTP 530 "Cloudflare Tunnel error"
  for `/models` and chat). The tunnel/gateway does not run on this Mac; the owner must restart it.
  `scripts/run_main_grid.sh` waits for it (checks every 5 minutes, up to 4 hours per attempt, 6 attempts).
* **The gateway can accept a connection and never answer.** Symptom: workers blocked in network reads (not
  sleeping), traces with large `wall_s` but tiny `llm_latency_s`, and no new files in `results/llm_cache`.
  The client's request timeout is 120 s for this reason; do not raise it. `LG_CONCURRENCY` (default 8) lowers
  parallel pressure — the last ablations ran at 4.
* **The gateway allows 60 requests/minute across all clients** (other projects share it). `llm.py` throttles to
  `LG_LLM_RPM` (default 50) per process: run one LLM pipeline at a time.
* **The model gateway can go down mid-run** (pilot 2: HTTP 502 / Cloudflare 530 / 524). Errored tasks go to a
  `*.harness_errors.jsonl` sidecar, runs stop after 5 consecutive harness errors, and resuming retries them. Check
  `harness_errors_unresolved` in the analysis before trusting any rate; `make freeze` refuses while it is non-zero.
* Monitor and background scripts run under **zsh**, which aborts on a glob that matches nothing
  (`no matches found`). Use `find` (or `setopt NULL_GLOB`) when the directory may not exist yet.
* The site runs **Next.js 16.3.4** (upgraded from 14.2.35 for a critical advisory; see DECISIONS). Route
  `params` are Promises: `await params` in any new dynamic route. The Next 14 `package.json`/lockfile backup was only
  kept in the session scratchpad.
* `pgrep -f <pattern>` matches the shell whose own command line contains the pattern, so a
  `while pgrep -f …` wait never ends and a monitor never sees an exit. Wait on a PID with `kill -0 <pid>`, or match
  on the executable column (`ps -axo pid=,command= | awk '$2 ~ /Python$/ && /pattern/'`).
* A REPL wall-clock timeout restarts the worker, and under memory pressure the re-import can take several minutes;
  a run that seems stalled at N/M is usually waiting on that.
* Two processes that both need the dense index used to build it concurrently and delete each other's chunks.
  `build_dense_embeddings` now takes an exclusive lock and writes atomically (tested with concurrent callers).
* A `SIGSTOP`ped process keeps its memory. Pausing the embedder did not relieve pressure; killing it dropped swap from ~10 GB to 2.5 GB.
  Run embeddings when no REPL is up: `python -c "from leangraph.retrieval import *; build_dense_embeddings(load_premises())"` (resumable in 20k chunks).

## Release status (2026-09-11)

* **Public repo:** https://github.com/Gariyuuu/leangraph (MIT code; Mathlib content Apache-2.0, see NOTICE).
* **Live site:** https://leangraph.vercel.app (Vercel project `leangraph`, Root Directory `site`, framework Next.js,
  SSO protection off; the domain was read from the project's own domain list). Pushes to `main` redeploy.
  CLI deploys must run from the repo root with `.vercelignore` (uploads only `site/`, ~9 MB); without it the upload
  exceeds Vercel's 10 MB request limit.
* **This is an interim release:** 9 of 15 configurations complete. The main grid was stopped at 14:5x because free disk
  fell to ~2.1 GB (other sessions' swap, not this project). BM25 retrieval + repair had 38/174 traces; retrieval +
  repair 173/174; dense retrieval + repair and the three full-agent ablations not started. Resume when free disk is
  back above ~4 GB: `LG_MIN_FREE_GB_GRID=4 bash scripts/run_main_grid.sh >> results/main_grid.log 2>&1`, then
  analysis → figures → paper → README results → export → `npm run build` → `scripts/site_smoke.mjs` → `make freeze`
  → commit + push (the site redeploys itself).

## Next steps, in order

1. Dense embeddings → `make retrieve` (retrieval benchmark). 7/13 chunks saved; the build resumes from
   `corpus/embeddings/chunk_*.npy`. **Run it only while no grid is running**: embedder (3 GB) + two REPLs + two
   certify processes pushed swap to 6.9 GB and free disk to 4.6 GB on 2026-09-10, so it was stopped mid-grid.
2. Dev pilots are closed (see DECISIONS 2026-09-10): prompt v2 canonical; reasoning-off replies capped at 2,048 tokens.
3. Main grid, reasoning-off tier, run id `main`, test split (174 theorems): **running unattended via
   `scripts/run_main_grid.sh`** (no-retrieval configurations → embeddings + retrieval benchmark → retrieval
   configurations; model-driven phases use 1 REPL worker to spare memory). State on 2026-09-11 ~15:00: 9 of 15 configurations complete (template 46, direct 1, direct ×4 2, repair 11,
   full 13, full − retrieval 9, retrieval 3, paraphrased direct 5, paraphrased repair 12, of 174); retrieval + repair
   173/174 and the five remaining configurations still running. Published as an interim release (site banner,
   paper status paragraph and README note are generated from `site/data/status.json`). After any interruption just re-run `bash scripts/run_main_grid.sh >> results/main_grid.log 2>&1`:
   finished work is skipped and harness-errored tasks are retried. **Do not run `make prove-think`.**
4. ~~Re-run the Lean verifier suite~~ Done 2026-09-11: `LG_TEST_WORKERS=1 pytest -m lean` → 18 passed (19 min).
5. Final results, once `results/runs/main/` has all 15 configurations at 174/174 and
   `harness_errors_unresolved` is 0 everywhere:
   * Check `results/retrieval/summary.json` is newer than the retrieval benchmark's start in the chain log
     (a stale 08:49 copy from an earlier session existed on 2026-09-11).
   * `make analyze figures paper site RUN_ID=main`, then `python -m leangraph.readme_results --run-id main`.
   * `cd site && npm run build`; open every route in a browser with the real data (not just curl).
5b. **Interim release (decided 2026-09-11):** once `full` is 174/174 (all six mandatory baselines done), release
   without freezing: `site/data/status.json` (from `leangraph.export_site.run_status`) drives an "Interim release"
   banner on the overview and leaderboard, and the paper gets a "Status of this version" paragraph listing the
   configurations still running. When the grid finishes, re-run analysis/figures/paper/site, `make freeze`, and push
   again (the banner and paragraph disappear once every `MAIN_GRID` configuration is complete).
6. Release (owner-approved 2026-09-10; public repo, MIT code licence + Mathlib NOTICE):
   * `make freeze RUN_ID=main` (refuses while harness errors remain); `make test`.
   * `git add -A && git commit`; `gh repo create Gariyuuu/leangraph --public --source=. --push`.
   * Vercel (see the owner's notes): from the repo root `vercel link --yes --project leangraph`; set Root
     Directory to `site` with `PATCH https://api.vercel.com/v9/projects/leangraph` body `{"rootDirectory":"site"}`
     using the CLI token in `~/Library/Application Support/com.vercel.cli/auth.json` (no CLI flag exists);
     `vercel project update leangraph --framework nextjs`; `vercel deploy --prod`;
     `vercel project protection disable leangraph --sso`.
   * Verify the URL Vercel lists for the project (`vercel projects ls` / project domains), never a guessed
     `leangraph.vercel.app` (strangers squat names); load it logged out.
   No second model: RQ6 stays unanswered by design. No `make prove-think`.
