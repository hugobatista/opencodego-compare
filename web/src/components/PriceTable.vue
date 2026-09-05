<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { buildRow } from '../lib/prices.js'
import { readParams, writeParams, paramStr, paramList } from '../lib/urlState.js'
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

const urlParams = readParams()

const sortRaw = paramStr(urlParams, 'sort', '')
if (sortRaw) {
  const [k, d] = sortRaw.split(':')
  const col = COLS.find((c) => c.id === k)
  if (col) sortKey.value = k
  if (d === '-1') sortDir.value = -1
}
if (paramStr(urlParams, 'gozen', '1') === '0') onlyGoZen.value = false
const orRaw = paramStr(urlParams, 'orshow', '3')
if (orRaw === 'all') orShow.value = 'all'
else if (Number.isInteger(Number(orRaw)) && Number(orRaw) >= 1 && Number(orRaw) <= 5) orShow.value = Number(orRaw)

for (const c of COLS) {
  if (c.kind === 'numeric') {
    numFilters[c.id] = {
      min: paramStr(urlParams, 'min_' + c.id, ''),
      max: paramStr(urlParams, 'max_' + c.id, ''),
    }
  } else {
    multiFilters[c.id] = paramList(urlParams, 'f_' + c.id)
  }
}

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
  if (suppressClick.value) { suppressClick.value = false; return }
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
  writeParams(toParams())
}

function toParams() {
  const out = {}
  out.sort = sortKey.value === 'in' && sortDir.value === 1 ? '' : sortKey.value + ':' + sortDir.value
  out.gozen = onlyGoZen.value ? '' : '0'
  out.orshow = orShow.value === 3 ? '' : String(orShow.value)
  for (const c of COLS) {
    if (c.kind === 'numeric') {
      out['min_' + c.id] = numFilters[c.id].min
      out['max_' + c.id] = numFilters[c.id].max
    } else {
      const opts = distinctOptions.value[c.id] || []
      const sel = multiFilters[c.id]
      out['f_' + c.id] = sel.length > 0 && sel.length < opts.length ? sel.map(encodeURIComponent).join(',') : ''
    }
  }
  return out
}

watch(toParams, (p) => writeParams(p), { deep: true })

const linkCopied = ref(false)
function copyLink() {
  const ok = () => {
    linkCopied.value = true
    setTimeout(() => (linkCopied.value = false), 1500)
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(location.href).then(ok, () => { fallbackCopy(location.href); ok() })
  } else {
    fallbackCopy(location.href)
    ok()
  }
}
function fallbackCopy(text) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  try { document.execCommand('copy') } catch (e) { /* ignore */ }
  document.body.removeChild(ta)
}

const DEFAULT_WIDTHS = {
  model: 14, plan: 10, provider: 9, 'in': 7, out: 7, rd: 6, wr: 6,
  ctx: 6, lat: 6, tps: 5, logs: 4, trains: 4, peak: 6, allowance: 7, notes: 12,
}
const colWidths = reactive({ ...DEFAULT_WIDTHS })
const colOrder = ref(COLS.map((c) => c.id))

const CELL_TITLES = {
  ctx: 'Context length',
  lat: '50th percentile latency',
  tps: '50th percentile tokens per second',
  logs: 'Provider logs your prompts',
  trains: 'Provider trains on your data',
  peak: 'Peak and off-peak hours',
  allowance: 'Monthly allowance = usage included per month at full price; weekly = 50%; 5h = 20%. Effective Go price applies only if you use the full monthly allowance',
}
const NUM_DISP = { ctx: 'ctxDisp', lat: 'latDisp', tps: 'tpsDisp' }

function colById(id) { return COLS.find((c) => c.id === id) }
function tdTitle(colId) { return CELL_TITLES[colId] || undefined }
function cellClass(colId, r) {
  if (colId === 'model') return 'model'
  if (colId === 'logs' || colId === 'trains') return 'yesno ' + r[colId]
  if (colId === 'allowance') return 'allow'
  if (colId === 'notes') return 'notes'
  if (colById(colId).kind === 'numeric') return 'num'
  return ''
}

function loadLayout() {
  try {
    const raw = localStorage.getItem('oc_layout')
    if (!raw) return
    const s = JSON.parse(raw)
    if (s && Array.isArray(s.order)) {
      const valid = s.order.filter((id) => colById(id))
      const rest = COLS.filter((c) => !valid.includes(c.id)).map((c) => c.id)
      colOrder.value = [...valid, ...rest]
    }
    if (s && s.widths && typeof s.widths === 'object') {
      for (const id of Object.keys(s.widths)) {
        const w = Number(s.widths[id])
        if (colById(id) && Number.isFinite(w) && w >= 4) colWidths[id] = w
      }
    }
  } catch (e) { /* ignore corrupted layout */ }
}
function saveLayout() {
  try {
    localStorage.setItem('oc_layout', JSON.stringify({ order: colOrder.value, widths: colWidths }))
  } catch (e) { /* ignore */ }
}
function resetLayout() {
  colOrder.value = COLS.map((c) => c.id)
  for (const id of Object.keys(DEFAULT_WIDTHS)) colWidths[id] = DEFAULT_WIDTHS[id]
  saveLayout()
}
loadLayout()

const drag = ref(null)
const suppressClick = ref(false)
function onHeaderPointerDown(e, colId) {
  if (e.button !== undefined && e.button !== 0) return
  drag.value = { id: colId, startX: e.clientX, startY: e.clientY, active: false, overId: null, before: false }
  window.addEventListener('pointermove', onHeaderPointerMove)
  window.addEventListener('pointerup', onHeaderPointerUp)
  window.addEventListener('pointercancel', onHeaderPointerUp)
}
function onHeaderPointerMove(e) {
  const d = drag.value
  if (!d) return
  if (!d.active) {
    if (Math.abs(e.clientX - d.startX) < 5 && Math.abs(e.clientY - d.startY) < 5) return
    d.active = true
    suppressClick.value = true
  }
  const th = e.target && e.target.closest ? e.target.closest('th') : null
  const colId = th && th.dataset.col
  if (!colId) { d.overId = null; return }
  if (colId === d.id) { d.overId = null; return }
  const rect = th.getBoundingClientRect()
  const before = e.clientX < rect.left + rect.width / 2
  if (d.overId === colId && d.before === before) return
  d.overId = colId
  d.before = before
  moveCol(d.id, colId, before)
}
function moveCol(fromId, toId, before) {
  const arr = [...colOrder.value]
  const from = arr.indexOf(fromId)
  if (from < 0) return
  const [moved] = arr.splice(from, 1)
  const to = arr.indexOf(toId)
  if (to < 0) return
  arr.splice(before ? to : to + 1, 0, moved)
  colOrder.value = arr
}
function onHeaderPointerUp() {
  const d = drag.value
  if (!d) return
  window.removeEventListener('pointermove', onHeaderPointerMove)
  window.removeEventListener('pointerup', onHeaderPointerUp)
  window.removeEventListener('pointercancel', onHeaderPointerUp)
  if (d.active) {
    saveLayout()
    setTimeout(() => { suppressClick.value = false }, 0)
  }
  drag.value = null
}

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
  saveLayout()
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
      <button
        type="button"
        class="reset-btn"
        :class="{ copied: linkCopied }"
        @click="copyLink"
        :disabled="linkCopied"
      >{{ linkCopied ? 'Copied!' : 'Copy link' }}</button>
      <button type="button" class="reset-btn" @click="resetLayout">Reset layout</button>
    </div>

    <div class="tablewrap">
      <table :style="tableStyle()">
        <colgroup>
          <col v-for="colId in colOrder" :key="colId" :style="{ width: colWidths[colId] + '%' }">
        </colgroup>
        <thead>
          <tr class="cols">
            <th
              v-for="colId in colOrder"
              :key="colId"
              :class="[
                colById(colId).kind === 'numeric' ? 'num' : '',
                sortKey === colId ? 'active' : '',
                drag && drag.active && drag.id === colId ? 'dragging' : '',
                drag && drag.active && drag.id !== colId && drag.overId === colId ? (drag.before ? 'drop-left' : 'drop-right') : '',
              ]"
              @click="toggleSort(colId)"
              title="Click to sort. Drag to reorder."
              :data-col="colId"
              @pointerdown="onHeaderPointerDown($event, colId)"
            >
              <span class="th-inner">{{ colById(colId).label }}</span>
              <span v-if="sortKey === colId" class="arrow">{{ sortDir < 0 ? '▲' : '▼' }}</span>
              <span class="resize-handle" @pointerdown.stop @mousedown.stop="onResizeStart($event, colId)"></span>
            </th>
          </tr>
          <tr class="filters">
            <th v-for="colId in colOrder" :key="colId" :data-col="colId" :class="colById(colId).kind === 'numeric' ? 'num' : ''">
              <template v-if="colById(colId).kind === 'numeric'">
                <span class="rng">
                  <input v-model="numFilters[colId].min" placeholder="min" @input.stop>
                  <input v-model="numFilters[colId].max" placeholder="max" @input.stop>
                </span>
              </template>
              <template v-else>
                <MultiSelect
                  :options="distinctOptions[colId] || []"
                  v-model:selected="multiFilters[colId]"
                  :label="colById(colId).label"
                />
              </template>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in sorted" :key="i">
            <td
              v-for="colId in colOrder"
              :key="colId"
              :class="cellClass(colId, r)"
              :title="tdTitle(colId)"
            >
              <template v-if="colId === 'model'">
                <div class="cell-model">
                  <span class="model-name">{{ r.model }}</span>
                  <span class="model-links">
                    <a v-if="r.modelLink" :href="r.modelLink" target="_blank" rel="noopener" class="mlink">ModelMarkets</a>
                    <a v-if="r.hfLink" :href="r.hfLink" target="_blank" rel="noopener" class="mlink">HuggingFace</a>
                  </span>
                </div>
              </template>

              <template v-else-if="colId === 'plan'">
                <a
                  v-if="r.planLink"
                  :href="r.planLink"
                  target="_blank"
                  rel="noopener"
                  class="plan"
                  :class="'p-' + r.market"
                >{{ r.plan }}</a>
                <span v-else class="plan" :class="'p-' + r.market">{{ r.plan }}</span>
              </template>

              <template v-else-if="colId === 'provider'">
                <a
                  v-if="r.provider"
                  :href="r.providerLink"
                  target="_blank"
                  rel="noopener"
                  class="prov"
                >{{ r.provider }}</a>
                <span v-else class="dash">—</span>
              </template>

              <template v-else-if="colId === 'in' || colId === 'out' || colId === 'rd' || colId === 'wr'">
                <div class="cell-disp" :class="{ dual: r[colId + 'Cell'].pair }">
                  <div class="real" :title="r[colId + 'Cell'].realTip || null">{{ r[colId + 'Cell'].real }}</div>
                  <div v-if="r[colId + 'Cell'].pair" class="list" :title="r[colId + 'Cell'].listTip || null">{{ r[colId + 'Cell'].list }}</div>
                </div>
              </template>

              <template v-else-if="colId === 'ctx' || colId === 'lat' || colId === 'tps'">
                {{ r[NUM_DISP[colId]] }}
              </template>

              <template v-else-if="colId === 'logs' || colId === 'trains'">
                {{ r[colId] }}
              </template>

              <template v-else-if="colId === 'peak'">
                {{ r.peak || '—' }}
              </template>

              <span v-else-if="colId === 'allowance'" v-html="r.allowance"></span>

              <template v-else>
                {{ r.notes }}
              </template>
            </td>
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
.reset-btn.copied { border-color: var(--ok); color: var(--ok); }
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
  touch-action: none;
}
thead tr.cols th.active { color: var(--accent-strong); }
thead tr.cols th:hover { color: var(--accent); }
thead tr.cols th.dragging { opacity: 0.45; }
thead tr.cols th.drop-left { box-shadow: inset 2px 0 0 var(--accent); }
thead tr.cols th.drop-right { box-shadow: inset -2px 0 0 var(--accent); }
thead tr.filters th { cursor: default; padding: 4px 6px; overflow: visible; }
.th-inner { pointer-events: none; }
.arrow { font-size: 0.5rem; pointer-events: none; margin-left: 1px; }

.num, th.num { text-align: right; }
td.num { font-weight: 600; }
.cell-disp .real { font-weight: 600; }
.cell-disp .list { color: var(--muted); font-size: 0.74rem; font-weight: 400; margin-top: 1px; }
.free { color: var(--ok); font-weight: 700; }

td.model { font-weight: 600; overflow-wrap: anywhere; }

.cell-model { display: flex; flex-direction: column; gap: 2px; }
.model-name { overflow-wrap: anywhere; }
.model-links { display: flex; flex-wrap: wrap; gap: 4px; font-weight: 400; }
a.mlink {
  color: var(--muted); font-size: 0.7rem; text-decoration: none;
  border: 1px solid var(--border); border-radius: 5px; padding: 0 5px;
  line-height: 1.5;
}
a.mlink:hover { color: var(--accent); border-color: var(--accent); }

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