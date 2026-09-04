<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  options: { type: Array, required: true },
  selected: { type: Array, required: true },
  label: { type: String, default: '' },
})

const emit = defineEmits(['update:selected'])

const open = ref(false)
const query = ref('')
const btnEl = ref(null)
const popEl = ref(null)
const pos = ref({ top: 0, left: 0, width: 0 })

const filteredOptions = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.options
  return props.options.filter((o) => o.toLowerCase().includes(q))
})

const allSelected = computed(() => {
  const fo = filteredOptions.value
  return fo.length > 0 && fo.every((o) => props.selected.includes(o))
})

const displayLabel = () => {
  if (props.selected.length === 0 || props.selected.length === props.options.length) return 'All'
  if (props.selected.length <= 2) return props.selected.join(', ')
  return `${props.selected.length} selected`
}

function toggle(val) {
  const s = [...props.selected]
  const i = s.indexOf(val)
  if (i >= 0) s.splice(i, 1)
  else s.push(val)
  emit('update:selected', s)
}

function toggleAll() {
  const fo = filteredOptions.value
  const s = [...props.selected]
  if (allSelected.value) {
    emit('update:selected', s.filter((o) => !fo.includes(o)))
  } else {
    emit('update:selected', [...new Set([...s, ...fo])])
  }
}

function updatePos() {
  const r = btnEl.value.getBoundingClientRect()
  pos.value = { top: r.bottom + 4, left: r.left, width: Math.max(r.width, 200) }
}

function close() {
  open.value = false
  window.removeEventListener('scroll', onScroll, true)
  window.removeEventListener('resize', updatePos)
  document.removeEventListener('keydown', onKey)
}

function onScroll() {
  if (open.value) updatePos()
}

function onKey(e) {
  if (e.key === 'Escape') close()
}

function onClick() {
  if (!open.value) {
    open.value = true
    query.value = ''
    updatePos()
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', updatePos)
    document.addEventListener('keydown', onKey)
  } else {
    close()
  }
}

function onOutside(e) {
  if (!open.value) return
  if (btnEl.value && btnEl.value.contains(e.target)) return
  if (popEl.value && popEl.value.contains(e.target)) return
  close()
}

onMounted(() => document.addEventListener('mousedown', onOutside))
onUnmounted(close)
</script>

<template>
  <div class="ms-wrap">
    <button ref="btnEl" type="button" class="ms-btn" @click="onClick" :title="label">
      <span class="ms-val">{{ displayLabel() }}</span>
      <span class="ms-arrow">{{ open ? '▲' : '▼' }}</span>
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        ref="popEl"
        class="ms-drop"
        :style="{ top: pos.top + 'px', left: pos.left + 'px', minWidth: pos.width + 'px' }"
      >
        <input
          v-if="options.length > 8"
          ref="searchEl"
          v-model="query"
          class="ms-search"
          type="text"
          placeholder="Type to filter…"
          @click.stop
        >
        <div class="ms-actions">
          <label class="ms-item ms-all">
            <input
              type="checkbox"
              :checked="allSelected"
              @change="toggleAll"
            >
            <span>{{ filteredOptions.length && allSelected ? 'Clear' : 'Select all' }}</span>
          </label>
          <span v-if="selected.length" class="ms-count">{{ selected.length }} picked</span>
        </div>
        <div class="ms-list">
          <label
            v-for="opt in filteredOptions"
            :key="opt"
            class="ms-item"
            @click.stop
          >
            <input
              type="checkbox"
              :checked="selected.includes(opt)"
              @change="toggle(opt)"
            >
            <span class="ms-opt">{{ opt }}</span>
          </label>
          <div v-if="!filteredOptions.length" class="ms-empty">No matches</div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.ms-wrap { position: relative; display: inline-block; width: 100%; }
.ms-btn {
  width: 100%; box-sizing: border-box; font-size: 0.8rem;
  padding: 3px 6px; border: 1px solid var(--border); border-radius: 4px;
  background: var(--bg); color: var(--fg); cursor: pointer;
  display: flex; align-items: center; justify-content: space-between; gap: 4px;
  transition: border-color 0.12s ease;
}
.ms-btn:hover { border-color: var(--accent); }
.ms-val { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ms-arrow { font-size: 0.65rem; flex-shrink: 0; color: var(--muted); }

.ms-drop {
  position: fixed; z-index: 1000;
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0,0,0,0.22);
  padding: 6px; max-height: 340px; display: flex; flex-direction: column;
  width: max-content; max-width: min(380px, calc(100vw - 20px));
}
.ms-search {
  width: 100%; box-sizing: border-box; font-size: 0.85rem;
  padding: 5px 8px; margin-bottom: 5px;
  border: 1px solid var(--border); border-radius: 5px;
  background: var(--bg); color: var(--fg);
}
.ms-actions {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 2px 4px 4px; border-bottom: 1px solid var(--border); margin-bottom: 4px;
}
.ms-count { font-size: 0.7rem; color: var(--muted); white-space: nowrap; }
.ms-list { overflow-y: auto; flex: 1; min-height: 0; }
.ms-item {
  display: flex; align-items: center; gap: 6px;
  padding: 3px 6px; font-size: 0.82rem; cursor: pointer; border-radius: 4px;
  white-space: nowrap;
}
.ms-item:hover { background: var(--row-hover); }
.ms-item input { margin: 0; cursor: pointer; flex-shrink: 0; }
.ms-opt { overflow: hidden; text-overflow: ellipsis; }
.ms-all { font-weight: 600; }
.ms-empty { padding: 8px 6px; font-size: 0.8rem; color: var(--muted); text-align: center; }
</style>