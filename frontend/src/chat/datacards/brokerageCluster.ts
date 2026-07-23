/**
 * Brokerage slab domain logic (brokerage-flow) — parse, order segments,
 * format. Ported from the approved prototype parseRate / fmtInr helpers;
 * CHO-259 replaced cross-segment rate clustering with a fixed-order
 * segment accordion (Equity → Derivative → Commodity → Currency).
 *
 * The slab arrives as per-segment groups of { title, desc } lines
 * ("₹20.00 for trade value of 10 thousand"). Per-line honesty: unparseable
 * desc falls back to upstream text at the call site — never invent a
 * cross-segment summary.
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

/** Fixed accordion order (CHO-259) — API order is ignored. */
export const BROKERAGE_SEGMENT_ORDER = [
  'Equity',
  'Derivative',
  'Commodity',
  'Currency',
] as const

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
 *  trimmed (₹20 → "0.2%", never "0.2000%"). Kept for non-card callers. */
export function formatRatePct(amt: number): string {
  return `${parseFloat((amt / 100).toFixed(4))}%`
}

/**
 * Single-line ₹-primary display for the brokerage card (CHO-259).
 * Percentage-primary is intentionally not returned.
 */
export function rateDisplay(rate: ParsedRate): string {
  return rate.unit === 'per10k'
    ? `${formatRateInr(rate.amt)} per ₹10,000 traded`
    : `${formatRateInr(rate.amt)} flat per order`
}

/**
 * Return non-empty groups in fixed Equity → Derivative → Commodity → Currency
 * order. Unknown titles append after the known four, preserving their
 * relative input order.
 */
export function orderBrokerageGroups(groups: readonly BrokerageGroup[]): BrokerageGroup[] {
  const byTitle = new Map<string, BrokerageGroup>()
  for (const g of groups) byTitle.set(g.title, g)

  const ordered: BrokerageGroup[] = []
  for (const title of BROKERAGE_SEGMENT_ORDER) {
    const g = byTitle.get(title)
    if (g) {
      ordered.push(g)
      byTitle.delete(title)
    }
  }
  for (const g of groups) {
    if (byTitle.has(g.title)) {
      ordered.push(g)
      byTitle.delete(g.title)
    }
  }
  return ordered
}
