<script setup>
import { ref, reactive, computed } from 'vue'
import { buildRow } from '../lib/prices.js'
import MultiSelect from './MultiSelect.vue'

const props = defineProps({
  rows: { type: Array, required: true },
  meta: { type: Object, required: true },
  tax: { type: Number, default: 0.2425 },
})

const COLS = [
  { id: 'model',   label: 'Model',           kind: 'text',   key: 'textM' },
  { id: 'plan',    label: 'Plan',            kind: 'text',   key: 'textPlan' },
  { id: 'provider', label: 'Provider',       kind: 'text',   key: 'textP' },
  { id: 'in',      label: 'Input/1M',        kind: 'numeric', key: 'valIn' },
  { id: 'out',     label: 'Output/1M',       kind: 'numeric', key: 'valOut' },
  { id: 'rd',      label: 'Cached Read/1M',  kind: 'numeric', key: 'valRd' },
  { id: 'wr',      label: 'Cached Write/1M', kind: 'numeric', key: 'valWr' },
  { id: 'ctx',     label: 'Context',         kind: 'numeric', key: 'ctxVal' },
  { id: 'lat',     label: 'Latency (p50)',   kind: 'numeric', key: 'latVal' },
  { id: 'tps',     label: 'TPS (p50)',       kind: 'numeric', key: 'tpsVal' },
  { id: 'logs',    label: 'Log prompts',     kind: 'choice',  key: 'logs' },
  { id: 'trains',  label: 'Training',        kind: 'choice',  key: 'trains' },
  { id: 'peak',    label: 'Peak slots',      kind: 'choice',  key: 'peak' },
  { id: 'allowance', label: 'Allowance',     kind: 'text',   key: 'textA' },
  { id: 'notes',   label: 'Notes',           kind: 'text',   key: 'textN' },
]

const sortKey = ref('in')
const sortDir = ref(1)

const multiFilters = reactive({})
for (const c of COLS) {
  if (c.kind !== 'numeric') multiFilters[c.id] = []
}
const numFilters = reactive({})
for (const c of COLS) {
  if (c.kind === 'numeric') numFilters[c.id] = { min: '', max: '' }
}

const display = computed(() => props.rows.map((r) => buildRow(r, props.meta, props.tax)))

const onlyGoZen = ref(true)
const norm = (s) => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '')
const clean = (s) => norm(String(s || '').replace(/\s*\([^)]*\)\s*/g, ''))
const goZenBases = computed(() => {
  const set = new Set()
  for (const r of props.rows) {
    if (r.market === 'or') continue
    if (r.base) set.add(clean(r.base))
  }
  return [...set].sort((a, b) => b.length - a.length)
})
const orMatches = (r) => {
  if (r.market !== 'or' || !onlyGoZen.value) return true
  const seg = clean(String(r.base || r.model).split('/').pop().split(':')[0])
  if (goZenBases.value.includes(seg)) return true
  return goZenBases.value.some((b) => b.length >= 8 && seg.startsWith(b))
}

const pool = computed(() => display.value.filter(orMatches))

const orShow = ref(3)
const limited = computed(() => {
  const N = orShow.value
  if (N === 'all') return pool.value
  const byBase = new Map()
  const out = []
  for (const r of pool.value) {
    if (r.market !== 'or') { out.push(r); continue }
    const arr = byBase.get(r.base) || []
    arr.push(r)
    byBase.set(r.base, arr)
  }
  for (const arr of byBase.values()) {
    if (arr.length <= N) { out.push(...arr); continue }
    const sorted = [...arr].sort((a, b) => (a.pxCost ?? 1e18) - (b.pxCost ?? 1e18))
    out.push(...sorted.slice(0, N))
  }
  return out
})
const hiddenCount = computed(() => Math.max(0, pool.value.length - limited.value.length))

const distinctOptions = computed(() => {
  const map = {}
  for (const c of COLS) {
    if (c.kind === 'numeric') continue
    const set = new Set()
    for (const r of limited.value) {
      const v = r[c.key]
      if (v === null || v === undefined || v === '') continue
      set.add(String(v))
    }
    map[c.id] = [...set].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
  }
  return map
})

const filtered = computed(() => {
  return limited.value.filter((r) => {
    for (const c of COLS) {
      if (c.kind !== 'numeric') {
        const sel = multiFilters[c.id]
        const opts = distinctOptions.value[c.id] || []
        // empty or full selection = no filter
        if (sel && sel.length > 0 && sel.length < opts.length) {
          const v = r[c.key]
          if (v === null || v === undefined || !sel.includes(String(v))) return false
        }
      } else {
        const nf = numFilters[c.id]
        const v = r[c.key]
        if (nf.min !== '' || nf.max !== '') {
          if (v === null || v === undefined || Number.isNaN(Number(v))) return false
          if (nf.min !== '' && Number(v) < parseFloat(nf.min)) return false
          if (nf.max !== '' && Number(v) > parseFloat(nf.max)) return false
        }
      }
    }
    return true
  })
})

const sorted = computed(() => {
  const key = sortKey.value
  const dir = sortDir.value
  const col = COLS.find((c) => c.id === key)
  if (!col) return filtered.value
  const dataKey = col.key
  const isNum = col.kind === 'numeric'
  const rows = [...filtered.value]
  rows.sort((a, b) => {
    const av = a[dataKey]
    const bv = b[dataKey]
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1
    if (isNum) return (Number(av) - Number(bv)) * dir
    return String(av).localeCompare(String(bv), undefined, { numeric: true }) * dir
  })
  return rows
})

function toggleSort(id) {
  if (sortKey.value === id) sortDir.value *= -1
  else { sortKey.value = id; sortDir.value = 1 }
}

function reset() {
  for (const c of COLS) {
    if (c.kind !== 'numeric') multiFilters[c.id] = []
    else { numFilters[c.id].min = ''; numFilters[c.id].max = '' }
  }
  sortKey.value = 'in'
  sortDir.value = 1
  onlyGoZen.value = true
  orShow.value = 3
}

const colWidths = reactive({
  model: 14, plan: 10, provider: 9, 'in': 7, out: 7, rd: 6, wr: 6,
  ctx: 6, lat: 6, tps: 5, logs: 4, trains: 4, peak: 6, allowance: 7, notes: 12,
})

const resizing = ref(null)
function onResizeStart(e, colId) {
  e.preventDefault()
  resizing.value = { colId, startX: e.clientX }
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
}
function onResizeMove(e) {
  if (!resizing.value) return
  const th = e.target.closest('th')
  if (!th) return
  const dx = e.clientX - resizing.value.startX
  const W = th.parentElement.clientWidth
  const w = Math.round(((th.getBoundingClientRect().width + dx) / W) * 1000) / 10
  colWidths[resizing.value.colId] = Math.max(4, w)
}
function onResizeEnd() {
  resizing.value = null
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
}

function tableStyle() {
  return 'table-layout: fixed; width: 100%; min-width: 640px;'
}
</script>

<template>
  <div>
    <div class="subbar">
      <label class="toggle">
        <input type="checkbox" v-model="onlyGoZen">
        <span>Only OpenRouter models also on Go/Zen</span>
      </label>
      <label class="plimit">
        <span>Cheapest OR providers/model:</span>
        <select v-model="orShow">
          <option :value="1">1</option>
          <option :value="2">2</option>
          <option :value="3">3</option>
          <option :value="4">4</option>
          <option :value="5">5</option>
          <option value="all">All</option>
        </select>
      </label>
      <span class="count">
        <strong>{{ sorted.length }}</strong> of {{ limited.length }} models
      </span>
      <span v-if="hiddenCount" class="count hint">{{ hiddenCount }} provider rows hidden</span>
      <button type="button" class="reset-btn" @click="reset">✕ Reset filters</button>
    </div>

    <div class="tablewrap">
      <table :style="tableStyle()">
        <colgroup>
          <col v-for="c in COLS" :key="c.id" :style="{ width: colWidths[c.id] + '%' }">
        </colgroup>
        <thead>
          <tr class="cols">
            <th
              v-for="c in COLS"
              :key="c.id"
              :class="[c.kind === 'numeric' ? 'num' : '', sortKey === c.id ? 'active' : '']"
              @click="toggleSort(c.id)"
              :title="c.kind === 'numeric' ? 'Click to sort' : 'Click to sort'"
            >
              <span class="th-inner">{{ c.label }}</span>
              <span v-if="sortKey === c.id" class="arrow">{{ sortDir < 0 ? '▲' : '▼' }}</span>
              <span class="resize-handle" @mousedown.stop="onResizeStart($event, c.id)"></span>
            </th>
          </tr>
          <tr class="filters">
            <th v-for="c in COLS" :key="c.id" :class="c.kind === 'numeric' ? 'num' : ''">
              <template v-if="c.kind === 'numeric'">
                <span class="rng">
                  <input v-model="numFilters[c.id].min" placeholder="min" @input.stop>
                  <input v-model="numFilters[c.id].max" placeholder="max" @input.stop>
                </span>
              </template>
              <template v-else>
                <MultiSelect
                  :options="distinctOptions[c.id] || []"
                  v-model:selected="multiFilters[c.id]"
                  :label="c.label"
                />
              </template>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in sorted" :key="i">
            <td class="model">{{ r.model }}</td>
            <td>
              <a
                v-if="r.planLink"
                :href="r.planLink"
                target="_blank"
                rel="noopener"
                class="plan"
                :class="'p-' + r.market"
              >{{ r.plan }}</a>
              <span v-else class="plan" :class="'p-' + r.market">{{ r.plan }}</span>
            </td>
            <td>
              <a
                v-if="r.provider"
                :href="r.providerLink"
                target="_blank"
                rel="noopener"
                class="prov"
              >{{ r.provider }}</a>
              <span v-else class="dash">—</span>
            </td>
            <td class="num">
              <div class="cell-disp" :class="{ dual: r.inCell.pair }">
                <div class="real" :title="r.inCell.realTip || null">{{ r.inCell.real }}</div>
                <div v-if="r.inCell.pair" class="list" :title="r.inCell.listTip || null">{{ r.inCell.list }}</div>
              </div>
            </td>
            <td class="num">
              <div class="cell-disp" :class="{ dual: r.outCell.pair }">
                <div class="real" :title="r.outCell.realTip || null">{{ r.outCell.real }}</div>
                <div v-if="r.outCell.pair" class="list" :title="r.outCell.listTip || null">{{ r.outCell.list }}</div>
              </div>
            </td>
            <td class="num">
              <div class="cell-disp" :class="{ dual: r.rdCell.pair }">
                <div class="real" :title="r.rdCell.realTip || null">{{ r.rdCell.real }}</div>
                <div v-if="r.rdCell.pair" class="list" :title="r.rdCell.listTip || null">{{ r.rdCell.list }}</div>
              </div>
            </td>
            <td class="num">
              <div class="cell-disp" :class="{ dual: r.wrCell.pair }">
                <div class="real" :title="r.wrCell.realTip || null">{{ r.wrCell.real }}</div>
                <div v-if="r.wrCell.pair" class="list" :title="r.wrCell.listTip || null">{{ r.wrCell.list }}</div>
              </div>
            </td>
            <td class="num" :title="'Context length'">{{ r.ctxDisp }}</td>
            <td class="num" :title="'50th percentile latency'">{{ r.latDisp }}</td>
            <td class="num" :title="'50th percentile tokens per second'">{{ r.tpsDisp }}</td>
            <td class="yesno" :class="r.logs" :title="'Provider logs your prompts'">{{ r.logs }}</td>
            <td class="yesno" :class="r.trains" :title="'Provider trains on your data'">{{ r.trains }}</td>
            <td :title="'Peak and off-peak hours'">{{ r.peak || '—' }}</td>
            <td class="allow" v-html="r.allowance" title="Monthly allowance = price per month at full price; weekly = 50%; 5h = 20%"></td>
            <td class="notes">{{ r.notes }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.subbar {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  font-size: 0.95rem; margin-bottom: 10px;
}
.subbar strong { color: var(--accent-strong); }
.toggle {
  display: inline-flex; align-items: center; gap: 6px; cursor: pointer;
  font-size: 0.9rem; user-select: none;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 8px; padding: 5px 10px;
}
.toggle input { accent-color: var(--accent); cursor: pointer; }
.plimit {
  display: inline-flex; align-items: center; gap: 6px; cursor: pointer;
  font-size: 0.88rem; color: var(--muted);
  background: var(--card); border: 1px solid var(--border);
  border-radius: 8px; padding: 5px 10px;
}
.plimit select {
  background: var(--bg); color: var(--fg);
  border: 1px solid var(--border); border-radius: 5px;
  font-size: 0.88rem; padding: 2px 4px; cursor: pointer;
}
.hint { color: var(--muted); }
.reset-btn {
  padding: 5px 12px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg); color: var(--fg); cursor: pointer; font-size: 0.88rem;
  transition: all 0.15s ease;
}
.reset-btn:hover { border-color: var(--accent); color: var(--accent); }
.count { color: var(--muted); }

.tablewrap {
  overflow: auto; max-height: calc(100vh - 205px);
  border: 1px solid var(--border); border-radius: 10px;
  background: var(--bg); box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
table {
  border-collapse: collapse; font-size: 0.82rem; font-variant-numeric: tabular-nums;
}
th, td {
  border-bottom: 1px solid var(--border); padding: 6px 8px;
  text-align: left;
}
th { vertical-align: middle; }
td { vertical-align: top; }

thead {
  position: sticky; top: 0; z-index: 5;
}
thead th {
  background: var(--thead);
  user-select: none;
}
thead tr.cols th {
  cursor: pointer; border-bottom: 1px solid var(--border);
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--muted); font-weight: 700; padding: 6px 8px;
  white-space: normal; line-height: 1.3; overflow-wrap: anywhere;
}
thead tr.cols th.active { color: var(--accent-strong); }
thead tr.cols th:hover { color: var(--accent); }
thead tr.filters th { cursor: default; padding: 4px 6px; overflow: visible; }
.th-inner { pointer-events: none; }
.arrow { font-size: 0.5rem; pointer-events: none; margin-left: 1px; }

.num, th.num { text-align: right; }
td.num { font-weight: 600; }
.cell-disp .real { font-weight: 600; }
.cell-disp .list { color: var(--muted); font-size: 0.74rem; font-weight: 400; margin-top: 1px; }
.free { color: var(--ok); font-weight: 700; }

td.model { font-weight: 600; overflow-wrap: anywhere; }

a.prov { color: var(--accent); text-decoration: none; }
a.prov:hover { text-decoration: underline; }
.dash { color: var(--muted); }
a.plan { text-decoration: none; }
a.plan:hover { text-decoration: underline; }
.plan { font-weight: 600; font-size: 0.8rem; white-space: nowrap; }
.p-go  { color: #2e7d32; }
.p-or  { color: #2b6cb0; }
.p-zen { color: #7c3aed; }
:global(.dark) .p-go, :global(html[data-theme=dark]) .p-go  { color: #a5d6a7; }
:global(.dark) .p-or,  :global(html[data-theme=dark]) .p-or  { color: #90caf9; }
:global(.dark) .p-zen, :global(html[data-theme=dark]) .p-zen { color: #b39ddb; }

.yesno { font-size: 0.76rem; }
.yesno.Yes { color: var(--bad); font-weight: 600; }
.yesno.No { color: var(--ok); }
td.notes { color: var(--muted); overflow-wrap: anywhere; }
td.allow { color: var(--muted); font-size: 0.76rem; line-height: 1.25; }

tbody tr { transition: background 0.08s ease; }
tbody tr:nth-child(even) { background: var(--row-alt); }
tbody tr:hover { background: var(--row-hover); }

.resize-handle {
  display: inline-block; width: 5px; cursor: col-resize;
  position: absolute; right: 0; top: 0; bottom: 0;
  border-radius: 2px;
}
.resize-handle:hover { background: var(--accent); opacity: 0.5; }
thead tr.cols th { position: relative; }

.rng { display: flex; gap: 2px; justify-content: flex-end; }
.rng input {
  width: 50%; min-width: 0; box-sizing: border-box; font-size: 0.72rem;
  padding: 3px 5px; border: 1px solid var(--border); border-radius: 4px;
  background: var(--bg); color: var(--fg); text-align: right;
}
.rng input:focus { outline: none; border-color: var(--accent); }
.rng input::placeholder { color: var(--muted); }
</style>