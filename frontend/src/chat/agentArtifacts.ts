/**
 * Agent data-artifact → existing data-card mapping (CHO-213 task 5.2).
 *
 * A `data` artifact arrives as {kind:"data", tool, ...payload}. This module
 * maps the producing tool's name onto the data flow that owns the matching
 * card and re-validates the payload with the exact parsers the deterministic
 * flows use — the agent path renders through the SAME components, and raw
 * JSON never reaches the conversation (unparseable payloads degrade to the
 * flow's graceful error line; unknown tools render nothing).
 *
 * Canonical Wave-B tool names: get_holdings, get_money, get_brokerage.
 * Matching is by substring so naming drift (e.g. "holdings" vs
 * "get_holdings") cannot silently drop a card.
 */

import { addDays, addYears, customRangeValue, today } from '../flow/dates'
import type { DataErrorCode } from '../flow/dataflow'
import { parseBrokeragePayload } from '../flow/dataflows/brokerage'
import { getFlow } from '../flow/registry'
import type {
  DeliveryMode,
  FilledValues,
  FlowDescriptor,
  Slot,
} from '../flow/types'
import { parseHoldingsPayload } from './datacards/holdings'
import { parseMoneyPayload } from './datacards/money'
import type { AgentDataArtifact, AgentFlowArtifact } from './agent'

/** Result of a parser — the common shape of Holdings/Money/BrokerageResult. */
type ParsedPayload =
  | { kind: 'ok'; data: unknown }
  | { kind: 'empty' }
  | { kind: 'error'; code: DataErrorCode }

export type ParsedDataArtifact =
  | { kind: 'ok'; flowKey: string; data: unknown }
  | { kind: 'empty'; flowKey: string }
  | { kind: 'error'; flowKey: string; code: DataErrorCode }

const MATCHERS: ReadonlyArray<
  readonly [RegExp, string, (body: Record<string, unknown>) => ParsedPayload]
> = [
  [/holding/i, 'holdings', parseHoldingsPayload],
  [/money|pay_?in|pay_?out|fund/i, 'money', parseMoneyPayload],
  [/brokerage/i, 'brokerage', parseBrokeragePayload],
]

/**
 * Resolve a data artifact to its data-flow key + validated payload, or null
 * when no card claims the tool (the agent's own text still narrates).
 */
export function parseDataArtifact(artifact: AgentDataArtifact): ParsedDataArtifact | null {
  for (const [pattern, flowKey, parse] of MATCHERS) {
    if (!pattern.test(artifact.tool)) continue
    const { kind: _kind, tool: _tool, ...body } = artifact
    const parsed = parse(body)
    return parsed.kind === 'ok'
      ? { kind: 'ok', flowKey, data: parsed.data }
      : parsed.kind === 'empty'
        ? { kind: 'empty', flowKey }
        : { kind: 'error', flowKey, code: parsed.code }
  }
  return null
}

/* ── flow artifact → seeded FlowRun input (CHO-214) ───────────────────── */

/** Backend seed field per frontend slot key (dates handled separately). */
const SEED_FIELD: Record<string, string> = {
  segment: 'segment',
  book: 'book',
  finYear: 'fy',
  format: 'format',
}

export interface ParsedFlowArtifact {
  flowKey: string
  /** Only values that validate against the descriptor survive — a dropped
   *  value simply means the widget asks for that slot. */
  seed: FilledValues
  /** Stated delivery preference — highlighted in the UI, never auto-fired. */
  preferredDelivery?: DeliveryMode
}

/** "YYYY-MM-DD" → local-midnight Date, or null. (Not `new Date(iso)`: that
 *  parses as UTC and can shift a day in negative-offset zones.) */
function parseIso(value: unknown): Date | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [y, m, d] = value.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  // Reject rollovers like 2026-02-31.
  return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d
    ? date
    : null
}

function seededDateRange(
  slot: Extract<Slot, { type: 'date' }>,
  seed: Record<string, unknown>,
): FilledValues[string] | null {
  const from = parseIso(seed.fromDate)
  const to = parseIso(seed.toDate)
  if (from === null || to === null || from > to) return null
  const { minDate, futureDaysCap, maxRangeYears } = slot.constraints
  const min = parseIso(minDate)
  if (min !== null && from < min) return null
  if (to > addDays(today(), futureDaysCap)) return null
  if (maxRangeYears !== undefined && to > addYears(from, maxRangeYears)) return null
  return customRangeValue(from, to)
}

/**
 * Re-validate a flow artifact's seed against the live descriptor and build
 * the typed slot values for `startRun(descriptor, seed)`. Invalid or unknown
 * values are dropped (never rendered); an unknown flow key returns null.
 */
export function parseFlowArtifact(artifact: AgentFlowArtifact): ParsedFlowArtifact | null {
  const descriptor: FlowDescriptor | undefined = getFlow(artifact.flowKey)
  if (descriptor === undefined) return null
  const raw = artifact.seed
  const seed: FilledValues = {}

  for (const slot of descriptor.slots) {
    if (slot.type === 'chips' || slot.type === 'format') {
      const value = raw[SEED_FIELD[slot.key] ?? slot.key]
      const option = slot.options.find((o) => o.value === value)
      if (option !== undefined) {
        seed[slot.key] = { type: slot.type, label: option.label, value: option.value }
      }
    } else if (slot.type === 'date') {
      const range = seededDateRange(slot, raw)
      if (range !== null) seed[slot.key] = range
    }
    // 'selection' is never seedable — its options are runtime-fetched.
  }

  const delivery = raw.delivery
  const preferredDelivery =
    (delivery === 'download' || delivery === 'email') &&
    descriptor.delivery.some((o) => o.mode === delivery)
      ? delivery
      : undefined
  return { flowKey: descriptor.key, seed, preferredDelivery }
}
