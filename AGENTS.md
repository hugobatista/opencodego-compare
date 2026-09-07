# AGENTS.md

Model pricing comparison site for OpenCode Go vs Zen vs Command Code vs OpenRouter.

## Layout

- `fetch/` — Python data pipeline. Needs `pip install -r fetch/requirements.txt`.
- `data/` — generated JSON. `prices.json` is the only file the frontend reads.
- `web/` — Vue 3 + Vite. Imports `data/prices.json` directly via `../../data/prices.json` (Vite `server.fs.allow: ['..']`).

## Data pipeline

Refresh in this exact order:

```
python3 fetch/run_all.py && python3 fetch/build_json.py
```

`run_all.py` stage 1 (`fetch_openrouter.py` + `fetch_deepinfra.py` + `scrape_opencode_go.py` + `scrape_opencode_zen.py` + `scrape_command_code_goat.py` + `scrape_command_code_pro.py` + `scrape_command_code_max.py`) runs in parallel, then `fetch_endpoints.py`, then `build_json.py`.
`build_json.py` then merges all sources into `data/prices.json` and is run separately (CI does the same).
`build_json.py` must always run after any fetch step, or `prices.json` goes stale.

Gotchas:
- Scrapers index tables by position (`tables[1]`, `tables[3]`) on `opencode.ai/docs/*`. Layout changes print a warning and exit 0 — check stderr/row counts, not exit codes.
- `fetch_endpoints.py` uses the structured OpenRouter API per model and stores a sha1 `digest` in `openrouter-endpoints.json`. The heavy HTML page is only re-fetched for models whose API digest changed (it carries `data_policy`, which the API lacks). The first run after this change fetches all HTML pages; later runs only changed models. `scrape_opencode_zen.py` uses regex on model names to hardcode the per-model privacy policy.
- `fetch_modelmarkets.py` fetches the models sitemap (allowed by robots.txt), caches `data/modelmarkets.json`, and re-fetches only pages whose sitemap `lastmod` changed. It regex-extracts the Hugging Face repo from each page (`hf` field) — only open-weight models have one. `build_json.py` matches every row to a slug by normalized name (OpenRouter/DeepInfra: `base` is the last segment of the id; Go/Zen/GOAT: name minus `(...)`/` Free`) — models absent from the modelmarkets catalog get no `modelLink`/`hfLink`. Non-`openrouter` rows get `developerId = org/slug` and `maker` from the match; `openrouter` rows keep the full OR id as `developerId`. Unmatched rows fall back to `null` and emit a warning to stderr.
- Families: `model` is the family (e.g. `DeepSeek V4 Flash`), `variant` the specific model (e.g. `DeepSeek V4 Flash (Off-Peak)`). `fetch/model_families.json` maps a normalized devId stem to the family name; `build_json.py` falls back to a heuristic (strips maker prefix, dates, variant tokens) and prints a `Family warning: no mapping for …` line to stderr for every unmapped/devId-less family — watch stderr and grow the map, don't rely on heuristic output. `fetch/makers.json` maps org/prefix slugs (normalized) to display names for the `maker` column.
- Units: prices are $/1M tokens. Go effective = listed × 10 ÷ monthly allowance ($10/mo sub). GOAT effective = listed × 10 ÷ per-model monthly credits ($10/mo sub; credits $20–$70; models without explicit credits default to $20). Pro effective = listed × 20 ÷ per-model monthly credits ($20/mo sub; credits $20–$80, default $30). Max effective = listed × sub ÷ per-model credits, sub = 100 (Max 10x) or 200 (Max 20x) and credits = 100/150 (10x) or 200/300 (20x): standard models factor to ×0.667 and premium to ×1.0 on both tiers. OpenRouter real = listed × 1.055 fee × (1 + tax, default 24.25%). Zen real = listed. DeepInfra real = listed (from the API `input_tokens`/`output_tokens`, cached reads from `cache_read_tokens`; only `chat`-tagged models are kept — embeddings are excluded). DeepInfra Priority/Flex tiers are extra rows at base × the model's multiplier (~1.5× / ~0.8×).
- `scrape_command_code_goat.py` reads `commandcode.ai/docs/plans/goat`: table 0 is the catalog (48 models, names carry `Free`/`-50%`/`Off-peak…` suffixes), tables 2+3 carry per-model monthly credits at billed prices. Prices come from the credits tables; the catalog prices have `+N` caps badges and struck deal text. Free models (LongCat 2.0, Laguna S 2.1) fall back to the catalog. Off-peak models (DeepSeek V4 Flash/Vision/Pro) show one row per variant — the peak rate is in an annotation (`peak $X / $Y`), and read/write scale by the same ratio as input.
- `scrape_command_code_pro.py` reads `commandcode.ai/docs/plans/pro`: 5+ tables. Table 0 is the 61-model catalog with **shifted columns vs GOAT** — index 1 = context, 2 = intelligence, 3 = tok/s, 4–7 = prices. Table 1 (index 1) is a request-estimate table — skip it. Tables 2/3/4 are per-model credits tables (51 models). Older models (Kimi K2.6, GLM-5, …) live only in a React RSC accordion, not a table; they are NOT scraped — they fall through the catalog fallback with `DEFAULT_CREDITS = 30` which matches the published "standard $30 credits" (catalog fallback only needs prices + context row 0). Premium models (Claude/GPT/Gemini) sit in table 3 at $20 credits (factor = 1.0). Off-peak handling is identical to GOAT.
- `scrape_command_code_max.py` reads `commandcode.ai/docs/plans/max`: the per-model table mixes catalog + credits and is **located by header** (row containing `Max 10× credits`), not position — the page has an at-a-glance table, a usage-limits table and a request-estimate table before it. Each model (69) emits two rows with `market` `command-code-max-10x` and `command-code-max-20x`; credits 10x/20x come from columns 5/6 ($100/$200 premium tier, $150/$300 standard tier). No off-peak on this page; deals (MiniMax M3 2×, …) don't change the listed prices. Context/tps are null and backfilled from OpenRouter by `fill_context`.
- `fetch_deepinfra.py` hits `api.deepinfra.com/v1/openai/models`, filters to `chat`-tagged token-priced models (base $/1M prices), writes `data/deepinfra.json`. It also calls `api.deepinfra.com/models/list` for per-model service-tier multipliers (`rate_per_service_tier_priority`/`_flex`, null = unsupported) and emits an extra row per supported tier: `variant` = `<base> (Priority)` (≈1.5×) and `<base> (Flex)` (≈0.8×), price = base × multiplier; `variantLink` stays `https://deepinfra.com/<id>` for all tiers of a model. `base` = last path segment of the id (like OpenRouter) for modelmarkets matching. About 35 DeepInfra models are absent from the modelmarkets catalog and get no `modelLink`/`maker`/`developerId` — expected. `assign_variants` in `build_json.py` preserves an explicit `variant` (the tier suffixes); other sources don't set one and fall back to the model name.
- Privacy columns (`logsPrompts`, `trainsOnData`): the frontend renders `true`→Yes (red), `false`→No (green), `null`→? (yellow). Only assert `false` (No) when the provider's own docs state it. Never default to `false` just because a source doesn't log content. Sources today — Zen: `scrape_opencode_zen.py` `zen_policy()` mirrors the Privacy section of `opencode.ai/docs/zen`; all free models are listed there as exceptions to the zero-retention default, so each free model that says "collected data may be used…" must be `logsPrompts=True` + `trainsOnData=True`. Go: scraped from the docs retention table. Command Code (all plans): docs never assert per-model ZDR, so all rows are `null` (?) — do not change to `false`. OpenRouter: from the `dataPolicy` on each endpoint's HTML page (via `openrouter-endpoints.json`). DeepInfra: from `docs.deepinfra.com/account/data-privacy` — first-party hosting asserts no retention + no training (`false`/`false`); Google (`gemini-…`) and Anthropic (`claude-…`) models are routed to the model owner, so `logsPrompts=True` (Google logs for abuse checks / Anthropic per Trust Center) with `trainsOnData=False`. Watch out for free/contributor/trial tiers — they are the places where "logs=No" is usually wrong. Each row also carries a `privacyNote` (human-readable conclusion shown in the cell tooltips) — Zen: from `zen_policy`; Go: the raw retention-table cell; Command Code (all plans): the market-level `99% of models route via ZDR-capable upstreams, most ZDR by default` string on every row; DeepInfra: the policy note plus `ZDR: held in memory only, no logging/training` for first-party; OpenRouter: empty, its policy has no prose. Never hardcode these strings in the frontend — `PriceTable.vue` only reads `row.privacyNote`.

## Taxonomy

- A **gateway** is the reseller/platform that owns the plan: OpenCode, Command Code, OpenRouter, DeepInfra. Plans belong to gateways, not providers.
- A **provider** is who actually serves the model. OpenRouter discloses per-endpoint providers; OpenCode/Command Code do not (rows show `—`). DeepInfra is both gateway and provider (its own plan + resold via OpenRouter). The provider display name/url resolution is config in `plans.json` (`gateways.*.providers`), applied by `build_json.py`; the binary `rows` carry `gateway` and `provider` display names.
- Column order: maker, model, variant, gateway, plan, provider.

## Market naming

`market` values are full plan names: `opencode-go`, `command-code-goat`, `command-code-pro`, `command-code-max-10x`, `command-code-max-20x`, `opencode-zen`, `openrouter`, `deepinfra`. There is no `market` column — the `plan` column holds the display label. Keep full names; avoid short acronyms (`or`, `goat`) when adding future Command Code plans.

Display metadata (gateway/plan labels, provider, URLs, subscription price, badge colors) is **not hardcoded in the frontend** — it lives in `fetch/plans.json`, which `build_json.py` copies into `prices.json` `meta.gateways`/`meta.plans`. **Colors and header labels are per gateway, not per plan** — gateways carry `color`/`colorDark`; plans do not. The frontend iterates `meta.gateways` for badges/legend (`App.vue` SOURCES/LEGEND) and colors the plan cell via `row.gatewayMeta`; rows carry `plan` (label), `gateway` (slug), and the market key must match a `meta.plans` key. Adding a new gateway = a `plans.json` entry + a scraper + a data file; no frontend changes. Adding a new provider to an existing gateway = one entry in that gateway's `providers` map.

## Config

- `fetch/plans.json`: gateways (name/url, per-gateway `providers` display-name map, optional `providerLink`, `color`/`colorDark` — per gateway, not per plan) and plans (name, gateway, url, `subPrice`, `feeTax`). Single source for all frontend display metadata.
- `fetch/overrides.json`: `opencode-go.exclude` skips models (e.g. "MiniMax M2.5"). `forceLogs` is dead config — never read.
- `fetch/fetch_or.py` is a stale copy of `fetch_openrouter.py`, not in the pipeline. Don't edit it.

## CI / deploy

- `fetch.yml` runs on `main` only, daily 05:05 UTC; auto-commits `data/` as `chore: refresh pricing data`, which then triggers `deploy.yml`.
- `deploy.yml` also runs on push to `main` touching `web/**` or `data/**`. Builds the site, deploys to GitHub Pages under `/opencodego-compare/`.
- All work happens on `main`; `dev` was removed.

## Verify

- Pipeline: each step prints "Saved N …"; watch for table-count warnings.
- Frontend: `cd web && npm run build`. No test or lint scripts exist in the repo.