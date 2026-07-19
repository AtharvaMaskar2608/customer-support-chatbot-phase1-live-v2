/**
 * Paise-safe, Indian-grouped INR formatting (data-card-system).
 *
 * All arithmetic happens in total paise (integers) so float edge cases like
 * 0.1 + 0.2 can never leak into what the customer reads. Whole rupees render
 * with no decimals ("₹1,01,49,986"); sub-rupee amounts keep their paise
 * ("₹0.10", "₹612.10"). Ported from the approved prototype's `moneyAbs`.
 */

/**
 * Format the ABSOLUTE value of `n` as Indian-grouped rupees. Callers own the
 * sign presentation (▴/▾ glyphs, +/− prefixes) — a data card never shows a
 * bare negative number.
 */
export function formatInr(n: number): string {
  const totalPaise = Math.round(Math.abs(n) * 100)
  const rupees = Math.floor(totalPaise / 100)
  const paise = totalPaise % 100

  // Indian grouping: last 3 digits, then pairs (₹1,01,49,986).
  let s = String(rupees)
  if (s.length > 3) {
    const last3 = s.slice(-3)
    const rest = s.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',')
    s = `${rest},${last3}`
  }

  return `₹${s}${paise ? `.${String(paise).padStart(2, '0')}` : ''}`
}

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/**
 * Freshness stamp for the hero line — "17 Jul, 3:59 pm". Derived from the
 * API's own timestamp (max LUT, computed server-side), never a hardcode.
 * Falls back to the raw string if the ISO date fails to parse.
 */
export function formatAsOf(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  let h = d.getHours()
  const ap = h >= 12 ? 'pm' : 'am'
  h = h % 12 || 12
  return `${d.getDate()} ${MON[d.getMonth()]}, ${h}:${String(d.getMinutes()).padStart(2, '0')} ${ap}`
}
