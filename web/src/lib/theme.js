import { ref } from 'vue'

function systemDark() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)')?.matches
}

function domDark() {
  if (typeof document === 'undefined') return false
  const el = document.documentElement
  return el.classList.contains('dark') || el.getAttribute('data-theme') === 'dark'
}

const dark = ref(systemDark() || domDark())

if (typeof window !== 'undefined') {
  const update = () => { dark.value = systemDark() || domDark() }
  window.matchMedia?.('(prefers-color-scheme: dark)')?.addEventListener('change', update)
  new MutationObserver(update).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class', 'data-theme'],
  })
}

export function useDark() {
  return dark
}

export function planColor(plan, darkMode) {
  if (!plan) return '#2b6cb0'
  return darkMode ? (plan.colorDark || plan.color) : plan.color
}

export function planBg(color) {
  const c = color.replace('#', '')
  if (c.length !== 6) return 'transparent'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, 0.14)`
}