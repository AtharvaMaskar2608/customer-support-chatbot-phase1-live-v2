/**
 * Holdings data client (holdings-flow).
 *
 * Pinned payload for POST /api/data/holdings (kind "ok"):
 *   {
 *     asOf: "<ISO>",              // max LUT across scrips, server-derived
 *     rows: [{ sym, name, qty, abp, ltp, current, invested, pnl, pnlPct,
 *              day, dayPct, alloc }, …],   // sorted by current value desc
 *     totals: { current, invested, pnl, pnlPct, day, dayPct, count }
 *   }
 *
 * Every displayed number is derived server-side (paise already normalized to
 * rupees) — the card renders, it does not calculate. `sym` arrives with the
 * exchange suffix stripped; we strip defensively anyway so the CSV's
 * `sym + "-EQ"` reconstruction can never double-append.
 */

import type { DataErrorCode } from '../../flow/dataflow'
import type { SessionContext } from '../../session'
import { postData } from './dataApi'

export interface HoldingRow {
  /** Display symbol, exchange suffix stripped, e.g. "GOLDBEES". */
  sym: string
  name: string
  qty: number
  /** Average buy price (rupees). */
  abp: number
  /** Last traded price (rupees). */
  ltp: number
  current: number
  invested: number
  pnl: number
  pnlPct: number
  /** Last-session move — "1D", never "Today". */
  day: number
  dayPct: number
  /** Share of portfolio current value, 0–100. */
  alloc: number
}

export interface HoldingsTotals {
  current: number
  invested: number
  pnl: number
  pnlPct: number
  day: number
  dayPct: number
  count: number
}

export interface HoldingsData {
  asOf: string
  rows: HoldingRow[]
  totals: HoldingsTotals
}

export type HoldingsResult =
  | { kind: 'ok'; data: HoldingsData }
  | { kind: 'empty' }
  | { kind: 'error'; code: DataErrorCode }

const ROW_NUMBER_KEYS = [
  'qty',
  'abp',
  'ltp',
  'current',
  'invested',
  'pnl',
  'pnlPct',
  'day',
  'dayPct',
  'alloc',
] as const

const TOTALS_NUMBER_KEYS = ['current', 'invested', 'pnl', 'pnlPct', 'day', 'dayPct', 'count'] as const

function hasFiniteNumbers(x: Record<string, unknown>, keys: readonly string[]): boolean {
  return keys.every((k) => typeof x[k] === 'number' && Number.isFinite(x[k]))
}

function isRow(x: unknown): x is HoldingRow {
  if (x === null || typeof x !== 'object') return false
  const r = x as Record<string, unknown>
  return typeof r.sym === 'string' && typeof r.name === 'string' && hasFiniteNumbers(r, ROW_NUMBER_KEYS)
}

function isTotals(x: unknown): x is HoldingsTotals {
  if (x === null || typeof x !== 'object') return false
  return hasFiniteNumbers(x as Record<string, unknown>, TOTALS_NUMBER_KEYS)
}

/** Validate + normalize an `ok` payload body. Shared by the flow fetch and
 *  the agent's data artifacts (CHO-213) — both render the same card. */
export function parseHoldingsPayload(body: Record<string, unknown>): HoldingsResult {
  const { asOf, rows, totals } = body
  if (typeof asOf !== 'string' || !Array.isArray(rows) || !isTotals(totals)) {
    return { kind: 'error', code: 'upstream_error' }
  }
  if (!rows.every(isRow)) return { kind: 'error', code: 'upstream_error' }
  if (rows.length === 0) return { kind: 'empty' }

  return {
    kind: 'ok',
    data: {
      asOf,
      rows: rows.map((r) => ({ ...r, sym: r.sym.replace(/-EQ$/, '') })),
      totals,
    },
  }
}

export async function fetchHoldings(session: SessionContext): Promise<HoldingsResult> {
  const envelope = await postData('/api/data/holdings', session)
  if (envelope.kind !== 'ok') return envelope
  return parseHoldingsPayload(envelope.body)
}
