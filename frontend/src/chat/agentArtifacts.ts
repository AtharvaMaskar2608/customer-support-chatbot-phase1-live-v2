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

import type { DataErrorCode } from '../flow/dataflow'
import { parseBrokeragePayload } from '../flow/dataflows/brokerage'
import { parseHoldingsPayload } from './datacards/holdings'
import { parseMoneyPayload } from './datacards/money'
import type { AgentDataArtifact } from './agent'

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
