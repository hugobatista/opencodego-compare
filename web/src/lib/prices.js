const OPENROUTER_SERVICE_FEE = 0.055

export function fmtMoney(v) {
  if (v === null || v === undefined) return '—'
  return '$' + Number(v).toFixed(3)
}

export function fmtAllow(v) {
  const w = v * 0.5
  const f = v * 0.2
  const money = (x) => Number(x).toFixed(3)
  return `$${money(v)} monthly<br>$${money(w)} weekly<br>$${money(f)} /5h`
}

export function fmtGoatAllow(v) {
  const money = (x) => Number(x).toFixed(3)
  return `$${money(v)} credits/mo<br>windows $35/wk<br>$14/5h`
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
  const free = (m === 'opencode-zen' || m === 'command-code-goat') && row.input === 0

  const val = (v) => {
    if (v === null || v === undefined) return null
    let r
    if (m === 'opencode-go' || m === 'command-code-goat') r = v  // already effective per-1M
    else if (m === 'openrouter') r = computeReal(v, v, tax)
    else r = v
    return Math.round(r * 1000) / 1000
  }

  const mkCell = (eff, list) => {
    if (free) return { free: true, real: 'Free', list: null, pair: false, realTip: 'Free model', listTip: null }
    const rawReal = val(eff ?? list)
    const rawList = list === null || list === undefined ? null : list
    const pair = rawReal !== null && rawList !== null && Math.abs(rawReal - rawList) > 1e-6
    const disp = rawReal !== null ? fmtMoney(rawReal) : (rawList !== null ? fmtMoney(rawList) : '—')
    const money = (x) => '$' + Number(x).toFixed(3)
    let realTip = ''
    if (rawList !== null && rawReal !== null) {
      if (m === 'openrouter') {
        realTip = `Real = listed ${money(rawList)} × (1 + ${(OPENROUTER_SERVICE_FEE * 100).toFixed(1)}% fee) × (1 + ${(tax * 100).toFixed(2)}% tax) = ${money(rawReal)}`
      } else if ((m === 'opencode-go' || m === 'command-code-goat') && eff != null && row.effAll > 0) {
        realTip = `Effective = listed ${money(rawList)} × (10 ÷ $${Number(row.effAll).toFixed(3)} monthly allowance) = ${money(rawReal)} — only if the full monthly allowance is used`
      } else {
        realTip = `Real = listed ${money(rawList)}`
      }
    }
    return {
      free: false,
      real: disp,
      list: rawList === null ? null : fmtMoney(rawList),
      pair,
      realTip: realTip || null,
      listTip: rawList !== null ? `Listed price ${money(rawList)}` : null,
    }
  }

  const peak = row.peakHours || null

  const PLAN = {
    'opencode-go': { label: 'OpenCode Go', link: meta.links?.['opencode-go'] },
    'command-code-goat': { label: 'Command Code GOAT', link: meta.links?.['command-code-goat'] },
    'opencode-zen': { label: 'OpenCode Zen', link: meta.links?.['opencode-zen'] },
    openrouter: { label: 'OpenRouter', link: meta.links?.openrouter },
    deepinfra: { label: 'DeepInfra', link: meta.links?.deepinfra },
  }

  return {
    market: m,
    model: row.model || row.variant,
    variant: row.variant || row.model,
    maker: row.maker || '',
    makerLink: row.makerLink || null,
    developerId: row.developerId || '',
    plan: row.plan || PLAN[m]?.label || m,
    planLink: PLAN[m]?.link || null,
    provider: m === 'openrouter' ? row.provider : '',
    providerLink: m === 'openrouter' ? row.providerLink : '',
    variantLink: (m === 'openrouter' || m === 'deepinfra') ? row.variantLink : null,
    modelLink: row.modelLink || null,
    hfLink: row.hfLink || null,
    notes: row.notes || '',
    allowance: free ? '' : (m === 'opencode-go' ? fmtAllow(row.effAll) : (m === 'command-code-goat' && row.effAll > 0 ? fmtGoatAllow(row.effAll) : 'Pay per usage')),
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
    textM: row.model || row.variant,
    textV: row.variant || row.model,
    textK: row.maker || '',
    textP: m === 'openrouter' ? row.provider : '',
    textPlan: PLAN[m]?.label || m,
    textA: free ? '' : (m === 'opencode-go' ? fmtAllow(row.effAll).replace(/<br>/g, ' ') : (m === 'command-code-goat' && row.effAll > 0 ? fmtGoatAllow(row.effAll).replace(/<br>/g, ' ') : 'Pay per usage')),
    textN: row.notes || '',
  }
}
