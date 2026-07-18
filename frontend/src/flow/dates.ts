/**
 * Date helpers for the `date` slot type — preset resolution + the constrained
 * custom-range calendar math. All ranges resolve to `YYYY-MM-DD` for the
 * backend and carry a customer-facing label for the chip.
 */

import type { DatePreset, DateRangeValue } from './types'

const MON = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]
export const MONTHS_LONG = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]
export const DOW = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

/** Local-midnight Date, stripped of time — the reference "today". */
export function today(): Date {
  const n = new Date()
  return new Date(n.getFullYear(), n.getMonth(), n.getDate())
}

export function toIso(d: Date): string {
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/** e.g. "18-Jul-2026" — the as-of stamp on result copy. */
export function toHuman(d: Date): string {
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${day}-${MON[d.getMonth()]}-${d.getFullYear()}`
}

/** Indian financial year (Apr 1 → Mar 31) containing `d`; returns start date
 *  and the "2026-27" style label. */
function financialYear(d: Date): { start: Date; label: string } {
  const y = d.getFullYear()
  // Months are 0-indexed; April = 3.
  const startYear = d.getMonth() >= 3 ? y : y - 1
  const start = new Date(startYear, 3, 1)
  const label = `FY ${startYear}-${`${startYear + 1}`.slice(2)}`
  return { start, label }
}

function rangeLabel(from: Date, to: Date): string {
  const sameYear = from.getFullYear() === to.getFullYear()
  if (sameYear) return `${MON[from.getMonth()]}–${MON[to.getMonth()]} ${to.getFullYear()}`
  return `${MON[from.getMonth()]} ${from.getFullYear()} – ${MON[to.getMonth()]} ${to.getFullYear()}`
}

/** Shared preset set for report date ranges (P&L / Ledger). */
export const REPORT_DATE_PRESETS: DatePreset[] = [
  {
    label: 'This FY',
    resolve: (t) => {
      const fy = financialYear(t)
      return { type: 'date', label: fy.label, fromDate: toIso(fy.start), toDate: toIso(t) }
    },
  },
  {
    label: 'This month',
    resolve: (t) => {
      const start = new Date(t.getFullYear(), t.getMonth(), 1)
      return {
        type: 'date',
        label: `${MONTHS_LONG[t.getMonth()]} ${t.getFullYear()}`,
        fromDate: toIso(start),
        toDate: toIso(t),
      }
    },
  },
  {
    label: 'Last 3 months',
    resolve: (t) => {
      const start = new Date(t.getFullYear(), t.getMonth() - 3, t.getDate())
      return {
        type: 'date',
        label: rangeLabel(start, t),
        fromDate: toIso(start),
        toDate: toIso(t),
      }
    },
  },
]

/** Build the display label for a hand-picked custom range. */
export function customRangeValue(from: Date, to: Date): DateRangeValue {
  const label = `${from.getDate()} ${MON[from.getMonth()]} – ${to.getDate()} ${MON[to.getMonth()]} ${to.getFullYear()}`
  return { type: 'date', label, fromDate: toIso(from), toDate: toIso(to) }
}

export function addYears(d: Date, years: number): Date {
  return new Date(d.getFullYear() + years, d.getMonth(), d.getDate())
}

export function addDays(d: Date, days: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + days)
}

export function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

/** Parse "YYYY-MM-DD" to a local-midnight Date. */
export function fromIso(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}
