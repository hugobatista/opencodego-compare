const OPENROUTER_SERVICE_FEE = 0.055

export function fmtMoney(v) {
  if (v === null || v === undefined) return '—'
  return '$' + Number(v).toFixed(3)
}

const usd = (x) => {
  const s = Number(x).toFixed(2)
  return '$' + s.replace(/\.?0+$/, '')
}

export function fmtAllow(v) {
  const w = v * 0.5
  const f = v * 0.2
  return `${usd(v)} monthly<br>${usd(w)} weekly<br>${usd(f)} /5h`
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
  if (v === null || v === undefined) return '?'
  return v ? 'Yes' : 'No'
}

export function computeReal(value, tax) {
  if (value === null || value === undefined) return null
  return value * (1 + OPENROUTER_SERVICE_FEE) * (1 + tax)
}

export function buildRow(row, meta, tax) {
  const m = row.market
  const plan = meta.plans?.[m] || {}
  const subPrice = plan.subPrice
  const feeTax = !!plan.feeTax
  const free = row.input === 0 && row.output === 0

  const val = (v) => {
    if (v === null || v === undefined) return null
    let r = feeTax ? computeReal(v, tax) : v
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
      if (feeTax) {
        realTip = `Real = listed ${money(rawList)} × (1 + ${(OPENROUTER_SERVICE_FEE * 100).toFixed(1)}% fee) × (1 + ${(tax * 100).toFixed(2)}% tax) = ${money(rawReal)}`
      } else if (subPrice && eff != null && row.effAll > 0) {
        realTip = `Effective = listed ${money(rawList)} × (${subPrice} ÷ ${usd(row.effAll)} monthly allowance) = ${money(rawReal)} — only if the full monthly allowance is used`
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

  const commitment = subPrice || 0
  const textCommitment = commitment > 0 ? '$' + commitment + '/mo' : '$0'

  const gatewayId = row.gateway || plan.gateway
  const gw = gatewayId ? meta.gateways?.[gatewayId] : null
  const gateway = gw?.name || ''
  const gatewayLink = gw?.url || null
  const provider = row.provider || ''
  const providerLink = row.providerLink || null

  const allowance = (forText) => {
    const br = forText ? ' ' : '<br>'
    if (free) return ''
    if (subPrice) return fmtAllow(row.effAll).replace(/<br>/g, br)
    return 'Pay per usage'
  }

  return {
    market: m,
    planMeta: plan,
    gatewayMeta: gw,
    model: row.model || row.variant,
    variant: row.variant || row.model,
    maker: row.maker || '',
    makerLink: row.makerLink || null,
    developerId: row.developerId || '',
    plan: row.plan || plan.name || m,
    planLink: plan.url || null,
    gateway,
    gatewayLink,
    provider,
    providerLink,
    variantLink: row.variantLink || null,
    modelMarketsLink: row.modelMarketsLink || null,
    hfLink: row.hfLink || null,
    notes: row.notes || '',
    privacyNote: row.privacyNote || '',
    allowance: allowance(false),
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
    textP: provider,
    textG: gateway,
    textPlan: row.plan || plan.name || m,
    textA: allowance(true),
    textN: row.notes || '',
    valCommit: commitment,
    textCommitment,
  }
}