# Environment

Generated from the lockfiles by a script, not typed by hand. Regenerate it whenever a pin changes.

## Lean

| Item | Value |
|---|---|
| Toolchain | `leanprover/lean4:v4.33.1` |
| `lean --version` | `Lean (version 4.33.1, arm64-apple-darwin24.6.0, commit 819816b2e0a3bf405af45ae5c7af2491d8f5bee6, Release)` |
| Lean REPL | `leanprover-community/repl` at `5d5c49d13dfc0c1d2df43a27c3e56e02ad81b9c3`; its `lean-toolchain` is set to the pin above before building |
| Default heartbeat budget | 200000 per theorem (`set_option maxHeartbeats 200000 in`) |
| Wall-clock backstop | 60 s per REPL check, 600 s per certification |

## Lake manifest (`lean_env/lake-manifest.json`)

| Package | Commit | Requested |
|---|---|---|
| `mathlib` | `0df444a360eaa60ab8c11dca51a86af692955474` | `v4.33.1` |
| `plausible` | `b7eb3304aeae834b12dda98993a37f6a41f6f0bb` | `main` |
| `LeanSearchClient` | `5f4d51b81cbd3f6b32b156bfad9056621a040404` | `main` |
| `importGraph` | `16f02aa7642864af59f1ff0e384a015994db9118` | `main` |
| `proofwidgets` | `4be2e3d5087eeb272cf5a8853b8f9dd025ef5957` | `main` |
| `aesop` | `3448c0bcc5ce01b2d1546e483ec3620e32df3d0e` | `master` |
| `Qq` | `92c15be17b7caf78c2ad767ec40f89052d908d81` | `master` |
| `batteries` | `4488d40d070b9700d4d5a6aa342f0d40c31b2a2d` | `main` |
| `Cli` | `6130a47896ce867c6a4a55373441e59e565bad0f` | `v4.33.0` |

## Python

Python 3.11 venv. Pinned packages (`requirements.txt`):

```
fastembed==0.8.0
httpx==0.28.1
matplotlib==3.11.1
numpy==2.4.6
onnxruntime==1.29.0
pandas==3.0.5
pytest==9.1.1
PyYAML==6.0.3
scipy==1.17.1
```

## Machine used for the frozen results

Darwin 24.1.0 (arm64), 12 logical cores, 24 GB RAM.
Each REPL worker holds Mathlib in memory (~4.7 GB RSS measured), so the default pool is 2 workers.

## Model

| Item | Value |
|---|---|
| Endpoint | OpenAI-compatible gateway at `api.gariyuuu.com/v1` (the owner's own) |
| Model id sent | `Yuu no Sekai` (the only model the gateway lists) |
| Upstream | The gateway's own docs (`gariyuuu-web/FEATURES.md`) name OpenRouter `qwen/qwen3-8b`; responses carry `"provider": "Alibaba"`. We did not verify the upstream independently. |
| Context limit reported by gateway | 8192 tokens |
| Tiers | `/no_think` appended (reasoning off) is the default tier; `*_think` configs leave reasoning on |
| Sampling | temperature 0.6; every response cached under a content hash in `results/llm_cache/` |
