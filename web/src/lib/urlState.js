export function readParams() {
  const sp = new URLSearchParams(location.search)
  const out = {}
  for (const [k, v] of sp) out[k] = v
  return out
}

export function writeParams(patch) {
  const sp = new URLSearchParams(location.search)
  for (const [k, v] of Object.entries(patch)) {
    if (v === undefined || v === null || v === '') sp.delete(k)
    else sp.set(k, v)
  }
  const qs = sp.toString()
  history.replaceState(null, '', qs ? '?' + qs : location.pathname)
}

export function paramStr(params, key, dflt) {
  const v = params[key]
  if (v === undefined || v === '') return dflt
  return v
}

export function paramNum(params, key, dflt) {
  const v = params[key]
  if (v === undefined || v === '') return dflt
  const n = Number(v)
  return Number.isFinite(n) ? n : dflt
}

export function paramList(params, key) {
  const v = params[key]
  if (v === undefined || v === '') return []
  return v.split(',').filter(Boolean).map(decodeURIComponent)
}