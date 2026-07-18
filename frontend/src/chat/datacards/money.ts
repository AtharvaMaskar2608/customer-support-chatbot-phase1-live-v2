/**
 * Money data client (money-flow).
 *
 * Pinned payload for POST /api/data/money (kind "ok"):
 *   {
 *     txns: [{ dir: "in"|"out", amt, st, dt, mode, dest, ref, rsn }, …],
 *       // ONE merged pay-in + pay-out stream, already newest-first;
 *       // mode/dest/ref/rsn are string-or-null (dest arrives masked:
 *       // bank name + last-4 — never a full account number)
 *     counts: { SUCCESS, PENDING, FAILURE, CANCELLED },
 *     landed: { in, out },        // SUCCESS-only totals (rupees)
 *     totalRecords: { in, out },  // upstream TotalRecords per direction
 *     partial: false              // true ⇒ one direction failed upstream
 *   }
 *
 * Merging, sorting, status counting and landed totals all happen server-side
 * — the card renders, it does not calculate. `rsn` (pay-out's Reason) is
 * displayed verbatim, never branched on.
 */

import type { DataErrorCode } from '../../flow/dataflow'
import type { SessionContext } from '../../session'
import { postData } from './dataApi'
import type { CanonicalStatus } from './tokens'

export interface MoneyTxn {
  /** Passbook direction: "in" = deposit, "out" = withdrawal. */
  dir: 'in' | 'out'
  /** Amount in rupees (paise-safe rendering is the card's job). */
  amt: number
  st: CanonicalStatus
  /** ISO 8601 request time, e.g. "2026-07-08T16:19:45". */
  dt: string
  /** Payment mode ("UPI", "Bank", "NB"…), or null. */
  mode: string | null
  /** Masked destination, e.g. "ICICI ••7280", or null. */
  dest: string | null
  /** Voucher/reference number, or null. */
  ref: string | null
  /** Upstream Reason, verbatim — displayed, never branched on. Or null. */
  rsn: string | null
}

export interface MoneyData {
  /** Merged newest-first stream (server-sorted). */
  txns: MoneyTxn[]
  counts: Record<CanonicalStatus, number>
  landed: { in: number; out: number }
  totalRecords: { in: number; out: number }
  /** One direction failed upstream — render what loaded + a quiet notice. */
  partial: boolean
}

export type MoneyResult =
  | { kind: 'ok'; data: MoneyData }
  | { kind: 'empty' }
  | { kind: 'error'; code: DataErrorCode }

const STATUSES: readonly CanonicalStatus[] = ['SUCCESS', 'PENDING', 'FAILURE', 'CANCELLED']

function isStatus(x: unknown): x is CanonicalStatus {
  return typeof x === 'string' && (STATUSES as readonly string[]).includes(x)
}

/** Optional-string fields: null stays null; empty-string sentinels (already
 *  normalized server-side, but harmless to re-normalize) also become null. */
function optional(v: unknown): string | null {
  return typeof v === 'string' && v !== '' ? v : null
}

function parseTxn(x: unknown): MoneyTxn | null {
  if (x === null || typeof x !== 'object') return null
  const t = x as Record<string, unknown>
  if (t.dir !== 'in' && t.dir !== 'out') return null
  if (typeof t.amt !== 'number' || !Number.isFinite(t.amt)) return null
  if (!isStatus(t.st) || typeof t.dt !== 'string') return null
  return {
    dir: t.dir,
    amt: t.amt,
    st: t.st,
    dt: t.dt,
    mode: optional(t.mode),
    dest: optional(t.dest),
    ref: optional(t.ref),
    rsn: optional(t.rsn),
  }
}

/** Counts map — a missing status key reads as 0 (callers render non-zero only). */
function parseCounts(x: unknown): Record<CanonicalStatus, number> | null {
  if (x === null || typeof x !== 'object') return null
  const c = x as Record<string, unknown>
  const out = {} as Record<CanonicalStatus, number>
  for (const k of STATUSES) {
    const v = c[k]
    if (v === undefined) {
      out[k] = 0
      continue
    }
    if (typeof v !== 'number' || !Number.isFinite(v)) return null
    out[k] = v
  }
  return out
}

function parseInOut(x: unknown): { in: number; out: number } | null {
  if (x === null || typeof x !== 'object') return null
  const r = x as Record<string, unknown>
  if (typeof r.in !== 'number' || !Number.isFinite(r.in)) return null
  if (typeof r.out !== 'number' || !Number.isFinite(r.out)) return null
  return { in: r.in, out: r.out }
}

export async function fetchMoney(session: SessionContext): Promise<MoneyResult> {
  const envelope = await postData('/api/data/money', session)
  if (envelope.kind !== 'ok') return envelope

  const { txns, counts, landed, totalRecords, partial } = envelope.body
  if (!Array.isArray(txns) || typeof partial !== 'boolean') {
    return { kind: 'error', code: 'upstream_error' }
  }
  const parsed: MoneyTxn[] = []
  for (const raw of txns) {
    const t = parseTxn(raw)
    if (!t) return { kind: 'error', code: 'upstream_error' }
    parsed.push(t)
  }
  const c = parseCounts(counts)
  const l = parseInOut(landed)
  const tr = parseInOut(totalRecords)
  if (!c || !l || !tr) return { kind: 'error', code: 'upstream_error' }

  // Genuinely nothing this period → the calm empty line. A partial result
  // with zero rows still renders the card (its notice explains the gap).
  if (parsed.length === 0 && !partial) return { kind: 'empty' }

  return {
    kind: 'ok',
    data: { txns: parsed, counts: c, landed: l, totalRecords: tr, partial },
  }
}
