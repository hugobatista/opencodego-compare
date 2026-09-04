# OpenCode Go vs Zen vs OpenRouter — Price Comparison 💸

Compare real-world LLM pricing across [OpenCode Go](https://opencode.ai/docs/go), [OpenCode Zen](https://opencode.ai/docs/zen), and [OpenRouter](https://openrouter.ai).

All prices are in **$ per 1M tokens** and normalized so you can compare apples to apples — listed prices, effective subscription costs, and OpenRouter's fee + tax markup are all visible side by side.

## 🖥️ Live demo

**[https://hugobatista.github.io/opencodego-compare/](https://hugobatista.github.io/opencodego-compare/)**

![Screenshot](https://img.shields.io/badge/status-live-2ea44f)

## ✨ Features

- **Three markets, one table** — Go, Zen, and OpenRouter rows merged into a single sortable, filterable view.
- **True cost, not list price** — hover any price cell to see how it was computed (effective Go price, OpenRouter fee + tax, or Zen listed price). Go effective prices assume the full monthly allowance is used.
- **Per-model filters** — filter by provider, context, latency, TPS, prompt logging, training on data, peak slots, and more.
- **Free Zen models highlighted** — free tiers are detected and labeled automatically.
- **Daily automated refresh** — prices are re-fetched by a scheduled CI job.

## 📊 How prices are computed

| Market | Formula |
| --- | --- |
| OpenCode Go | Effective = listed × (10 ÷ monthly allowance) |
| OpenRouter | Real = listed × 1.055 service fee × (1 + sales tax) |
| OpenCode Zen | Real = listed |

The Go effective price is a best-case rate: it assumes the flat $10/month fee is spread over the full monthly allowance included for that model. It is real only if you consume the whole allowance. Use less and the real cost per token is higher; go over and the excess is billed at listed price (Zen balance) or blocked.

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

The pipeline fetches live pricing from all three providers and regenerates `data/prices.json`.

```bash
pip install -r fetch/requirements.txt
python3 fetch/run_all.py
python3 fetch/build_json.py
```

Refresh order: `fetch_openrouter.py` → `fetch_endpoints.py` → `scrape_go.py` → `scrape_zen.py` → `build_json.py`.

> [!NOTE]
> `build_json.py` must always run after any fetch step, or `data/prices.json` goes stale.

Fetch overrides and exclusions live in `fetch/overrides.json`.

## 🤖 CI / deployment

- **`fetch.yml`** — runs daily at 05:05 UTC on `main`. Re-fetches data and auto-commits it as `chore: refresh pricing data`.
- **`deploy.yml`** — builds the site and deploys it to GitHub Pages under `/opencodego-compare/`. Triggers on pushes touching `web/**` or `data/**`, and on every completed fetch.

Development happens on the `dev` branch; pushes there are ignored by CI.

## 📄 License

[MIT](LICENSE)