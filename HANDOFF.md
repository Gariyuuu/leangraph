# Handoff

Last updated: 2026-09-12. **The study is complete and released.** Everything below was checked; nothing is aspirational.

## State

| Piece | Status |
|---|---|
| Lean 4.33.1 + Mathlib v4.33.1 (`lean_env/`, 7.6 GB `.lake`, not committed) | installed, `lake build` OK; restore with `make setup` |
| Lean REPL (`.lean_repl/`, commit in `lean_env/repl.commit`) | built against 4.33.1; ~40 s warm import, ~4.7 GB RSS per worker |
| Verifier (`leangraph/verify.py`) | Lean suite 18/18 (2026-09-11, `LG_TEST_WORKERS=1 pytest -m lean`, 19 min) |
| Tasks | 203 in `corpus/tasks.jsonl`: 150 Mathlib held-out (121 test / 29 dev) + 53 authored (all certified); **test split = 174** |
| Premises | 262,216-theorem dump; 260,003 user-facing theorems indexed (dump and embeddings not committed; rebuildable) |
| Retrieval benchmark | done, n = 164: recall@8 BM25 8.6% (MRR 0.117), dense 7.3% (MRR 0.088), hybrid 10.1% (MRR 0.125) (`results/retrieval/`) |
| Main grid (run `main`) | **complete: 15 configurations × 174 theorems, no unresolved harness errors**; 8,798 model calls, $2.54 total model cost |
| Analysis / figures / paper | final (`results/analysis/main/`, `results/figures/main/`, `paper/paper.md`); no interim status text |
| Frozen | `results/FROZEN_main.json` pins every result file and the response cache by SHA-256; `python -m leangraph.freeze --check --run-id main` |
| Site | Next.js 16.3.4; browser smoke test 20/20 page views OK (10 routes × desktop/phone, `scripts/site_smoke.mjs`) |
| Release | public repo https://github.com/Gariyuuu/leangraph; Vercel project `leangraph` auto-deploys `main` (root `site/`, SSO off); live https://leangraph.vercel.app |
| Tests | 66 fast tests pass (`make test`) |

## Results (test split, 174 theorems)

| Configuration | Verified | Rate [95% Wilson CI] |
|---|---:|---:|
| Template (no LLM) | 46/174 | 26.4% [20.4, 33.4] |
| Full (plan + retrieval + repair) | 13/174 | 7.5% [4.4, 12.4] |
| Full − skeleton | 13/174 | 7.5% [4.4, 12.4] |
| BM25 retrieval + repair | 13/174 | 7.5% [4.4, 12.4] |
| Repair (paraphrased prompt) | 12/174 | 6.9% [4.0, 11.7] |
| Full − memory | 11/174 | 6.3% [3.6, 11.0] |
| Repair | 11/174 | 6.3% [3.6, 11.0] |
| Full − compiler feedback | 10/174 | 5.7% [3.2, 10.3] |
| Full − retrieval | 9/174 | 5.2% [2.7, 9.5] |
| Dense retrieval + repair | 9/174 | 5.2% [2.7, 9.5] |
| Hybrid retrieval + repair | 8/174 | 4.6% [2.3, 8.8] |
| Direct (paraphrased prompt) | 5/174 | 2.9% [1.2, 6.5] |
| Hybrid retrieval | 3/174 | 1.7% [0.6, 4.9] |
| Direct ×4 | 2/174 | 1.1% [0.3, 4.1] |
| Direct | 1/174 | 0.6% [0.1, 3.2] |

4 of 15 pre-registered contrasts survive Holm correction:
  * RQ2 compiler-feedback repair vs one draft: +5.7 points [+2.3, +9.2], Holm p = 0.0254
  * RQ2 repair vs independent resampling at equal LLM calls: +5.2 points [+2.3, +8.6], Holm p = 0.0469
  * Primary: full agent vs direct generation: +6.9 points [+3.4, +10.9], Holm p = 0.00684
  * LLM vs no-LLM automation: -25.9 points [-32.2, -19.5], Holm p = 8.53e-13

Retrieval, planning, every full-agent ablation (including withholding Lean's error text), BM25/dense vs hybrid and the
paraphrased prompts show no reliable effect. See the paper's conclusion for the careful attribution: repair beats
equal-budget independent drafts, but the data cannot separate Lean's error text from revising one's own failed proof.

## Model

One model: the owner's gateway `api.gariyuuu.com/v1`, model id `Yuu no Sekai`; its docs (gariyuuu-web) name the upstream
as OpenRouter `qwen/qwen3-8b` (responses report provider "Alibaba"). Reasoning off (`/no_think`), replies capped at 2,048
tokens. **By the owner's decision (2026-09-10) there is no reasoning-on tier and no second model: RQ6 is not answered.**

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

## If you pick this up

* Nothing is pending. To verify the release: `python -m leangraph.freeze --check --run-id main`, `make test`, and
  `make reproduce` (recomputes everything from cached model responses, no API calls; needs `make setup` first).
* Regenerating outputs: `make analyze figures paper site RUN_ID=main` then `python -m leangraph.readme_results --run-id main`;
  commit and push (the site redeploys itself). Re-freeze only if traces change.
* **Site icon:** `site/app/icon.svg` is the single source (⊢ ending in a graph node, accent `#1c5cab`). Never
  hand-edit `site/app/apple-icon.png` or `site/app/favicon.ico`; regenerate them with
  `PLAYWRIGHT_DIR=<node_modules with playwright> node scripts/make_icons.mjs && .venv/bin/python scripts/make_favicon.py`.
  `scripts/site_smoke.mjs` fails if the head stops declaring the icons or any icon URL stops resolving.
* **Do not** run `make prove-think` (declined spend) or add configurations to run `main` without re-freezing and
  re-deriving the Holm family.
* Other Claude sessions share `~/Projects`; one committed and pushed this repo mid-run on 2026-09-12. Check
  `git log origin/main` before pushing.
