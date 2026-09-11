# Decisions

Design decisions and revisions, newest last. Each says what was decided, why, and what evidence prompted it.

## 2026-09-09 · Pin Lean 4.33.1 / Mathlib v4.33.1
The newest stable pair at the time (both released 2026-08-21), not a release candidate. Mathlib pinned by git tag so
`lake-manifest.json` records an exact commit.

## 2026-09-09 · Two-tier verification
A long-lived Lean REPL (0.01–0.2 s per check, ~40 s warm import) is used for search; a fresh `lean` process is the
only judge. Measured: a cold file compile takes 15–30 s, too slow for search but independent of REPL state.

## 2026-09-10 · Certifier output is tagged with a per-run nonce
Found by test: indenting model output under `by` does not stop it adding top-level commands, because Lean ends a
tactic block at a command keyword. An injected `#eval IO.println "…depends on axioms: [propext]"` would have printed
before the real `#print axioms`. The certifier now reports axioms, used constants and added declarations itself,
each line prefixed with a random nonce created after the proof exists, and rejects extra declarations. A text filter
for command keywords stays as a second, independent layer; tests disable it and check the certifier alone.

## 2026-09-10 · Wall-clock backstop kept
Found by test: `repeat rw [Nat.add_comm] at h` is not stopped by the heartbeat limit. A 60 s wall-clock limit remains,
and verdicts it produces are machine-dependent (stated in the paper's limitations).

## 2026-09-10 · Held-out modules are near-leaves, with the downstream closure banned
A module is eligible if at most 20 modules depend on it and none is a tactic module; the target's module and every
module importing it are banned from proofs and from the index. Banning the downstream closure of a foundational
module would ban most of Mathlib, so eligibility is restricted to near-leaves.

## 2026-09-10 · Drop statements that mention banned constants
Measured: 15,008 of 17,993 near-leaf theorems state facts about their own module's definitions. Their unfolding
lemmas live in the banned module, so under the ban they are close to unprovable; they are excluded rather than kept
as an artificially hard tail.

## 2026-09-10 · Sample from the filtered pool, not filter a sample
The first version sampled 472 candidates and then filtered to 145, all-dev in four families because of a split bug.
Candidates are now every theorem of every eligible module; Lean-side filtering runs on all of them, and a balanced
round-robin sample (≤ 3 per module) is drawn afterwards. Selection never uses any prover's result.

## 2026-09-10 · Paraphrased prompt set
Added `direct_prompt_b` / `repair_prompt_b` (prompt set `p2`) so prompt sensitivity is measured rather than
listed as unmeasured. The primary prompt `p1` is pinned byte-for-byte by a test, since cached draws depend on it.

## 2026-09-10 · Revision: tactic-internal lemmas are not premises
First BM25 run (ground truth = every Mathlib theorem in the reference proof term): 166 theorems, MRR 0.119,
recall@8 0.085, hit@8 0.217. Inspection showed the ten most frequent ground-truth "premises" were all
`Mathlib.Meta.NormNum.*` / `Mathlib.Tactic.Ring.*` lemmas that `norm_num` and `ring` insert into proof terms; ground-truth
sets had median 5 but mean 18.3 and p90 60. These are not premises a prover cites, so they are now excluded from both the
index and the ground truth (rule: module `Mathlib.Tactic.*`, or namespace `Mathlib.Tactic.` / `Mathlib.Meta.`), for every
retriever alike. The rule is semantic and was fixed before any dense or hybrid result existed.

After the revision (same BM25, same 203 tasks): 164 theorems with reachable ground truth, MRR 0.117 [0.081, 0.155],
recall@8 0.086, hit@8 0.213, recall@50 0.166. The change barely moved BM25, because BM25 rarely retrieved tactic-internal
lemmas anyway; it matters for the definition, and possibly for the dense retriever, not for this number.

## 2026-09-10 · Revision: strip a restated `:= by` from model replies
The end-to-end demo (8 theorems, BM25 retrieval + repair, reasoning off) showed 4 of 8 first drafts beginning with
`:= by …`, the tail of the theorem header. The extractor stripped a leading `by` but not `:= by`, so Lean saw a stray
`:=` and failed. In `novel_nt_03` the round-0 tactic was correct and failed only for this reason; round 1 resubmitted
it without the prefix and verified. The extractor now also strips a leading `:= by`, the same class as stripping a
restated header: format extraction, not correction of tactics. Demo traces in `results/runs/demo/` predate the fix and
are not canonical. Added before any canonical run: `repeat_rate`, the share of repair attempts identical to an earlier
attempt in the same sample (3 of the 8 demo traces resubmitted an identical proof in later rounds).

## 2026-09-10 · Dev pilot 1: taxonomy labels and prompt v2
Direct generation (prompt p1, reasoning off) on the 29 dev theorems verified none of the first 25. Every failure was
inspected for harness artifacts; none were found (the `:= by` extraction fix was already in place), but three labels
were wrong: a Lean 3 `end,` was rejected as a forbidden command (the filter no longer lists `end`, which cannot inject
anything; Lean rejects it itself), Lean 3 tactic names such as `apply_instance` and `reflexivity` and lowercase
namespaces such as `measure_theory.` were labelled plain syntax errors (now Lean 3 syntax), and "Invalid simp theorem:
Expected a proposition" was unclassified (now a type mismatch). Labels only; no verdict changes.
Because Lean 3 habits dominated, the primary prompt was revised on the dev split before any test run: `v2` names the
specific Lean 3 constructs that fail and asks the model not to repeat `:= by`; `v2b` is its paraphrase for the
prompt-sensitivity contrast. `p1`/`p2` remain in the code for the demo and pilot-1 traces. Every canonical run uses v2.

### Pilot 1 final baseline (prompt p1, direct, reasoning off, 29 dev theorems), recorded before pilot 2 ran
0/29 verified; no harness errors; one wall-clock timeout. First-error classes (labels as of the refined taxonomy):
Lean 3 syntax 9, syntax error 6, wrong tactic 5, hallucinated theorem 3, forbidden 3 (run-time rejections), type
mismatch 2, timeout 1. **Planned comparison for pilot 2 (prompt v2, same 29 theorems):** verified count and the share
of first errors that are Lean 3 syntax. With 29 theorems this is descriptive, not a test; v2 was adopted on design
grounds before its pilot and is not contingent on the result.

## 2026-09-10 · Incident: gateway outage during pilot 2; harness errors are never results
Pilot 2 (prompt v2) recorded 24 of 29 theorems as harness errors: after five retries each, the gateway returned
HTTP 502 (8), Cloudflare 530 "origin unreachable" (8) and 524 "origin timeout" (8). Only 5 theorems got a real
attempt, so pilot 2 is void and is rerun after the gateway recovers. The run exposed three harness weaknesses, all
fixed with tests: resume treated an errored task as done (errored rows now go to a `*.harness_errors.jsonl` sidecar
and the task is retried); a run kept going through an outage (it now stops after 5 consecutive harness errors);
and analysis counted an errored task as an unverified proof (errored tasks are now excluded from every denominator
and reported as `harness_errors_unresolved`, and `freeze` refuses to run while any remain).

## 2026-09-10 · Owner decisions: scope of the model axis, release
* **No reasoning-on tier.** The owner declined the spend (estimated ~$6–7). Only reasoning-off configurations run.
  RQ7 (cost) is answered within that tier; the reasoning-on contrasts are absent from the analysis.
* **No second model.** RQ6 (can cheaper inference with strong scaffolding compete with more expensive inference?)
  is reported as not answered; the paper says so in its limitations.
* **Release.** Once the core steps are done (main grid, analysis, figures, paper, site on real data): commit, push to
  GitHub (public, per the owner's default for their own repos) and deploy the site to Vercel with SSO protection off.

## 2026-09-10 · Dev pilot 2 closed; reply cap 2,048 tokens (reasoning off); one more label fix
**Pilot 2 (prompt v2, direct, reasoning off)**: 26 of 29 dev theorems got real traces; 3 remain unresolved after
repeated HTTP 524 origin timeouts and the retry was stopped. On the 26 theorems both pilots completed
(`python -m leangraph.pilot_compare pilot pilot_v2 --config direct`): verified 0 vs 0; Lean 3 share of first errors
31% (p1) vs 27% (v2); first errors moved from syntax errors (5 → 3) to wrong tactics (5 → 10), i.e. more v2 proofs
parse and then fail at the tactic level. Despite the instruction, 6 v2 replies still restated `:= by` (extraction
handles it; no empty proofs). No harness artifacts. v2 stays canonical (adopted before its pilot, as recorded).
**Reply cap.** Replies that reach the 6,000-token cap are repetition loops (5% of first replies in the pilots), take
114–125 s, and sit at the gateway's ~100 s origin timeout; one of the three 524 theorems hit the cap in pilot 1.
Median replies are 72–100 tokens. Reasoning-off calls are now capped at 2,048 tokens (~40 s), recorded in each
trace's config. This changes cache keys, so the main grid shares no draws with the pilots (it runs on the test
split anyway). **Label fix:** Lean's bare `expected token` parse error is now a syntax error (was "other").

## 2026-09-10 · Site on Next.js 16.3.4 (security), React 18 kept
`npm audit` flagged a critical advisory (GHSA-3x4c-7xq6-9pq8, unbounded `next/image` disk-cache growth) for every
Next.js release through 16.3.0-preview.10, including 14.2.35, the newest 14.2 patch; Vercel blocks deploys of
Next.js versions with known critical advisories. The site moved to 16.3.4 (the `latest` tag; its peer range still
accepts React 18, so React, recharts, react-markdown and Tailwind are unchanged). The only code change: the
theorem route's `params` is now awaited (Next 15+ passes it as a Promise). `npm audit --omit=dev`: 0 vulnerabilities.

## 2026-09-11 · Gateway errors during the main run: 429s and transient 400s
The first pass over the no-retrieval configurations recorded 66 harness errors: HTTP 429 (30; the gateway allows
60 requests/minute across all of its clients, and other projects were using it) and HTTP 400 (36; direct ×4 6,
prompt-variant direct 5, full-without-retrieval 5, repair 20). The 400s are transient, not a context limit: the
same prompts later succeeded (the prompt-variant direct run completed 174/174 on retry), and a probe accepted
prompts of 4,800, 7,979 and 11,169 tokens with a 2,048-token reply budget (Lean-flavoured text runs ~2.5
characters per token). Client changes (no effect on cached draws or prompts): 429/503 honour Retry-After or back
off 30 s → 5 min; 400s and 5xx are retried with backoff and the response body is kept in the final error (the old
client discarded it); retries per call 6; default rate 30 requests/minute. Tasks that still fail go to the
harness-error sidecar and are retried by `scripts/run_main_grid.sh`; no errored task is counted as a result.

## 2026-09-11 · Finding: repeated draws from the gateway are nearly deterministic; Direct ×4 is not a resampling control
Direct ×4 was meant as the equal-budget control for repair: four independent drafts per theorem. In the main run,
for 98 of 173 theorems all four drafts are byte-identical, 57 have two distinct drafts, 16 three and only 2 four;
the median similarity of drafts 2–4 to draft 1 is 1.00. Every draft was a separate billed call with its own cache key,
so this is not our cache. A probe sent one prompt three times at temperature 0.6 and three times at 1.2: six distinct
response ids, no cached prompt tokens, one identical reply. So the upstream generation behaves almost
deterministically for a given prompt, whatever the temperature. Consequence: Direct ×4 measures repetition, not
independent sampling, and **the contrast "repair vs equal-budget resampling" (+5.7 points, Holm p = 0.008) does not
test what it was designed to test**; it is almost the same comparison as repair vs a single draft. It is reported
as uninformative, not as evidence for repair. Repair's own numbers are unaffected (each round sends a different
prompt), as are all single-draft configurations.
Also established: the gateway's limit is **60 requests/minute per API key** (its 429 body says so), and other
sessions use the same key, so our share of it varies.
**Remedy (decided before re-running).** A probe found that the request's `seed` parameter does change the reply
(three seeds gave 3 distinct replies on one theorem and 2 on a theorem whose four run drafts were identical), while
a per-sample tag in the system prompt did not. So a resampled draw (sample index k > 0) now sends `seed = 1000 + k`;
first drafts and repair rounds send no seed, so their requests, cache keys and existing traces are unchanged.
Direct ×4 is the only configuration with more than one sample. Its unseeded run is kept as evidence in
`results/runs_archive/main/direct_at4_unseeded.jsonl` (outside the run directory, so analysis and freezing ignore
it) and Direct ×4 is re-run with seeds. The equal-budget contrast is reported from the seeded run only.
**Remedy verified in the run.** On the first 53 theorems of the seeded Direct ×4 run, drafts per theorem were
4 distinct for 46, 3 for 5 and 2 for 2 (the unseeded run on the same theorems: 4 distinct for 0, 3 for 7, 2 for 17,
1 for 29); the median similarity of drafts 2–4 to draft 1 fell from 1.00 to 0.15. Draft 1 was byte-identical to the
unseeded run's draft 1 for 53/53, confirming that first drafts still replay from the cache under their original
keys.
**Seeded Direct ×4, full run.** 174/174 theorems; drafts per theorem (173 with four drafts): 4 distinct 148, 3 18,
2 5, 1 1 (unseeded run: 2, 16, 57, 98). Verified 2/174: `novel_nt_10` by a seeded draft (sample 1) and
`novel_cat_01` by the shared first draft. Repair vs this equal-budget control: 6.3% vs 1.1%, +5.2 points
[+2.3, +8.6], 9 theorems solved only by repair and 0 only by Direct ×4, exact McNemar p = 0.0039 (Holm p = 0.012
among the contrasts computed at that point; the reported Holm value is recomputed over every pre-registered
contrast once the grid is complete).

## 2026-09-11 · Only complete configurations are ever reported
While preparing an interim release, the generated abstract stated the primary contrast ("the full agent's
advantage over direct generation is not distinguishable from zero, Holm p = 1") from the full agent's first ~39
of 174 theorems: `analyze` computed any contrast on whatever tasks two configurations shared. That is a claim
from a partial run, and the paper's own status paragraph promised such contrasts were omitted. Rule now enforced
in `leangraph/analyze.py`, the single source for the paper, the site and the README: a configuration enters
`configs`, the breakdowns, the contrasts, the error taxonomy, the difficulty analysis and the Holm family only
when it has a real trace for every task in the run (the union across configurations; the grid runs all of them on
the same tasks). Configurations still running, or holding unresolved harness errors, are listed in
`configs_partial` with their counts and appear only in the interim status banner and paragraph. Tested with a
half-finished configuration and with an unresolved harness error. Separately, the abstract's and the site's
"best agent" are now chosen among the six headline configurations, not the prompt-sensitivity variants.
