/**
 * Conversation message model. The chat surface is one continuous list of
 * these; ChatShell appends/updates them imperatively (mirroring the
 * prototype's `add()` rhythm) and renders each by `kind`.
 */

import type { FileInfo, ReportErrorCode } from '../flow/api'
import type { FlowRun } from '../flow/engine'
import type { FilledValues, HelpKind } from '../flow/types'

let counter = 0
export function nextId(): string {
  counter += 1
  return `m${counter}`
}

export type Message =
  | { id: string; kind: 'user'; text: string }
  /** Bot text line; `**bold**` marks emphasis (see RichText). */
  | { id: string; kind: 'bot'; text: string }
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
    }
  | { id: string; kind: 'email'; noun: string; emailMasked: string }
  /** Actionable help card (options + raise-a-ticket). */
  | { id: string; kind: 'help'; helpKind: HelpKind }
  /** Ticket-confirmation card. */
  | { id: string; kind: 'ticket'; ticketId: string }

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

/** Intro copy for the help card, by kind. */
export function helpIntro(kind: HelpKind): string {
  switch (kind) {
    case 'pdf':
      return 'These report PDFs are locked with your PAN (all caps) as the password. Want a hand?'
    case 'cn':
      return "Contract notes aren't password-protected — they should open directly. Want a hand?"
    case 'email':
      return 'Email can take a couple of minutes, or land in spam. Want a hand?'
  }
}

/** Stub ticket id, e.g. "CJ-48213" (no real ticketing backend in Wave 0). */
export function makeTicketId(): string {
  return `CJ-${Math.floor(10000 + Math.random() * 90000)}`
}
