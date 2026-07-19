/**
 * Data-flow descriptor schema (CHO-211).
 *
 * The second flow family. File flows (FlowDescriptor) end in a delivered
 * file; data flows end in an interactive card rendered in the conversation —
 * the answer IS the card. A data flow is zero-or-more-slot (Holdings is
 * zero-slot: sticker → narration → card) and pairs a typed fetch with the
 * Card component that renders its payload.
 *
 * Adding a data flow (Money, Brokerage — Wave B) = drop one descriptor file
 * into `dataflows/` + one card component under `chat/datacards/`; the
 * registry, stickers, keyword routing and shell need no edits.
 */

import type { ComponentType } from 'react'
import type { SessionContext } from '../session'
import type { FlowDescriptor, HelpKind, IconComponent, TintKey } from './types'

/** Normalized failure kinds for the `/api/data/*` envelope (lowercase on the
 *  wire, unlike the file flows' HTTP-status-derived codes). */
export type DataErrorCode = 'auth_expired' | 'no_data' | 'upstream_error' | 'network'

export type DataFetchResult<T = unknown> =
  | { kind: 'ok'; data: T }
  /** The account genuinely has nothing here (calm card line, not an error). */
  | { kind: 'empty' }
  | { kind: 'error'; code: DataErrorCode }

/** Props every data-card component receives. `data` is the payload the
 *  descriptor's own `fetch` produced — the card narrows it back to its
 *  concrete type (the descriptor pairs the two, so the cast is sound). */
export interface DataCardProps {
  data: unknown
  session: SessionContext
}

export interface DataFlowDescriptor {
  /** Discriminant vs FlowDescriptor (which has no `kind`). */
  kind: 'data'
  /** Stable key, the flow's identity in the data registry, e.g. "holdings". */
  key: string
  /** Sticker ordering — shared scale with the file flows (Holdings is 0,
   *  ahead of P&L's 1). */
  order: number
  /** The phrase echoed as the user's message on tap (and the default
   *  sticker label when `stickerLabel` is absent). */
  trigger: string
  /** Short sticker label when it should differ from the echoed phrase
   *  (prototype: sticker "Brokerage" vs echo "What is my brokerage?"). */
  stickerLabel?: string
  /** Composer keyword routing (checked before the file flows). */
  keywords: RegExp
  sticker: { icon: IconComponent; tint: TintKey }
  /** First bot line once the flow starts (must stay time-honest — never
   *  claim live prices). */
  intro: string
  /** Narrated-fetch captions shown while the request is in flight. */
  narration: string[]
  /** The one backend call; the card renders whatever this resolves. */
  fetch: (session: SessionContext) => Promise<DataFetchResult>
  /** Renders the `ok` payload as the in-chat card. */
  Card: ComponentType<DataCardProps>
  /** Calm line rendered in the card frame for `empty`. */
  emptyLine: string
  /** Noun for error copy, e.g. "your holdings". */
  errorNoun: string
  /** Follow-up under the card ("Tap any holding… · Something look off?"),
   *  or null for none. */
  followup: { text: string; linkLabel: string } | null
  /** Which help copy the follow-up link opens. */
  helpKind: HelpKind
}

export type AnyFlowDescriptor = FlowDescriptor | DataFlowDescriptor

export function isDataFlow(flow: AnyFlowDescriptor): flow is DataFlowDescriptor {
  return 'kind' in flow && (flow as DataFlowDescriptor).kind === 'data'
}
