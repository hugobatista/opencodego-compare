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

`run_all.py` stage 1 (`fetch_openrouter.py` + `scrape_go.py` + `scrape_zen.py` + `scrape_goat.py`) runs in parallel, then `fetch_endpoints.py`, then `build_json.py`.
`build_json.py` then merges all sources into `data/prices.json` and is run separately (CI does the same).
`build_json.py` must always run after any fetch step, or `prices.json` goes stale.

Gotchas:
- Scrapers index tables by position (`tables[1]`, `tables[3]`) on `opencode.ai/docs/*`. Layout changes print a warning and exit 0 — check stderr/row counts, not exit codes.
- `fetch_endpoints.py` uses the structured OpenRouter API per model and stores a sha1 `digest` in `or_endpoints.json`. The heavy HTML page is only re-fetched for models whose API digest changed (it carries `data_policy`, which the API lacks). The first run after this change fetches all HTML pages; later runs only changed models. `scrape_zen.py` is regex-based and fragile. `scrape_zen.py` hardcodes the per-model privacy policy.
- `fetch_modelmarkets.py` fetches the models sitemap (allowed by robots.txt), caches `data/modelmarkets.json`, and re-fetches only pages whose sitemap `lastmod` changed. It regex-extracts the Hugging Face repo from each page (`hf` field) — only open-weight models have one. `build_json.py` matches every row to a slug by normalized name (OR: last segment of `base`; Go/Zen: name minus `(...)`/` Free`) — models absent from the modelmarkets catalog get no `modelLink`/`hfLink`.
- Units: prices are $/1M tokens. Go effective = listed × 10 ÷ monthly allowance ($10/mo sub). GOAT effective = listed × 10 ÷ per-model monthly credits ($10/mo sub; credits $20–$70; models without explicit credits default to $20). OpenRouter real = listed × 1.055 fee × (1 + tax, default 24.25%). Zen real = listed.
- `scrape_goat.py` reads `commandcode.ai/docs/plans/goat`: table 0 is the catalog (48 models, names carry `Free`/`-50%`/`Off-peak…` suffixes), tables 2+3 carry per-model monthly credits at billed prices. Prices come from the credits tables; the catalog prices have `+N` caps badges and struck deal text. Free models (LongCat 2.0, Laguna S 2.1) fall back to the catalog. Off-peak models (DeepSeek V4 Flash/Vision/Pro) show one row per variant — the peak rate is in an annotation (`peak $X / $Y`), and read/write scale by the same ratio as input.

## Config

- `fetch/overrides.json`: `go.exclude` skips models (e.g. "MiniMax M2.5"). `forceLogs` is dead config — never read.
- `fetch/fetch_or.py` is a stale copy of `fetch_openrouter.py`, not in the pipeline. Don't edit it.

## CI / deploy

- `fetch.yml` runs on `main` only, daily 05:05 UTC; auto-commits `data/` as `chore: refresh pricing data`, which then triggers `deploy.yml`.
- `deploy.yml` also runs on push to `main` touching `web/**` or `data/**`. Builds the site, deploys to GitHub Pages under `/opencodego-compare/`.
- All work happens on `main`; `dev` was removed.

## Verify

- Pipeline: each step prints "Saved N …"; watch for table-count warnings.
- Frontend: `cd web && npm run build`. No test or lint scripts exist in the repo.