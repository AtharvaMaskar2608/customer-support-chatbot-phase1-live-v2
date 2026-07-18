/**
 * Contract-notes backend client (the selection flow's delivery layer).
 *
 * Two calls, mirroring the normalized envelopes the P&L client returns:
 *   POST <list>     {fromDate,toDate} → {notes:[{id,date,segment,badge,month}]}
 *   POST <download> {id}              → {delivery:"download", file, fileToken}
 *
 * The browser never sees the upstream file_id — the list hands back an opaque,
 * server-mapped id, and download resolves it server-side. Failures degrade
 * gracefully into the conversation via the shared ReportErrorCode set.
 */

import { hasCredentials, type SessionContext } from '../session'
import type { FileInfo, ReportErrorCode } from '../flow/api'

/** One pickable contract note (file_id-free — `id` is the opaque token). */
export interface ClientNote {
  id: string
  /** "9 Jun 2024" — the trade date. */
  date: string
  /** "Equity & F&O" | "Commodity". */
  segment: string
  /** Exchange badge, set only to disambiguate a date with two notes. */
  badge: string | null
  /** "JUNE 2024" — the month-group header. */
  month: string
}

export type NotesListResult =
  | { kind: 'list'; notes: ClientNote[] }
  | { kind: 'error'; code: ReportErrorCode }

export type NoteDownloadResult =
  | { kind: 'download'; file: FileInfo; fileToken: string }
  | { kind: 'error'; code: ReportErrorCode }

/** Same credential triple as the P&L fetch. Raw JWT — no "Bearer". */
function authHeaders(session: SessionContext): Record<string, string> {
  return {
    Authorization: session.accessToken!,
    'X-Session-Id': session.sessionId!,
    'X-User-Id': session.userId!,
  }
}

function statusToError(status: number): ReportErrorCode {
  if (status === 400 || status === 401) return 'AUTH_EXPIRED'
  if (status === 404) return 'NO_DATA'
  return 'UPSTREAM_ERROR'
}

function isClientNote(x: unknown): x is ClientNote {
  if (x === null || typeof x !== 'object') return false
  const n = x as Record<string, unknown>
  return (
    typeof n.id === 'string' &&
    typeof n.date === 'string' &&
    typeof n.segment === 'string' &&
    typeof n.month === 'string' &&
    (n.badge === null || typeof n.badge === 'string')
  )
}

function isFileInfo(x: unknown): x is FileInfo {
  if (x === null || typeof x !== 'object') return false
  const f = x as Record<string, unknown>
  return (
    typeof f.name === 'string' &&
    typeof f.sizeLabel === 'string' &&
    typeof f.format === 'string'
  )
}

/** Fetch the pickable list of notes for a date range. */
export async function fetchContractNotes(
  endpoint: string,
  fromDate: string,
  toDate: string,
  session: SessionContext,
): Promise<NotesListResult> {
  if (!hasCredentials(session)) return { kind: 'error', code: 'AUTH_EXPIRED' }

  let res: Response
  try {
    res = await fetch(endpoint, {
      method: 'POST',
      headers: { ...authHeaders(session), 'Content-Type': 'application/json' },
      body: JSON.stringify({ fromDate, toDate }),
    })
  } catch {
    return { kind: 'error', code: 'NETWORK' }
  }

  if (!res.ok) return { kind: 'error', code: statusToError(res.status) }

  const body: unknown = await res.json().catch(() => null)
  if (body === null || typeof body !== 'object') return { kind: 'error', code: 'UPSTREAM_ERROR' }
  const notes = (body as Record<string, unknown>).notes
  if (!Array.isArray(notes)) return { kind: 'error', code: 'UPSTREAM_ERROR' }
  return { kind: 'list', notes: notes.filter(isClientNote) }
}

/** Download one note by its opaque id; server stores bytes + returns a token. */
export async function downloadContractNote(
  endpoint: string,
  id: string,
  session: SessionContext,
): Promise<NoteDownloadResult> {
  if (!hasCredentials(session)) return { kind: 'error', code: 'AUTH_EXPIRED' }

  let res: Response
  try {
    res = await fetch(endpoint, {
      method: 'POST',
      headers: { ...authHeaders(session), 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    })
  } catch {
    return { kind: 'error', code: 'NETWORK' }
  }

  if (!res.ok) return { kind: 'error', code: statusToError(res.status) }

  const body: unknown = await res.json().catch(() => null)
  if (body === null || typeof body !== 'object') return { kind: 'error', code: 'UPSTREAM_ERROR' }
  const data = body as Record<string, unknown>
  if (data.delivery === 'download' && isFileInfo(data.file) && typeof data.fileToken === 'string') {
    return { kind: 'download', file: data.file, fileToken: data.fileToken }
  }
  return { kind: 'error', code: 'UPSTREAM_ERROR' }
}
