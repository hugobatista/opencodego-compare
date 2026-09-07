<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { buildRow } from '../lib/prices.js'
import { useDark, planColor } from '../lib/theme.js'
import { readParams, writeParams, paramStr, paramList } from '../lib/urlState.js'
import MultiSelect from './MultiSelect.vue'

const props = defineProps({
  rows: { type: Array, required: true },
  meta: { type: Object, required: true },
  tax: { type: Number, default: 0.2425 },
})

const isDark = useDark()

const COLS = [
  { id: 'maker',    label: 'Model Maker',      kind: 'text',   key: 'textK' },
  { id: 'model',    label: 'Model',           kind: 'text',   key: 'textM' },
  { id: 'variant',  label: 'Model Variant',   kind: 'text',   key: 'textV' },
  { id: 'gateway',  label: 'Gateway Provider', kind: 'text',  key: 'textG' },
  { id: 'plan',     label: 'Plan',            kind: 'text',   key: 'textPlan' },
  { id: 'provider', label: 'Inference Provider', kind: 'text', key: 'textP' },
  { id: 'in',       label: 'Input',           kind: 'numeric', key: 'valIn' },
  { id: 'out',      label: 'Output',          kind: 'numeric', key: 'valOut' },
  { id: 'rd',       label: 'Cached Read',     kind: 'numeric', key: 'valRd' },
  { id: 'wr',       label: 'Cached Write',    kind: 'numeric', key: 'valWr' },
  { id: 'ctx',      label: 'Context',         kind: 'numeric', key: 'ctxVal' },
  { id: 'lat',      label: 'Latency (p50)',   kind: 'numeric', key: 'latVal' },
  { id: 'tps',      label: 'TPS (p50)',       kind: 'numeric', key: 'tpsVal' },
  { id: 'logs',     label: 'Log prompts',     kind: 'choice',  key: 'logs' },
  { id: 'trains',   label: 'Training',        kind: 'choice',  key: 'trains' },
  { id: 'peak',     label: 'Peak slots',      kind: 'choice',  key: 'peak' },
  { id: 'allowance', label: 'Allowance',      kind: 'text',    key: 'textA' },
  { id: 'commitment', label: 'Commitment',    kind: 'numeric', key: 'valCommit' },
  { id: 'intelligence', label: 'Intelligence', kind: 'numeric', key: 'intelligenceVal' },
  { id: 'coding',   label: 'Coding',     kind: 'numeric', key: 'codingVal' },
  { id: 'agentic',  label: 'Agentic',    kind: 'numeric', key: 'agenticVal' },
  { id: 'notes',    label: 'Notes',           kind: 'text',    key: 'textN' },
]

const GROUPS = [
  { label: 'Model',        cols: ['maker', 'model', 'variant'] },
  { label: 'Provider',     cols: ['gateway', 'plan', 'provider'] },
  { label: 'Pricing/1M',   cols: ['in', 'out', 'rd', 'wr'] },
  { label: 'Performance',  cols: ['ctx', 'lat', 'tps'] },
  { label: 'Privacy',      cols: ['logs', 'trains'] },
  { label: 'Plan Details', cols: ['peak', 'allowance', 'commitment'] },
  { label: 'Benchmark Index', cols: ['intelligence', 'coding', 'agentic'] },
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

const onlyCommonModels = ref(true)
const showBatch = ref(false)
const norm = (s) => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '')
const commonFamilies = computed(() => {
  const set = new Set()
  for (const r of props.rows) {
    if (r.market === 'openrouter') continue
    if (r.model) set.add(norm(r.model))
  }
  return [...set].sort((a, b) => b.length - a.length)
})
const openrouterMatches = (r) => {
  if (r.market !== 'openrouter' || !onlyCommonModels.value) return true
  const fam = norm(r.model)
  if (commonFamilies.value.includes(fam)) return true
  return commonFamilies.value.some((b) => b.length >= 8 && fam.startsWith(b))
}

const pool = computed(() => display.value.filter(openrouterMatches))
const isNotBatch = (r) => showBatch.value || !(r.developerId || '').endsWith(':batch')
const filteredPool = computed(() => pool.value.filter(isNotBatch))

const openrouterShow = ref(3)
const limited = computed(() => {
  const N = openrouterShow.value
  if (N === 'all') return filteredPool.value
  const byKey = new Map()
  const out = []
  for (const r of filteredPool.value) {
    if (r.market !== 'openrouter') { out.push(r); continue }
    const key = r.developerId || r.model
    const arr = byKey.get(key) || []
    arr.push(r)
    byKey.set(key, arr)
  }
  for (const arr of byKey.values()) {
    if (arr.length <= N) { out.push(...arr); continue }
    const sorted = [...arr].sort((a, b) => (a.pxCost ?? 1e18) - (b.pxCost ?? 1e18))
    out.push(...sorted.slice(0, N))
  }
  return out
})
const hiddenCount = computed(() => Math.max(0, filteredPool.value.length - limited.value.length))

function passesOthers(row, exceptId) {
  for (const c of COLS) {
    if (c.id === exceptId) continue
    if (c.kind === 'numeric') {
      const nf = numFilters[c.id]
      const v = row[c.key]
      if (nf.min !== '' || nf.max !== '') {
        if (v === null || v === undefined || Number.isNaN(Number(v))) return false
        if (nf.min !== '' && Number(v) < parseFloat(nf.min)) return false
        if (nf.max !== '' && Number(v) > parseFloat(nf.max)) return false
      }
    } else {
      const sel = multiFilters[c.id] || []
      if (sel.length === 0) continue
      const v = row[c.key]
      const isEmpty = v === null || v === undefined || v === ''
      if (isEmpty) {
        if (!sel.includes('(empty)')) return false
      } else if (!sel.includes(String(v))) {
        return false
      }
    }
  }
  return true
}

const distinctOptions = computed(() => {
  const map = {}
  for (const c of COLS) {
    if (c.kind === 'numeric') continue
    const set = new Set()
    let hasEmpty = false
    for (const r of limited.value) {
      if (!passesOthers(r, c.id)) continue
      const v = r[c.key]
      if (v === null || v === undefined || v === '') { hasEmpty = true; continue }
      set.add(String(v))
    }
    const sorted = [...set].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
    if (hasEmpty) sorted.unshift('(empty)')
    map[c.id] = sorted
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
if (paramStr(urlParams, 'common', '1') === '0') onlyCommonModels.value = false
if (paramStr(urlParams, 'batch', '') === '1') showBatch.value = true
const orRaw = paramStr(urlParams, 'openroutershow', '3')
if (orRaw === 'all') openrouterShow.value = 'all'
else if (Number.isInteger(Number(orRaw)) && Number(orRaw) >= 1 && Number(orRaw) <= 5) openrouterShow.value = Number(orRaw)

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
  return limited.value.filter(passesOthers)
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
  onlyCommonModels.value = true
  showBatch.value = false
  openrouterShow.value = 3
  writeParams(toParams())
}

const columnsOpen = ref(false)
const colMenu = ref(null)
function onColMenuClick(e) {
  if (colMenu.value && !colMenu.value.contains(e.target)) columnsOpen.value = false
}
function setupColMenuWatcher() {
  if (columnsOpen.value) document.addEventListener('pointerdown', onColMenuClick)
  else document.removeEventListener('pointerdown', onColMenuClick)
}
watch(columnsOpen, setupColMenuWatcher)

function toParams() {
  const out = {}
  out.sort = sortKey.value === 'in' && sortDir.value === 1 ? '' : sortKey.value + ':' + sortDir.value
  out.common = onlyCommonModels.value ? '' : '0'
  out.batch = showBatch.value ? '1' : ''
  out.openroutershow = openrouterShow.value === 3 ? '' : String(openrouterShow.value)
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
  maker: 9, model: 14, variant: 13, gateway: 9, plan: 10, provider: 9, 'in': 7, out: 7, rd: 6, wr: 6,
  ctx: 6, lat: 6, tps: 5, intelligence: 6, coding: 5, agentic: 5, logs: 4, trains: 4, peak: 6, allowance: 7, commitment: 7, notes: 12,
}
const colWidths = reactive({ ...DEFAULT_WIDTHS })
const colOrder = ref(COLS.map((c) => c.id))
const hiddenCols = ref(new Set(['notes']))
const renderCols = computed(() => {
  const vis = colOrder.value.filter((id) => !hiddenCols.value.has(id))
  const grouped = vis.filter((id) => groupedColIds.has(id))
  const ungrouped = vis.filter((id) => !groupedColIds.has(id))
  return [...grouped, ...ungrouped]
})
const groupedColIds = new Set(GROUPS.flatMap((g) => g.cols))
const visibleGroups = computed(() => {
  const vis = new Set(renderCols.value)
  return GROUPS.filter((g) => g.cols.some((c) => vis.has(c)))
})
const ungroupedVisible = computed(() => renderCols.value.filter((id) => !groupedColIds.has(id)))
const groupsContiguous = computed(() => {
  const pos = new Map(renderCols.value.map((id, i) => [id, i]))
  for (const g of GROUPS) {
    const ps = g.cols.filter((c) => pos.has(c)).map((c) => pos.get(c)).sort((a, b) => a - b)
    for (let i = 1; i < ps.length; i++) {
      if (ps[i] !== ps[i - 1] + 1) return false
    }
  }
  return true
})
const groupFirstCol = computed(() => {
  if (!groupsContiguous.value) return new Set()
  const s = new Set()
  const vis = new Set(renderCols.value)
  for (const g of GROUPS) {
    for (const c of g.cols) {
      if (vis.has(c)) { s.add(c); break }
    }
  }
  return s
})
const firstUngroupedCol = computed(() => ungroupedVisible.value[0] || null)
function isGroupAllVisible(g) {
  const vis = new Set(renderCols.value)
  return g.cols.every((c) => vis.has(c))
}
function toggleGroupCols(g, show) {
  for (const c of g.cols) toggleCol(c, show)
}
function selectAllCols() {
  hiddenCols.value = new Set()
  saveLayout()
}
function resetCols() {
  hiddenCols.value = new Set(['notes'])
  saveLayout()
}
const collapsedMenuGroups = ref(new Set(GROUPS.map((g) => g.label)))
function toggleMenuGroup(label) {
  const s = new Set(collapsedMenuGroups.value)
  if (s.has(label)) s.delete(label)
  else s.add(label)
  collapsedMenuGroups.value = s
}
const colSearch = ref('')
const colSearchNorm = computed(() => norm(colSearch.value))
watch(colSearch, (q) => {
  if (!norm(q)) return
  const s = new Set(collapsedMenuGroups.value)
  for (const g of GROUPS) {
    if (g.cols.some((c) => colMatchesSearch(colById(c)))) s.delete(g.label)
  }
  collapsedMenuGroups.value = s
})
function colMatchesSearch(c) {
  return !colSearchNorm.value || norm(c.label).includes(colSearchNorm.value) || norm(c.id).includes(colSearchNorm.value)
}
function groupHasMatch(g) {
  return !colSearchNorm.value || g.cols.some((c) => colMatchesSearch(colById(c)))
}
function toggleCol(id, show) {
  const h = new Set(hiddenCols.value)
  if (show) h.delete(id)
  else {
    if (h.size + 1 >= COLS.length) return
    h.add(id)
  }
  hiddenCols.value = h
  saveLayout()
}

const CELL_TITLES = {
  model: 'Model family — groups all variants',
  variant: 'Specific model variant',
  maker: 'Model manufacturer/creator',
  gateway: 'Reseller/gateway that serves the model; a plan belongs to it',
  plan: 'Subscription/pricing plan offered by the gateway',
  ctx: 'Context length',
  lat: '50th percentile latency',
  tps: '50th percentile tokens per second',
  intelligence: 'Artificial Analysis intelligence index (reasoning, knowledge, instruction following)',
  coding: 'Artificial Analysis coding index (code generation, debugging, refactoring)',
  agentic: 'Artificial Analysis agentic index (tool use, multi-step planning, autonomous tasks)',
  logs: 'Provider logs your prompts',
  trains: 'Provider trains on your data',
  peak: 'Peak and off-peak hours',
  commitment: 'Minimum monthly subscription commitment in USD',
  allowance: 'Monthly allowance = usage included per month at full price; weekly = 50%; 5h = 20%. Subscription effective prices apply only if you use the full monthly allowance',
}
const NUM_DISP = { ctx: 'ctxDisp', lat: 'latDisp', tps: 'tpsDisp', commitment: 'textCommitment', intelligence: 'intelligenceDisp', coding: 'codingDisp', agentic: 'agenticDisp' }

function colById(id) { return COLS.find((c) => c.id === id) }
function tdTitle(colId, r) {
  if (colId === 'logs' || colId === 'trains') {
    const note = r.privacyNote ? ' — ' + r.privacyNote : ''
    if (r[colId] === '?') return 'Not disclosed / unconfirmed by provider' + note
    return CELL_TITLES[colId] + ' — ' + r[colId] + note
  }
  return CELL_TITLES[colId] || undefined
}
function cellClass(colId, r) {
  let cls = ''
  if (groupFirstCol.value.has(colId)) cls += 'group-start '
  if (colId === firstUngroupedCol.value) cls += 'separator '
  if (colId === 'model') return cls + 'model'
  if (colId === 'logs' || colId === 'trains') return cls + 'yesno ' + r[colId]
  if (colId === 'allowance') return cls + 'allow'
  if (colId === 'notes') return cls + 'notes'
  if (colById(colId).kind === 'numeric') return cls + 'num'
  return cls.trim()
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
    if (s && Array.isArray(s.hidden)) {
      const valid = s.hidden.filter((id) => colById(id))
      if (valid.length < COLS.length) hiddenCols.value = new Set(valid)
    }
  } catch (e) { /* ignore corrupted layout */ }
}
function saveLayout() {
  try {
    localStorage.setItem('oc_layout', JSON.stringify({ order: colOrder.value, widths: colWidths, hidden: [...hiddenCols.value] }))
  } catch (e) { /* ignore */ }
}
function resetLayout() {
  colOrder.value = COLS.map((c) => c.id)
  hiddenCols.value = new Set(['notes'])
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
        <input type="checkbox" v-model="onlyCommonModels">
        <span>Only common models</span>
      </label>
      <label class="toggle">
        <input type="checkbox" v-model="showBatch">
        <span>Show batch models</span>
      </label>
      <label class="plimit">
        <span>Cheapest OR providers/model:</span>
        <select v-model="openrouterShow">
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
      <div ref="colMenu" class="colmenu">
        <button type="button" class="reset-btn" :class="{ active: columnsOpen }" @click="columnsOpen = !columnsOpen">
          Columns <span class="colcount">{{ renderCols.length }}/{{ COLS.length }}</span>
        </button>
        <div v-if="columnsOpen" class="colmenu-panel">
          <div class="colmenu-actions">
            <label class="colmenu-action-item">
              <input type="checkbox" :checked="renderCols.length === COLS.length" @change="renderCols.length === COLS.length ? resetCols() : selectAllCols()">
              <span>{{ renderCols.length === COLS.length ? 'Clear' : 'Select all' }}</span>
            </label>
            <button type="button" class="colmenu-reset" @click="resetCols">Reset</button>
          </div>
          <input
            v-model="colSearch"
            type="text"
            class="colmenu-search"
            placeholder="Search columns…"
            @input.stop
          >
          <template v-for="g in GROUPS.filter(groupHasMatch)" :key="g.label">
            <div class="colmenu-item colmenu-group" @click="toggleMenuGroup(g.label)">
              <input
                type="checkbox"
                :checked="isGroupAllVisible(g)"
                @change.stop="toggleGroupCols(g, $event.target.checked)"
                @click.stop
              >
              <span class="colmenu-chevron" :class="{ open: !collapsedMenuGroups.has(g.label) }">▸</span>
              <span class="colmenu-group-label">{{ g.label }}</span>
            </div>
            <template v-if="!collapsedMenuGroups.has(g.label)">
              <label v-for="c in g.cols.filter(c => colMatchesSearch(colById(c)))" :key="c.id" class="colmenu-item colmenu-col">
                <input
                  type="checkbox"
                  :checked="renderCols.includes(c)"
                  @change="toggleCol(c, $event.target.checked)"
                >
                <span>{{ colById(c).label }}</span>
              </label>
            </template>
          </template>
          <template v-for="c in COLS.filter(c => !groupedColIds.has(c.id) && colMatchesSearch(c))" :key="c.id">
            <label class="colmenu-item colmenu-group">
              <input
                type="checkbox"
                :checked="renderCols.includes(c.id)"
                @change="toggleCol(c.id, $event.target.checked)"
              >
              <span class="colmenu-group-label">{{ c.label }}</span>
            </label>
          </template>
        </div>
      </div>
    </div>

    <div class="tablewrap">
      <table :style="tableStyle()">
        <colgroup>
          <col v-for="colId in renderCols" :key="colId" :style="{ width: colWidths[colId] + '%' }">
        </colgroup>
        <thead>
          <tr class="groups" v-if="groupsContiguous && (visibleGroups.length || ungroupedVisible.length)">
            <th
              v-for="g in visibleGroups"
              :key="g.label"
              :colspan="g.cols.filter(c => !hiddenCols.has(c)).length"
            >{{ g.label }}</th>
            <th
              v-if="ungroupedVisible.length"
              :colspan="ungroupedVisible.length"
            > </th>
          </tr>
          <tr class="cols">
            <th
              v-for="colId in renderCols"
              :key="colId"
              :class="[
                colById(colId).kind === 'numeric' ? 'num' : '',
                sortKey === colId ? 'active' : '',
                groupFirstCol.has(colId) ? 'group-start' : '',
                colId === firstUngroupedCol ? 'separator' : '',
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
            <th v-for="colId in renderCols" :key="colId" :data-col="colId" :class="[colById(colId).kind === 'numeric' ? 'num' : '', groupFirstCol.has(colId) ? 'group-start' : '', colId === firstUngroupedCol ? 'separator' : '']">
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
              v-for="colId in renderCols"
              :key="colId"
              :class="cellClass(colId, r)"
              :title="tdTitle(colId, r)"
            >
              <template v-if="colId === 'model'">
                <div class="cell-model">
                  <span class="model-name">{{ r.model }}</span>
                  <span class="model-links">
                    <a v-if="r.modelMarketsLink" :href="r.modelMarketsLink" target="_blank" rel="noopener" class="mlink">ModelMarkets</a>
                    <a v-if="r.hfLink" :href="r.hfLink" target="_blank" rel="noopener" class="mlink">HuggingFace</a>
                  </span>
                </div>
              </template>

              <template v-else-if="colId === 'gateway'">
                <a
                  v-if="r.gateway && r.gatewayLink"
                  :href="r.gatewayLink"
                  target="_blank"
                  rel="noopener"
                  class="prov"
                  :style="{ color: planColor(r.gatewayMeta, isDark.value) }"
                >{{ r.gateway }}</a>
                <span v-else-if="r.gateway" class="prov" :style="{ color: planColor(r.gatewayMeta, isDark.value) }">{{ r.gateway }}</span>
                <span v-else class="dash">—</span>
              </template>

              <template v-else-if="colId === 'plan'">
                <a
                  v-if="r.planLink"
                  :href="r.planLink"
                  target="_blank"
                  rel="noopener"
                  class="plan"
                >{{ r.plan }}</a>
                <span v-else class="plan">{{ r.plan }}</span>
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

              <template v-else-if="colId === 'ctx' || colId === 'lat' || colId === 'tps' || colId === 'commitment' || colId === 'intelligence' || colId === 'coding' || colId === 'agentic'">
                {{ r[NUM_DISP[colId]] }}
              </template>

              <template v-else-if="colId === 'logs' || colId === 'trains'">
                {{ r[colId] }}
              </template>

              <template v-else-if="colId === 'peak'">
                {{ r.peak || '—' }}
              </template>

              <template v-else-if="colId === 'maker'">
                <a
                  v-if="r.makerLink"
                  :href="r.makerLink"
                  target="_blank"
                  rel="noopener"
                  class="maker"
                >{{ r.maker || '—' }}</a>
                <span v-else class="dash">{{ r.maker || '—' }}</span>
              </template>

              <template v-else-if="colId === 'variant'">
                <a
                  v-if="r.variantLink"
                  :href="r.variantLink"
                  target="_blank"
                  rel="noopener"
                  class="vlink"
                >{{ r.variant || '—' }}</a>
                <span v-else class="vname">{{ r.variant || '—' }}</span>
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
.reset-btn.active { border-color: var(--accent); color: var(--accent); }
.colcount { opacity: 0.65; font-size: 0.78rem; }
.colmenu { position: relative; }
.colmenu-panel {
  position: absolute; top: calc(100% + 6px); right: 0; z-index: 30;
  display: flex; flex-direction: column; gap: 2px; min-width: 210px;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px; box-shadow: 0 6px 18px rgba(0,0,0,0.18);
}
.colmenu-item {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
  font-size: 0.86rem; padding: 4px 8px; border-radius: 5px; user-select: none;
}
.colmenu-item:hover { background: var(--row-hover); }
.colmenu-item input { accent-color: var(--accent); cursor: pointer; flex-shrink: 0; }
.colmenu-group { font-weight: 700; font-size: 0.82rem; margin-top: 4px; }
.colmenu-group:first-child { margin-top: 0; }
.colmenu-group-label { text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.72rem; }
.colmenu-col { padding-left: 20px; }
.colmenu-chevron {
  display: inline-block; transition: transform 0.15s ease;
  font-size: 0.55rem; margin-right: 2px; flex-shrink: 0;
}
.colmenu-chevron.open { transform: rotate(90deg); }
.colmenu-actions {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 2px 4px 4px; border-bottom: 1px solid var(--border); margin-bottom: 4px;
}
.colmenu-action-item {
  display: flex; align-items: center; gap: 6px; cursor: pointer;
  font-size: 0.72rem; user-select: none;
}
.colmenu-action-item input { accent-color: var(--accent); cursor: pointer; }
.colmenu-reset {
  font-size: 0.72rem; padding: 2px 8px; cursor: pointer;
  border: 1px solid var(--border); border-radius: 4px;
  background: var(--bg); color: var(--fg);
}
.colmenu-reset:hover { border-color: var(--accent); color: var(--accent-strong); }
.colmenu-search {
  width: 100%; padding: 5px 8px; margin-bottom: 4px;
  border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg); color: var(--fg); font-size: 0.82rem;
  outline: none;
}
.colmenu-search:focus { border-color: var(--accent); }
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
  border-bottom: 1px solid color-mix(in srgb, var(--border) 40%, transparent); padding: 6px 8px;
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
thead tr.groups th {
  cursor: default;
  font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--fg); font-weight: 700; padding: 5px 8px 3px;
  text-align: center; border-bottom: 2px solid var(--border);
}
.group-start { border-left: 2px solid var(--border) !important; padding-left: 10px !important; }
.separator { border-left: 2px solid var(--border) !important; padding-left: 10px !important; }
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
a.maker { color: var(--accent-strong); text-decoration: none; font-weight: 600; }
a.maker:hover { text-decoration: underline; }
a.vlink { color: var(--text); text-decoration: none; }
a.vlink:hover { text-decoration: underline; color: var(--accent); }
.vname { overflow-wrap: anywhere; }
a.plan { color: var(--fg); text-decoration: none; }
a.plan:hover { text-decoration: underline; }
.plan { font-weight: 400; font-size: 0.8rem; white-space: normal; overflow-wrap: anywhere; }

.yesno { font-size: 0.76rem; }
.yesno.Yes { color: var(--bad); font-weight: 600; }
.yesno.No { color: var(--ok); }
.yesno.\? { color: var(--warn); font-weight: 600; }
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