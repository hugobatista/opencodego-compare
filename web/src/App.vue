<script setup>
import { ref, computed } from 'vue'
import PriceTable from './components/PriceTable.vue'
import prices from '../../data/prices.json'
import pkg from '../package.json'

const meta = prices.meta
const rows = prices.rows
const generated = prices.generated_date

const version = pkg.version
const repo = 'https://github.com/hugobatista/opencodego-compare'

const taxPct = ref(meta.salesTaxDefault * 100)
const tax = computed(() => taxPct.value / 100)
const feePct = ((meta.openrouterServiceFee ?? meta.serviceFee) * 100).toFixed(1)

const SOURCES = [
  { key: 'go', name: 'OpenCode Go', url: meta.links.go },
  { key: 'or', name: 'OpenRouter', url: meta.links.or },
  { key: 'zen', name: 'OpenCode Zen', url: meta.links.zen },
]
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
        :class="'b-' + s.key"
        :href="s.url"
        target="_blank"
        rel="noopener"
      >
        {{ s.name }}
      </a>
    </div>
  </header>

  <div class="legend">
    <span><strong>Real</strong> price on top, <em>listed</em> below.</span>&nbsp;
    <span><strong>Go:</strong> eff = listed × (10 ÷ monthly allowance), $10/mo — only if you use the full monthly allowance.</span>&nbsp;
    <span><strong>OpenRouter:</strong> real = listed × (1 + {{ feePct }}% fee, min $0.80) × (1 + tax).</span>&nbsp;
    <span><strong>Zen:</strong> real = listed.</span>
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
    <p class="hint">Sort by clicking a column header. Filter with the dropdowns (multi-select) and the min/max fields.</p>
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