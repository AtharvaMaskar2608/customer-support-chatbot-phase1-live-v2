/**
 * Report backend client (delivery layer, frontend half).
 *
 * Pinned contract:
 *   POST /api/report/pnl
 *     Headers: Authorization <SSO JWT>, X-Session-Id, X-User-Id
 *     Body:    {segment, fromDate, toDate, delivery}
 *     200 download → {delivery:"download", file:{name,sizeLabel,format,passwordProtected}, fileToken}
 *     200 email    → {delivery:"email", emailMasked}
 *     401 AUTH_EXPIRED / 404 NO_DATA / 502 UPSTREAM_ERROR
 *   GET /api/report/file/{fileToken}  (streams the PDF; token is session-bound,
 *     so the X-Session-Id header MUST be sent — a bare anchor won't carry it)
 *
 * The browser never sees the upstream URL/file_id/email — only this normalized
 * envelope. Any failure degrades gracefully into the conversation.
 */

import { hasCredentials, type SessionContext } from '../session'
import type { BackendConfig, DeliveryMode, FilledValues } from './types'

export interface FileInfo {
  name: string
  sizeLabel: string
  format: string
  passwordProtected: boolean
}

export type ReportErrorCode = 'AUTH_EXPIRED' | 'NO_DATA' | 'UPSTREAM_ERROR' | 'NETWORK'

export type ReportResult =
  // `ttlSeconds`/`expiresAt` (CHO-230) are additive hints for the native
  // file bridge — how long the opaque download token stays valid. Optional:
  // older backends and the agent path omit them.
  | { kind: 'download'; file: FileInfo; fileToken: string; ttlSeconds?: number; expiresAt?: string }
  | { kind: 'email'; emailMasked: string }
  | { kind: 'error'; code: ReportErrorCode }

/** Same credential triple as the greeting fetch. Raw JWT — no "Bearer". */
function authHeaders(session: SessionContext): Record<string, string> {
  return {
    Authorization: session.accessToken!,
    'X-Session-Id': session.sessionId!,
    'X-User-Id': session.userId!,
  }
}

function statusToError(status: number): ReportErrorCode {
  // 400 MISSING_CREDENTIALS + 401 AUTH_EXPIRED both resolve to "reopen from FinX".
  if (status === 400 || status === 401) return 'AUTH_EXPIRED'
  if (status === 404) return 'NO_DATA'
  return 'UPSTREAM_ERROR'
}

/** Structural check for the pinned file payload (also used by the agent SSE
 *  client to validate file artifacts before rendering the download card). */
export function isFileInfo(x: unknown): x is FileInfo {
  if (x === null || typeof x !== 'object') return false
  const f = x as Record<string, unknown>
  return typeof f.name === 'string' && typeof f.sizeLabel === 'string' && typeof f.format === 'string'
}

export async function submitReport(
  backend: BackendConfig,
  values: FilledValues,
  mode: DeliveryMode,
  session: SessionContext,
): Promise<ReportResult> {
  // No credentials → cannot authenticate the report; treat as expired session.
  if (!hasCredentials(session)) return { kind: 'error', code: 'AUTH_EXPIRED' }

  let res: Response
  try {
    res = await fetch(backend.endpoint, {
      method: 'POST',
      headers: { ...authHeaders(session), 'Content-Type': 'application/json' },
      body: JSON.stringify(backend.buildBody(values, mode)),
    })
  } catch {
    return { kind: 'error', code: 'NETWORK' }
  }

  if (!res.ok) return { kind: 'error', code: statusToError(res.status) }

  const body: unknown = await res.json().catch(() => null)
  if (body === null || typeof body !== 'object') return { kind: 'error', code: 'UPSTREAM_ERROR' }
  const data = body as Record<string, unknown>

  if (data.delivery === 'email' && typeof data.emailMasked === 'string') {
    return { kind: 'email', emailMasked: data.emailMasked }
  }
  if (data.delivery === 'download' && isFileInfo(data.file) && typeof data.fileToken === 'string') {
    return {
      kind: 'download',
      file: data.file,
      fileToken: data.fileToken,
      ttlSeconds: typeof data.ttlSeconds === 'number' ? data.ttlSeconds : undefined,
      expiresAt: typeof data.expiresAt === 'string' ? data.expiresAt : undefined,
    }
  }
  return { kind: 'error', code: 'UPSTREAM_ERROR' }
}

/**
 * Hand the file to the browser as a download via a plain token link.
 * The token is opaque + short-TTL, so no session header is needed — a bare
 * anchor to our own endpoint works, and Content-Disposition names the file.
 */
export function downloadReportFile(fileToken: string, fileName: string): boolean {
  try {
    const a = document.createElement('a')
    a.href = `/api/report/file/${encodeURIComponent(fileToken)}`
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    a.remove()
    return true
  } catch {
    return false
  }
}
