# OpenCode Go vs Zen vs OpenRouter — Price Comparison 💸

Compare real-world LLM pricing across [OpenCode Go](https://opencode.ai/docs/go), [Command Code](https://commandcode.ai) (GOAT, Pro, Max), [OpenCode Zen](https://opencode.ai/docs/zen), [OpenRouter](https://openrouter.ai), and [DeepInfra](https://deepinfra.com/pricing).

All prices are in **$ per 1M tokens** and normalized so you can compare apples to apples — listed prices, effective subscription costs, and OpenRouter's fee + tax markup are all visible side by side.

## 🖥️ Live demo

**[https://hugobatista.github.io/opencodego-compare/](https://hugobatista.github.io/opencodego-compare/)**

![Screenshot](https://img.shields.io/badge/status-live-2ea44f)

## ✨ Features

- **Eight markets, one table** — OpenCode Go, Command Code GOAT/Pro/Max 10x/Max 20x, Zen, OpenRouter, and DeepInfra rows merged into a single sortable, filterable view.
- **True cost, not list price** — hover any price cell to see how it was computed (effective subscription price, OpenRouter fee + tax, or listed price). Subscription effective prices assume the full monthly allowance is used.
- **Per-model filters** — filter by provider, context, latency, TPS, prompt logging, training on data, peak slots, and more.
- **Free models highlighted** — free tiers are detected and labeled automatically.
- **JSON-driven display** — providers, plans, labels, providers and badge colors come from `prices.json` `meta` (via `fetch/plans.json`), not frontend code.
- **Daily automated refresh** — prices are re-fetched by a scheduled CI job.

## 📊 How prices are computed

| Market | Formula |
| --- | --- |
| OpenCode Go | Effective = listed × (10 ÷ monthly allowance) |
| Command Code GOAT | Effective = listed × (10 ÷ per-model monthly credits) |
| Command Code Pro | Effective = listed × (20 ÷ per-model monthly credits) |
| Command Code Max 10x/20x | Effective = listed × (100/200 ÷ per-model monthly credits) |
| OpenRouter | Real = listed × 1.055 service fee × (1 + sales tax) |
| OpenCode Zen | Real = listed |
| DeepInfra | Real = listed; Priority ≈1.5× and Flex ≈0.8× shown as extra rows |

Subscription effective prices are best-case rates: they assume the flat monthly fee is spread over the full monthly allowance or per-model credits included. They are real only if you consume the whole allowance. Use less and the real cost per token is higher; go over and the excess is billed at listed price (Zen balance), at regular rates (Command Code pay-as-you-go credits) or blocked.

The sales tax defaults to 24.25% and is adjustable in the UI. See `data/prices.json` → `meta` for the current defaults.

## 🗂️ Project layout

```
├── fetch/          # Python data pipeline
├── data/           # Generated JSON (prices.json is the only file the frontend reads)
├── web/            # Vue 3 + Vite frontend
└── .github/        # CI workflows (daily fetch + deploy to GitHub Pages)
```

## 🚀 Get started

### Frontend

```bash
cd web
npm install
npm run dev
```

Then open `http://localhost:5173`. Build with `npm run build`.

### Data pipeline

The pipeline fetches live pricing from all eight markets and regenerates `data/prices.json`.

```bash
pip install -r fetch/requirements.txt
python3 fetch/run_all.py
python3 fetch/build_json.py
```

All Command Code/OpenCode scrapers and plans metadata are independent JSON configs and scripts. `build_json.py` merges everything and copies `fetch/plans.json` into `prices.json` `meta`.

> [!NOTE]
> `build_json.py` must always run after any fetch step, or `data/prices.json` goes stale.

Fetch overrides and exclusions live in `fetch/overrides.json`; provider/plan display metadata lives in `fetch/plans.json`.

## 🤖 CI / deployment

- **`fetch.yml`** — runs daily at 05:05 UTC on `main`. Re-fetches data and auto-commits it as `chore: refresh pricing data`.
- **`deploy.yml`** — builds the site and deploys it to GitHub Pages under `/opencodego-compare/`. Triggers on pushes touching `web/**` or `data/**`, and on every completed fetch.

All work happens on `main`.

## 📄 License

[MIT](LICENSE)