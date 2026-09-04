const OPENROUTER_SERVICE_FEE = 0.055

export function fmtMoney(v) {
  if (v === null || v === undefined) return '—'
  return '$' + Number(v).toFixed(2)
}

export function fmtAllow(v) {
  const w = v * 0.5
  const f = v * 0.2
  const money = (x) => Number(x).toFixed(2)
  return `$${money(v)} monthly<br>$${money(w)} weekly<br>$${money(f)} /5h`
}

export function fmtCtx(v) {
  if (!v) return '—'
  if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 1 : 2).replace(/\.?0+$/, '') + 'M'
  if (v >= 1e3) return String(Math.round(v / 1e3)) + 'K'
  return String(v)
}

export function fmtWhole(v, suffix) {
  if (v === null || v === undefined) return '—'
  return Math.round(v).toLocaleString('en-US') + suffix
}

export function fmtBool(v) {
  if (v === null || v === undefined) return '—'
  return v ? 'Yes' : 'No'
}

export function computeReal(value, listed, tax) {
  if (value === null || value === undefined) return null
  return value * (1 + OPENROUTER_SERVICE_FEE) * (1 + tax)
}

export function buildRow(row, meta, tax) {
  const m = row.market
  const free = m === 'zen' && row.input === 0

  const val = (v) => {
    if (v === null || v === undefined) return null
    let r
    if (m === 'go') r = v  // already effective per-1M
    else if (m === 'or') r = computeReal(v, v, tax)
    else r = v
    return Math.round(r * 100) / 100
  }

  const mkCell = (eff, list) => {
    if (free) return { free: true, real: 'Free', list: null, pair: false, tip: 'Free model' }
    const rawReal = val(eff ?? list)
    const rawList = list === null || list === undefined ? null : list
    const pair = rawReal !== null && rawList !== null && Math.abs(rawReal - rawList) > 1e-6
    const disp = rawReal !== null ? fmtMoney(rawReal) : (rawList !== null ? fmtMoney(rawList) : '—')
    const money = (x) => '$' + Number(x).toFixed(2)
    let tip = ''
    if (rawList !== null && rawReal !== null) {
      if (m === 'or') {
        tip = `Real = listed ${money(rawList)} × (1 + ${(OPENROUTER_SERVICE_FEE * 100).toFixed(1)}% fee) × (1 + ${(tax * 100).toFixed(2)}% tax) = ${money(rawReal)}`
      } else if (m === 'go' && eff != null && row.effAll > 0) {
        tip = `Effective = listed ${money(rawList)} × (10 ÷ $${Number(row.effAll).toFixed(2)} monthly allowance) = ${money(rawReal)}`
      } else {
        tip = `Real = listed ${money(rawList)}`
      }
    }
    return {
      free: false,
      real: disp,
      list: rawList === null ? null : fmtMoney(rawList),
      pair,
      tip: tip || null,
    }
  }

  const offpeak = /\(off-peak\)/i.test(row.model || '')
  const peak = row.peakHours ? `${offpeak ? 'Off-Peak' : 'Peak'}: ${row.peakHours}` : null

  const PLAN = {
    go: { label: 'OpenCode Go', link: meta.links?.go },
    zen: { label: 'OpenCode Zen', link: meta.links?.zen },
    or: { label: 'OpenRouter', link: meta.links?.or },
  }

  return {
    market: m,
    model: row.model,
    base: row.base || row.model,
    plan: PLAN[m]?.label || m,
    planLink: PLAN[m]?.link || null,
    provider: m === 'or' ? row.provider : '',
    providerLink: m === 'or' ? row.providerLink : '',
    notes: row.notes || '',
    allowance: free ? '' : (m === 'go' ? fmtAllow(row.effAll) : 'Pay per usage'),
    logs: fmtBool(row.logsPrompts),
    trains: fmtBool(row.trainsOnData),
    peak,
    inCell: mkCell(row.effIn, row.input),
    outCell: mkCell(row.effOut, row.output),
    rdCell: mkCell(row.effRead, row.read),
    wrCell: mkCell(row.effWrite, row.write),
    valIn: val(row.effIn ?? row.input),
    valOut: val(row.effOut ?? row.output),
    valRd: val(row.effRead ?? row.read),
    valWr: val(row.effWrite ?? row.write),
    pxCost: (val(row.effIn ?? row.input) ?? 1e18) + (val(row.effOut ?? row.output) ?? 1e18),
    ctxDisp: fmtCtx(row.context),
    ctxVal: row.context || null,
    latDisp: fmtWhole(row.latency, ' ms'),
    latVal: row.latency ?? null,
    tpsDisp: fmtWhole(row.tps, ' tps'),
    tpsVal: row.tps ?? null,
    textM: row.model,
    textP: m === 'or' ? row.provider : '',
    textPlan: PLAN[m]?.label || m,
    textA: free ? '' : (m === 'go' ? fmtAllow(row.effAll).replace(/<br>/g, ' ') : 'Pay per usage'),
    textN: row.notes || '',
  }
}
