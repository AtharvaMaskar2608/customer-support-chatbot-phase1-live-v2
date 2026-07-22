/**
 * Holdings CSV export (holdings-flow) — client-side, from data the card
 * already holds: no extra endpoint, no second copy of the portfolio in
 * flight. Mirrors FinX's own "Holding Overall Report" export byte-for-byte
 * in shape (see docs/prototype/samples/):
 *
 *   Instrument,Exchange,QTY | LOT,Avg. Price,LTP,Invested Amt.,Current Value,
 *   Returns,Returns %,Product
 *   GOLDBEES-EQ,NSE,88,64.09,115.79,5639.89,10189.52,4549.6,80.67,DELIVERY
 *
 * Filename: {UserCode}_Holding_Overall_Report_{yyyymmddhhmmssms}.csv — the
 * real UserCode from the session, never a hardcode. The filename stays on the
 * button feedback side: it is NEVER echoed into the conversation.
 */

import { sendInlineFileToHost } from '../../bridge'
import type { HoldingRow } from './holdings'

const HEADER = [
  'Instrument',
  'Exchange',
  'QTY | LOT',
  'Avg. Price',
  'LTP',
  'Invested Amt.',
  'Current Value',
  'Returns',
  'Returns %',
  'Product',
]

/** FinX's CSV number style: max 2 decimals, trailing zeros dropped ("177"). */
export function csvNum(n: number): string {
  return String(Math.round(n * 100) / 100)
}

/** "202607181927757"-style stamp: yyyy mm dd hh mm ss + 3-digit ms. */
export function csvStamp(now: Date = new Date()): string {
  const p = (n: number, l = 2) => String(n).padStart(l, '0')
  return (
    `${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}` +
    `${p(now.getHours())}${p(now.getMinutes())}${p(now.getSeconds())}${p(now.getMilliseconds(), 3)}`
  )
}

export function holdingsCsvFilename(userCode: string, now: Date = new Date()): string {
  return `${userCode}_Holding_Overall_Report_${csvStamp(now)}.csv`
}

export function buildHoldingsCsv(rows: readonly HoldingRow[]): string {
  const lines = [HEADER.join(',')]
  for (const r of rows) {
    lines.push(
      [
        `${r.sym}-EQ`, // display sym is suffix-stripped; the export restores it
        'NSE',
        String(r.qty),
        csvNum(r.abp),
        csvNum(r.ltp),
        csvNum(r.invested),
        csvNum(r.current),
        csvNum(r.pnl),
        csvNum(r.pnlPct),
        'DELIVERY',
      ].join(','),
    )
  }
  return lines.join('\r\n')
}

/** Build + hand the CSV off. Native host first (CHO-230): the inline bridge
 *  gets the CSV when running in the Android WebView; otherwise the browser Blob
 *  download stays the web fallback. Returns success. */
export function downloadHoldingsCsv(rows: readonly HoldingRow[], userCode: string): boolean {
  const csv = buildHoldingsCsv(rows)
  const filename = holdingsCsvFilename(userCode)
  if (sendInlineFileToHost(filename, csv)) return true
  try {
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(a.href)
    return true
  } catch {
    return false
  }
}
