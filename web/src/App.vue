<script setup>
import { ref, computed, watch } from 'vue'
import PriceTable from './components/PriceTable.vue'
import { readParams, writeParams, paramNum } from './lib/urlState.js'
import { useDark, planColor, planBg } from './lib/theme.js'
import prices from '../../data/prices.json'
import pkg from '../package.json'

const meta = prices.meta
const rows = prices.rows
const generated = prices.generated_date
const isDark = useDark()

const version = pkg.version
const repo = 'https://github.com/hugobatista/opencodego-compare'

const defaultTaxPct = meta.salesTaxDefault * 100
const taxPct = ref(taxFromUrl())
function taxFromUrl() {
  const n = paramNum(readParams(), 'tax', defaultTaxPct)
  return Math.min(100, Math.max(0, n))
}
watch(taxPct, (v) => {
  writeParams({ tax: Math.abs(v - defaultTaxPct) < 1e-9 ? '' : String(Math.round(v * 10) / 10) })
})
const tax = computed(() => taxPct.value / 100)
const feePct = ((meta.openrouterServiceFee ?? meta.serviceFee) * 100).toFixed(1)

const SOURCES = computed(() =>
  Object.entries(meta.gateways || {}).map(([key, g]) => ({ key, name: g.name, url: g.url, color: planColor(g, isDark.value) }))
)

const LEGEND = computed(() => {
  const out = []
  for (const [key, g] of Object.entries(meta.gateways || {})) {
    const plans = Object.values(meta.plans || {}).filter((p) => p.gateway === key)
    const names = plans.map((p) => p.name).join(', ')
    const head = `${g.name}`
    if (plans.some((p) => p.subPrice)) {
      out.push(`${head}: $${Math.min(...plans.map((p) => p.subPrice))}/mo sub. eff = listed × (sub ÷ monthly allowance) — only if you use the full allowance.`)
    } else if (plans.some((p) => p.feeTax)) {
      out.push(`${head}: real = listed × (1 + ${feePct}% fee, min $0.80) × (1 + tax).`)
    } else {
      out.push(`${head}: real = listed.`)
    }
  }
  return out
})
</script>

<template>
  <header class="hero">
    <h1>OpenCode Go vs alternatives</h1>
    <p class="subtitle">Model pricing comparison — refreshed {{ generated }}</p>
    <div class="srcs">
      <a
        v-for="s in SOURCES"
        :key="s.key"
        class="badge"
        :href="s.url"
        target="_blank"
        rel="noopener"
        :style="{ color: s.color, background: planBg(s.color) }"
      >
        {{ s.name }}
      </a>
    </div>
  </header>

  <div class="legend">
    <span><strong>Real</strong> price on top, <em>listed</em> below.</span>&nbsp;
    <span v-for="(txt, i) in LEGEND" :key="i">{{ txt }}</span>&nbsp;
    <span><strong>Allowance:</strong> monthly = usage included per month at full price; weekly = 50%; 5h = 20%.</span>
  </div>

  <div class="controls">
    <label class="taxctl">
      <span>Sales tax (OpenRouter only)</span>
      <div class="taxrow">
        <input
          type="range"
          min="0"
          max="100"
          step="0.1"
          v-model.number="taxPct"
        >
        <input
          type="number"
          min="0"
          max="100"
          step="0.1"
          v-model.number="taxPct"
        >
        <strong>{{ taxPct.toFixed(1) }}%</strong>
        <span class="default">default {{ (meta.salesTaxDefault * 100).toFixed(2) }}%</span>
      </div>
    </label>
    <p class="hint">Sort by clicking a column header. Drag headers to reorder columns, drag group labels to reorder groups — the layout is saved. Filter with the dropdowns (multi-select) and the min/max fields.</p>
  </div>

  <PriceTable :rows="rows" :meta="meta" :tax="tax" />

  <footer class="footer">
    <div class="f-meta">
      <span v-if="version">OpenCode Go vs alternatives · v{{ version }}</span>
      <span>by Hugo Batista</span>
      <a :href="repo + '/issues'" target="_blank" rel="noopener">Feedback &amp; issues</a>
    </div>
    <p class="f-disclaimer">
      Disclaimer: not affiliated with any of these companies. Prices shown may
      change — please confirm with the providers before making decisions.
    </p>
  </footer>
</template>