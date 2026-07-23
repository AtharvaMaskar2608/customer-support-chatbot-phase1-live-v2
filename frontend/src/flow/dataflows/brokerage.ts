/**
 * Brokerage data flow (brokerage-flow) — the rate card.
 *
 * Zero-slot: keyword → narrated fetch → segment accordion card (CHO-259).
 * The slab is per-client; segment order and ₹ phrasing live in
 * chat/datacards/brokerageCluster.ts. The card presents the PLAN, never
 * charges billed — statutory-charges + contract-note honesty lives in the
 * card footer; follow-up chips route to contract notes or raise-ticket.
 *
 * The fetch lives here (not a separate datacards client) so
 * brokerageCluster.ts stays a pure, dependency-free domain module.
 */

import { BrokerageCard } from '../../chat/datacards/BrokerageCard'
import type { BrokerageData, BrokerageGroup, BrokerageItem } from '../../chat/datacards/brokerageCluster'
import { postData } from '../../chat/datacards/dataApi'
import { TagIcon } from '../../icons'
import type { SessionContext } from '../../session'
import type { DataErrorCode, DataFlowDescriptor } from '../dataflow'

export type BrokerageResult =
  | { kind: 'ok'; data: BrokerageData }
  | { kind: 'empty' }
  | { kind: 'error'; code: DataErrorCode }

function isItem(x: unknown): x is BrokerageItem {
  if (x === null || typeof x !== 'object') return false
  const r = x as Record<string, unknown>
  return typeof r.title === 'string' && typeof r.desc === 'string'
}

function isGroup(x: unknown): x is BrokerageGroup {
  if (x === null || typeof x !== 'object') return false
  const r = x as Record<string, unknown>
  return typeof r.title === 'string' && Array.isArray(r.list) && r.list.every(isItem)
}

/**
 * POST /api/data/brokerage — the slab passthrough (no PII; needs a fresh
 * SSO JWT upstream, so auth_expired is the common dev-time failure).
 * Pinned `ok` payload:
 *   { groups: [{ title: "Equity", list: [{ title: "Intraday",
 *     desc: "₹0.10 for trade value of 10 thousand" }, …] }, …] }
 * Segments with no lines are dropped; a slab with no lines at all is `empty`.
 */
export async function fetchBrokerage(session: SessionContext): Promise<BrokerageResult> {
  const envelope = await postData('/api/data/brokerage', session)
  if (envelope.kind !== 'ok') return envelope
  return parseBrokeragePayload(envelope.body)
}

/** Validate + normalize an `ok` payload body. Shared by the flow fetch and
 *  the agent's data artifacts (CHO-213) — both render the same card. */
export function parseBrokeragePayload(body: Record<string, unknown>): BrokerageResult {
  const { groups } = body
  if (!Array.isArray(groups) || !groups.every(isGroup)) {
    return { kind: 'error', code: 'upstream_error' }
  }
  const nonEmpty = groups.filter((g) => g.list.length > 0)
  if (nonEmpty.length === 0) return { kind: 'empty' }

  return { kind: 'ok', data: { groups: nonEmpty } }
}

const brokerage: DataFlowDescriptor = {
  kind: 'data',
  key: 'brokerage',
  order: 6, // last sticker — after Pay in / out (5), matching the prototype row
  trigger: 'What is my brokerage?',
  stickerLabel: 'Brokerage',
  // CHO-233: business wants brokerage off the home chip grid, but the flow
  // stays reachable by typing (keywords below) and via the rate card.
  hideSticker: true,
  keywords: /brokerage|my charges|my fees|rate card|slab/i,
  sticker: { icon: TagIcon, tint: 'rose' },
  intro: "Here's your brokerage plan — tap a segment to expand.",
  narration: ['Fetching your plan…'],
  fetch: fetchBrokerage,
  Card: BrokerageCard,
  emptyLine: 'No brokerage plan found on your account',
  errorNoun: 'your brokerage plan',
  followup: {
    chips: [
      { label: 'Get my contract note', action: 'startFlow', flowKey: 'contract-notes' },
      { label: 'Raise a ticket', emoji: '🎫', action: 'raiseTicket' },
    ],
  },
  helpKind: 'brokerage',
}

export default brokerage
