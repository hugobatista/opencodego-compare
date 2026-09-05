# AGENTS.md

Model pricing comparison site for OpenCode Go vs Zen vs OpenRouter.

## Layout

- `fetch/` — Python data pipeline. Needs `pip install -r fetch/requirements.txt`.
- `data/` — generated JSON. `prices.json` is the only file the frontend reads.
- `web/` — Vue 3 + Vite. Imports `data/prices.json` directly via `../../data/prices.json` (Vite `server.fs.allow: ['..']`).

## Data pipeline

Refresh in this exact order:

```
python3 fetch/run_all.py && python3 fetch/build_json.py
```

`run_all.py` stage 1 (`fetch_openrouter.py` + `fetch_deepinfra.py` + `scrape_opencode_go.py` + `scrape_opencode_zen.py` + `scrape_command_code_goat.py`) runs in parallel, then `fetch_endpoints.py`, then `build_json.py`.
`build_json.py` then merges all sources into `data/prices.json` and is run separately (CI does the same).
`build_json.py` must always run after any fetch step, or `prices.json` goes stale.

Gotchas:
- Scrapers index tables by position (`tables[1]`, `tables[3]`) on `opencode.ai/docs/*`. Layout changes print a warning and exit 0 — check stderr/row counts, not exit codes.
- `fetch_endpoints.py` uses the structured OpenRouter API per model and stores a sha1 `digest` in `or_endpoints.json`. The heavy HTML page is only re-fetched for models whose API digest changed (it carries `data_policy`, which the API lacks). The first run after this change fetches all HTML pages; later runs only changed models. `scrape_opencode_zen.py` uses regex on model names to hardcode the per-model privacy policy.
- `fetch_modelmarkets.py` fetches the models sitemap (allowed by robots.txt), caches `data/modelmarkets.json`, and re-fetches only pages whose sitemap `lastmod` changed. It regex-extracts the Hugging Face repo from each page (`hf` field) — only open-weight models have one. `build_json.py` matches every row to a slug by normalized name (OpenRouter/DeepInfra: `base` is the last segment of the id; Go/Zen/GOAT: name minus `(...)`/` Free`) — models absent from the modelmarkets catalog get no `modelLink`/`hfLink`. Non-`openrouter` rows get `developerId = org/slug` and `maker` from the match; `openrouter` rows keep the full OR id as `developerId`. Unmatched rows fall back to `null` and emit a warning to stderr.
- Families: `model` is the family (e.g. `DeepSeek V4 Flash`), `variant` the specific model (e.g. `DeepSeek V4 Flash (Off-Peak)`). `fetch/model_families.json` maps a normalized devId stem to the family name; `build_json.py` falls back to a heuristic (strips maker prefix, dates, variant tokens) and prints a `Family warning: no mapping for …` line to stderr for every unmapped/devId-less family — watch stderr and grow the map, don't rely on heuristic output. `fetch/makers.json` maps org/prefix slugs (normalized) to display names for the `maker` column.
- Units: prices are $/1M tokens. Go effective = listed × 10 ÷ monthly allowance ($10/mo sub). GOAT effective = listed × 10 ÷ per-model monthly credits ($10/mo sub; credits $20–$70; models without explicit credits default to $20). OpenRouter real = listed × 1.055 fee × (1 + tax, default 24.25%). Zen real = listed. DeepInfra real = listed (from the API `input_tokens`/`output_tokens`, cached reads from `cache_read_tokens`; only `chat`-tagged models are kept — embeddings are excluded).
- `scrape_command_code_goat.py` reads `commandcode.ai/docs/plans/goat`: table 0 is the catalog (48 models, names carry `Free`/`-50%`/`Off-peak…` suffixes), tables 2+3 carry per-model monthly credits at billed prices. Prices come from the credits tables; the catalog prices have `+N` caps badges and struck deal text. Free models (LongCat 2.0, Laguna S 2.1) fall back to the catalog. Off-peak models (DeepSeek V4 Flash/Vision/Pro) show one row per variant — the peak rate is in an annotation (`peak $X / $Y`), and read/write scale by the same ratio as input.
- `fetch_deepinfra.py` hits `api.deepinfra.com/v1/openai/models`, filters to `chat`-tagged token-priced models, writes `data/deepinfra.json`. `base` = last path segment of the id (like OpenRouter) for modelmarkets matching; `variantLink` = `https://deepinfra.com/<id>`. About 35 DeepInfra models are absent from the modelmarkets catalog and get no `modelLink`/`maker`/`developerId` — expected.

## Market naming

`market` values are full plan names: `opencode-go`, `command-code-goat`, `opencode-zen`, `openrouter`, `deepinfra`. There is no `market` column — the `plan` column holds the display label (e.g. `OpenCode Go`), and `market` drives styling/classes (`b-<market>`, `p-<market>`), pricing math, and matching. Keep full names; avoid short acronyms (`or`, `goat`) when adding future Command Code plans.

## Config

- `fetch/overrides.json`: `opencode-go.exclude` skips models (e.g. "MiniMax M2.5"). `forceLogs` is dead config — never read.
- `fetch/fetch_or.py` is a stale copy of `fetch_openrouter.py`, not in the pipeline. Don't edit it.

## CI / deploy

- `fetch.yml` runs on `main` only, daily 05:05 UTC; auto-commits `data/` as `chore: refresh pricing data`, which then triggers `deploy.yml`.
- `deploy.yml` also runs on push to `main` touching `web/**` or `data/**`. Builds the site, deploys to GitHub Pages under `/opencodego-compare/`.
- All work happens on `main`; `dev` was removed.

## Verify

- Pipeline: each step prints "Saved N …"; watch for table-count warnings.
- Frontend: `cd web && npm run build`. No test or lint scripts exist in the repo.