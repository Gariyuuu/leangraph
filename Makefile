# LeanGraph — every step of the study is a make target. `make reproduce` replays
# the frozen results from cached model responses without calling any API.

SHELL := /bin/bash
PY    := .venv/bin/python
export PATH := $(HOME)/.elan/bin:$(PATH)
LEAN_TOOLCHAIN := leanprover/lean4:v4.33.1
REPL_COMMIT := $(shell cat lean_env/repl.commit 2>/dev/null)
RUN_ID ?= main
SPLIT ?= test

.PHONY: setup corpus benchmark-smoke retrieve prove prove-think analyze figures paper site test test-lean reproduce freeze

setup:  ## Lean toolchain, Mathlib cache, Lean REPL, Python env
	command -v elan >/dev/null || curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y --default-toolchain none
	elan toolchain install $(LEAN_TOOLCHAIN)
	cd lean_env && lake exe cache get && lake build LeangraphEnv
	test -d .lean_repl || git clone https://github.com/leanprover-community/repl.git .lean_repl
	cd .lean_repl && git checkout -q $(REPL_COMMIT) && echo "$(LEAN_TOOLCHAIN)" > lean-toolchain && lake build
	test -d .venv || python3.11 -m venv .venv
	$(PY) -m pip install -q -r requirements.txt

corpus:  ## premise dump, candidate pool, Lean metadata, verified task list
	cd lean_env && LG_PREMISES_OUT=$(CURDIR)/corpus/premises.jsonl lake env lean Extract.lean
	cd lean_env && LG_NAMES_OUT=$(CURDIR)/corpus/all_names.txt lake env lean AllNames.lean
	$(PY) -m leangraph.corpus
	cd lean_env && LG_CANDIDATES_IN=$(CURDIR)/corpus/candidates.txt LG_CANDIDATES_OUT=$(CURDIR)/corpus/candidates_meta.jsonl lake env lean Candidates.lean
	$(PY) -m leangraph.build novel
	$(PY) -m leangraph.build tasks

benchmark-smoke:  ## three theorems through template, direct, repair and BM25 retrieval + repair (no dense index needed)
	$(PY) -m leangraph.run template direct repair rag_repair_bm25 --tasks novel_nt_03,novel_ineq_01,novel_set_04 --run-id smoke --workers 1 --concurrency 3

retrieve:  ## retrieval benchmark (BM25 / dense / hybrid) against ground-truth premises
	$(PY) -m leangraph.retrieval_eval

prove:  ## every agent configuration on the test split (no-think tier)
	$(PY) -m leangraph.run template direct direct_at4 repair rag rag_repair full rag_repair_bm25 rag_repair_dense \
	    full_no_retrieval full_no_feedback full_no_memory full_no_skeleton direct_prompt_b repair_prompt_b \
	    --split $(SPLIT) --run-id $(RUN_ID)

prove-think:  ## reasoning-tier configurations (slow)
	$(PY) -m leangraph.run direct_think repair_think rag_repair_think full_think --split $(SPLIT) --run-id $(RUN_ID)

analyze:  ## tables and statistics from traces
	$(PY) -m leangraph.analyze --run-id $(RUN_ID)

figures:
	$(PY) -m leangraph.figures --run-id $(RUN_ID)

paper:
	$(PY) -m leangraph.paper --run-id $(RUN_ID)

site:
	$(PY) -m leangraph.export_site --run-id $(RUN_ID)
	cd site && npm run build

test:  ## fast tests (no Lean)
	$(PY) -m pytest -q -m "not lean"

test-lean:  ## Lean-backed verifier tests (slow)
	$(PY) -m pytest -q -m lean

freeze:  ## pin canonical results by hash (make freeze RUN_ID=main)
	$(PY) -m leangraph.freeze --run-id $(RUN_ID)

reproduce:  ## re-derive every number from frozen traces and cached responses, no API calls
	$(PY) -m leangraph.run $(shell $(PY) -c "from leangraph.run import CONFIGS; print(' '.join(c for c in CONFIGS if not c.endswith('_think')))") --split $(SPLIT) --run-id reproduce --offline
	$(MAKE) analyze figures paper RUN_ID=reproduce
