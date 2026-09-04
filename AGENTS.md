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

`run_all.py` runs `fetch_openrouter.py` → `fetch_endpoints.py` → `scrape_go.py` → `scrape_zen.py`.
`build_json.py` then merges all sources into `data/prices.json` and is run separately (CI does the same).
`build_json.py` must always run after any fetch step, or `prices.json` goes stale.

Gotchas:
- Scrapers index tables by position (`tables[1]`, `tables[3]`) on `opencode.ai/docs/*`. Layout changes print a warning and exit 0 — check stderr/row counts, not exit codes.
- `fetch_endpoints.py` and `scrape_zen.py` are regex-based and fragile. `scrape_zen.py` hardcodes the per-model privacy policy.
- Units: prices are $/1M tokens. Go effective = listed × 10 ÷ monthly allowance ($10/mo sub). OpenRouter real = listed × 1.055 fee × (1 + tax, default 24.25%). Zen real = listed.

## Config

- `fetch/overrides.json`: `go.exclude` skips models (e.g. "MiniMax M2.5"). `forceLogs` is dead config — never read.
- `fetch/fetch_or.py` is a stale copy of `fetch_openrouter.py`, not in the pipeline. Don't edit it.

## CI / deploy

- `fetch.yml` runs on `main` only, daily 05:05 UTC; auto-commits `data/` as `chore: refresh pricing data`, which then triggers `deploy.yml`.
- `deploy.yml` also runs on push to `main` touching `web/**` or `data/**`. Builds the site, deploys to GitHub Pages under `/opencodego-compare/`.
- Work happens on `dev`; pushes there do nothing.

## Verify

- Pipeline: each step prints "Saved N …"; watch for table-count warnings.
- Frontend: `cd web && npm run build`. No test or lint scripts exist in the repo.