/**
 * Brokerage slab domain logic (brokerage-flow) — parse, cluster, label,
 * format. Ported faithfully from the approved prototype
 * (docs/prototype/report-flow-prototype.html — parseRate / brokerageClusters
 * / clusterHead / fmtInr / fmtPct).
 *
 * The slab arrives as per-segment groups of { title, desc } lines
 * ("₹20.00 for trade value of 10 thousand"). Slabs are PER-CLIENT, so the
 * rate clusters are computed from the response at render time, never
 * hardcoded: lines with an identical (unit, amount) parsed from `desc`
 * collapse — across segments — into one statement row
 * ("All futures · Stock · Index · Commodity · Currency").
 *
 * Honesty valve: ANY unparseable desc, or a slab that would need more than
 * 6 clusters, makes `brokerageClusters` return null and the card falls back
 * to the plain per-segment list with upstream text verbatim — a wrong
 * "All futures" claim must never render.
 *
 * Deliberately dependency-free (type-only module surface) so the algorithm
 * is directly runnable outside the app for verification.
 */

/** 'per10k' = ₹amt per ₹10,000 traded; 'order' = flat ₹amt per order. */
export type RateUnit = 'per10k' | 'order'

export interface ParsedRate {
  /** Rupee amount, e.g. 0.1, 1, 20. */
  amt: number
  unit: RateUnit
}

/** One slab line as upstream sends it, e.g.
 *  { title: "Stock Future", desc: "₹20.00 for trade value of 10 thousand" }. */
export interface BrokerageItem {
  title: string
  desc: string
}

/** One segment group, e.g. { title: "Derivative", list: [ …items ] }. */
export interface BrokerageGroup {
  title: string
  list: BrokerageItem[]
}

/** The `ok` payload the Brokerage card renders. */
export interface BrokerageData {
  groups: BrokerageGroup[]
}

/** A slab line tagged with its segment and parsed rate, ready to cluster. */
export interface ClusteredItem {
  /** Segment title, e.g. "Equity". */
  seg: string
  /** Line title, e.g. "Stock Future". */
  title: string
  rate: ParsedRate
}

export interface ClusterLabel {
  /** Row headline, e.g. "Equity intraday" or "All futures". */
  main: string
  /** Coverage subline for multi-item clusters ("Stock · Index · …"), or null. */
  cov: string | null
}

/** More clusters than this and the summary stops being a summary → fallback. */
const MAX_CLUSTERS = 6

/**
 * Parse one upstream desc into a rate. Recognized shapes:
 *   "₹20.00 per order"                        → { amt: 20, unit: 'order' }
 *   "₹1.00 for trade value of 10 thousand"    → { amt: 1,  unit: 'per10k' }
 * Anything else → null (the caller falls back to verbatim rendering).
 */
export function parseRate(desc: string): ParsedRate | null {
  const m = /₹\s*([\d.]+)/.exec(desc)
  if (!m) return null
  const amt = parseFloat(m[1])
  if (!Number.isFinite(amt)) return null
  if (/per order/i.test(desc)) return { amt, unit: 'order' }
  if (/10 thousand|trade value/i.test(desc)) return { amt, unit: 'per10k' }
  return null
}

/** "₹20", "₹0.10" — whole rupees carry no trailing ".00" noise. */
export function formatRateInr(amt: number): string {
  return `₹${Number.isInteger(amt) ? amt : amt.toFixed(2)}`
}

/** ₹-per-₹10,000 → the advertised percentage: ₹1 → "0.01%"; trailing zeros
 *  trimmed (₹20 → "0.2%", never "0.2000%"). */
export function formatRatePct(amt: number): string {
  return `${parseFloat((amt / 100).toFixed(4))}%`
}

/** The two-line right-hand display for a rate: primary value + official
 *  phrasing beneath (percentage-primary for value-based, flat for orders). */
export function rateDisplay(rate: ParsedRate): { value: string; unit: string } {
  return rate.unit === 'per10k'
    ? { value: formatRatePct(rate.amt), unit: `${formatRateInr(rate.amt)} per ₹10,000 traded` }
    : { value: formatRateInr(rate.amt), unit: 'flat per order' }
}

/**
 * Cluster the slab by identical (unit, amount) across all segments.
 * Returns the clusters in first-appearance order, or null when any desc
 * fails to parse or the slab needs more than MAX_CLUSTERS rows — the
 * caller then renders the per-segment fallback.
 */
export function brokerageClusters(groups: readonly BrokerageGroup[]): ClusteredItem[][] | null {
  const items: ClusteredItem[] = []
  for (const g of groups) {
    for (const it of g.list) {
      const rate = parseRate(it.desc)
      if (!rate) return null // one unparseable line poisons the whole summary
      items.push({ seg: g.title, title: it.title, rate })
    }
  }
  const map = new Map<string, ClusteredItem[]>()
  for (const it of items) {
    const key = `${it.rate.unit}|${it.rate.amt}`
    const bucket = map.get(key)
    if (bucket) bucket.push(it)
    else map.set(key, [it])
  }
  return map.size <= MAX_CLUSTERS ? [...map.values()] : null
}

/**
 * Label one cluster:
 *   singleton                        → "Equity intraday" (segment + lowercased title)
 *   shared last word ("Future" ×4)   → "All futures" + coverage subline of the
 *                                      titles with the kind stripped ("Stock ·
 *                                      Index · …"; a bare kind falls back to
 *                                      its segment title)
 *   mixed kinds                      → titles joined verbatim, no subline
 */
export function clusterLabel(cluster: readonly ClusteredItem[]): ClusterLabel {
  if (cluster.length === 1) {
    const it = cluster[0]
    return { main: `${it.seg} ${it.title.toLowerCase()}`, cov: null }
  }
  const kinds = cluster.map((it) => it.title.split(' ').pop() ?? it.title)
  const kind = kinds[0]
  if (kinds.every((k) => k === kind)) {
    return {
      main: `All ${kind.toLowerCase()}s`,
      cov: cluster
        .map((it) =>
          it.title.endsWith(kind)
            ? it.title.slice(0, it.title.length - kind.length).trimEnd() || it.seg
            : it.title,
        )
        .join(' · '),
    }
  }
  return { main: cluster.map((it) => it.title).join(' · '), cov: null }
}
