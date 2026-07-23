/**
 * Conversation message model. The chat surface is one continuous list of
 * these; ChatShell appends/updates them imperatively (mirroring the
 * prototype's `add()` rhythm) and renders each by `kind`.
 */

import type { FileInfo, ReportErrorCode } from '../flow/api'
import type { DataErrorCode } from '../flow/dataflow'
import type { FlowRun } from '../flow/engine'
import type { DeliveryMode, FilledValues, HelpKind } from '../flow/types'
import type { ClientNote } from './notes'

let counter = 0
export function nextId(): string {
  counter += 1
  return `m${counter}`
}

export type Message =
  | { id: string; kind: 'user'; text: string }
  /** Bot text line; `**bold**` marks emphasis (see RichText). */
  | { id: string; kind: 'bot'; text: string }
  /** Streaming agent reply — grows in place as SSE text deltas arrive.
   *  Rendered like `bot`, plus pre-wrap so the model's paragraphs survive.
   *  `anchorSeq` (stamped from done.lastSeq onto the exchange-final bubble)
   *  gates the feedback chip; `feedback` is the optimistic rating (CHO-217). */
  | { id: string; kind: 'agent'; text: string; anchorSeq?: number; feedback?: 'up' | 'down' }
  /** Transient "typing…" dots. */
  | { id: string; kind: 'typing' }
  /** The available-actions sticker row (unmatched composer text). */
  | { id: string; kind: 'actions' }
  /** A live slot-filling card. `preferredDelivery` (agent-seeded flows only)
   *  highlights the stated delivery button — the user still taps to fire. */
  | { id: string; kind: 'flow'; run: FlowRun; preferredDelivery?: DeliveryMode }
  /** Narrated-generation pill showing the current caption. */
  | { id: string; kind: 'narrate'; caption: string }
  | {
      id: string
      kind: 'download'
      /** flowKey + values let the card's "Email it" re-invoke the backend. */
      flowKey: string
      values: FilledValues
      file: FileInfo
      fileToken: string
      /** Token-expiry hints (CHO-230) threaded to the native file bridge; the
       *  agent path omits them. */
      ttlSeconds?: number
      expiresAt?: string
      /** Bridge bookkeeping hint (CHO-230): which report family produced the file. */
      source?: 'report' | 'contract-note'
      passwordNote: string | null
      helpKind: HelpKind
      /** Whether the "Email it" affordance applies (false for contract notes,
       *  which have no email delivery). Absent ⇒ emailable. */
      emailable?: boolean
      /** Feedback anchor (agent-path cards only; sticker-path cards submit
       *  without one) + the optimistic rating (CHO-217). */
      anchorSeq?: number
      feedback?: 'up' | 'down'
    }
  | {
      id: string
      kind: 'email'
      noun: string
      emailMasked: string
      anchorSeq?: number
      feedback?: 'up' | 'down'
    }
  /** Contract-notes selection step: the month-grouped tap-to-get list. */
  | {
      id: string
      kind: 'notesList'
      /** The flow message this list belongs to (its date step, for editing). */
      flowMsgId: string
      downloadEndpoint: string
      notes: ClientNote[]
    }
  /** A standalone "Change dates"/"Other dates" pill (empty/error only). */
  | { id: string; kind: 'notesAction'; flowMsgId: string; label: string }
  /** No-data report retry pill (CHO-256): "Try a different range" under a
   *  no-data report line; re-seeds a fresh guided flow with the attempted
   *  values so the user can adjust the range. */
  | { id: string; kind: 'reportRetry'; flowKey: string; values: FilledValues }
  /** Actionable help card (options + raise-a-ticket). */
  | { id: string; kind: 'help'; helpKind: HelpKind }
  /** Ticket-confirmation card — always a REAL Freshdesk ticket id (CHO-218). */
  | { id: string; kind: 'ticket'; ticketId: string }
  /** A rendered data card (the answer in the chat). `data` is the payload the
   *  flow's fetch produced; its Card component narrows it. */
  | {
      id: string
      kind: 'datacard'
      flowKey: string
      data: unknown
      anchorSeq?: number
      feedback?: 'up' | 'down'
    }
  /** Calm empty-state card for a data flow (kind "empty" from the backend). */
  | { id: string; kind: 'dataEmpty'; flowKey: string }
  /** Follow-up line under a data card (help affordance). */
  | { id: string; kind: 'dataFollowup'; flowKey: string }

/** Graceful, in-conversation copy for each backend failure mode. */
export function errorLine(code: ReportErrorCode): string {
  switch (code) {
    case 'AUTH_EXPIRED':
      return "Your session's expired — please reopen AskFinX from FinX and try again."
    case 'NO_DATA':
      return "I couldn't find any P&L for that period. Want to try a different date range?"
    default:
      return 'Something went wrong pulling that report. Mind trying again in a moment?'
  }
}

/** Graceful copy for a data-flow failure; `noun` e.g. "your holdings". */
export function dataErrorLine(code: DataErrorCode, noun: string): string {
  switch (code) {
    case 'auth_expired':
      return "Your session's expired — please reopen AskFinX from FinX and try again."
    case 'no_data':
      return `I couldn't find ${noun} just now. Want to try again in a moment?`
    default:
      return `Something went wrong fetching ${noun}. Mind trying again in a moment?`
  }
}

/** Copy for an agent stream dropping mid-answer (partial text already on
 *  screen, so keyword fallback would read as a non-sequitur). */
export function agentInterruptLine(): string {
  return 'Sorry — I lost the thread there. Mind sending that again?'
}

/** Friendly progress caption for an agent tool round — never the raw tool
 *  name. Matches the tone of the flows' own narration captions. */
export function toolCaption(name: string): string {
  const n = name.toLowerCase()
  if (n.includes('kb') || n.includes('search') || n.includes('knowledge')) return 'Looking that up…'
  if (n.includes('holding')) return 'Fetching your holdings…'
  if (n.includes('money') || n.includes('pay')) return 'Pulling your transactions…'
  if (n.includes('brokerage')) return 'Fetching your plan…'
  if (n.includes('pnl') || n.includes('profit')) return 'Pulling your P&L…'
  if (n.includes('ledger')) return 'Pulling your ledger…'
  if (n.includes('tax') || n.includes('gain')) return 'Preparing your tax report…'
  if (n.includes('contract') || n.includes('note')) return 'Looking up your notes…'
  return 'Working on it…'
}

/** Intro copy for the help card, by kind. */
export function helpIntro(kind: HelpKind): string {
  switch (kind) {
    case 'pdf':
      return 'Your report downloads right here and opens directly — no password needed. Want a hand?'
    case 'cn':
      return "Contract notes aren't password-protected — they should open directly. Want a hand?"
    case 'email':
      return 'Email can take a couple of minutes, or land in spam. Want a hand?'
    case 'holding':
      return 'Prices here are from the last fetch — not a live feed — so they can lag the market. Ask again for fresher numbers. Want a hand?'
    case 'payin':
      return 'Deposits can sit as ‘Pending’ before they land; failed ones auto-reverse. Withdrawals need enough free balance — a rejected one says exactly why in its details. Want a hand?'
    case 'brokerage':
      return "These are your plan's rates — a specific trade's actual charges are on its contract note. Want a hand?"
  }
}
