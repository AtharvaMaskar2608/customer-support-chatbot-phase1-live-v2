/**
 * Conversation message model. The chat surface is one continuous list of
 * these; ChatShell appends/updates them imperatively (mirroring the
 * prototype's `add()` rhythm) and renders each by `kind`.
 */

import type { FileInfo, ReportErrorCode } from '../flow/api'
import type { DataErrorCode } from '../flow/dataflow'
import type { FlowRun } from '../flow/engine'
import type { FilledValues, HelpKind } from '../flow/types'
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
   *  Rendered like `bot`, plus pre-wrap so the model's paragraphs survive. */
  | { id: string; kind: 'agent'; text: string }
  /** Transient "typing…" dots. */
  | { id: string; kind: 'typing' }
  /** The available-actions sticker row (unmatched composer text). */
  | { id: string; kind: 'actions' }
  /** A live slot-filling card. */
  | { id: string; kind: 'flow'; run: FlowRun }
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
      passwordNote: string | null
      helpKind: HelpKind
      /** Whether the "Email it" affordance applies (false for contract notes,
       *  which have no email delivery). Absent ⇒ emailable. */
      emailable?: boolean
    }
  | { id: string; kind: 'email'; noun: string; emailMasked: string }
  /** Contract-notes selection step: the month-grouped tap-to-get list. */
  | {
      id: string
      kind: 'notesList'
      /** The flow message this list belongs to (its date step, for editing). */
      flowMsgId: string
      downloadEndpoint: string
      notes: ClientNote[]
    }
  /** A standalone "Change dates"/"Other dates" pill (single-note & empty/error). */
  | { id: string; kind: 'notesAction'; flowMsgId: string; label: string }
  /** Actionable help card (options + raise-a-ticket). */
  | { id: string; kind: 'help'; helpKind: HelpKind }
  /** Ticket-confirmation card. */
  | { id: string; kind: 'ticket'; ticketId: string }
  /** A rendered data card (the answer in the chat). `data` is the payload the
   *  flow's fetch produced; its Card component narrows it. */
  | { id: string; kind: 'datacard'; flowKey: string; data: unknown }
  /** Calm empty-state card for a data flow (kind "empty" from the backend). */
  | { id: string; kind: 'dataEmpty'; flowKey: string }
  /** Follow-up line under a data card (help affordance). */
  | { id: string; kind: 'dataFollowup'; flowKey: string }

/** Graceful, in-conversation copy for each backend failure mode. */
export function errorLine(code: ReportErrorCode): string {
  switch (code) {
    case 'AUTH_EXPIRED':
      return "Your session's expired — please reopen Jini from FinX and try again."
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
      return "Your session's expired — please reopen Jini from FinX and try again."
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
      return 'These report PDFs are locked with your PAN (all caps) as the password. Want a hand?'
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

/** Stub ticket id, e.g. "CJ-48213" (no real ticketing backend in Wave 0). */
export function makeTicketId(): string {
  return `CJ-${Math.floor(10000 + Math.random() * 90000)}`
}
