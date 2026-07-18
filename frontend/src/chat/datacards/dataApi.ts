/**
 * Data backend client (finx-data-backend, frontend half).
 *
 * Pinned envelope for every `/api/data/*` endpoint:
 *   POST <endpoint>
 *     Headers: Authorization <SSO JWT>, X-Session-Id, X-User-Id (same triple
 *     as the report flows — the backend owns per-upstream auth mapping)
 *     200 → {"kind":"ok", ...payload} | {"kind":"empty"}
 *         | {"kind":"auth_expired"|"no_data"|"upstream_error"}
 *   Non-2xx statuses degrade to the same codes (400/401 → auth_expired,
 *   404 → no_data, else upstream_error) so either signalling style works.
 *
 * The browser never sees upstream URLs or unfiltered bodies — only this
 * normalized envelope; per-flow clients (holdings, …) validate the payload.
 */

import { hasCredentials, type SessionContext } from '../../session'
import type { DataErrorCode } from '../../flow/dataflow'

export type DataEnvelope =
  | { kind: 'ok'; body: Record<string, unknown> }
  | { kind: 'empty' }
  | { kind: 'error'; code: DataErrorCode }

/** Same credential triple as the report fetches. Raw JWT — no "Bearer". */
function authHeaders(session: SessionContext): Record<string, string> {
  return {
    Authorization: session.accessToken!,
    'X-Session-Id': session.sessionId!,
    'X-User-Id': session.userId!,
  }
}

function statusToError(status: number): DataErrorCode {
  // 400 MISSING_CREDENTIALS + 401 AUTH_EXPIRED both resolve to "reopen from FinX".
  if (status === 400 || status === 401) return 'auth_expired'
  if (status === 404) return 'no_data'
  return 'upstream_error'
}

/** POST a data endpoint and normalize its envelope. `body` defaults to `{}`
 *  (Holdings needs no parameters; Wave B flows may pass paging etc.). */
export async function postData(
  endpoint: string,
  session: SessionContext,
  body: Record<string, unknown> = {},
): Promise<DataEnvelope> {
  if (!hasCredentials(session)) return { kind: 'error', code: 'auth_expired' }

  let res: Response
  try {
    res = await fetch(endpoint, {
      method: 'POST',
      headers: { ...authHeaders(session), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    return { kind: 'error', code: 'network' }
  }

  if (!res.ok) return { kind: 'error', code: statusToError(res.status) }

  const parsed: unknown = await res.json().catch(() => null)
  if (parsed === null || typeof parsed !== 'object') {
    return { kind: 'error', code: 'upstream_error' }
  }
  const data = parsed as Record<string, unknown>
  switch (data.kind) {
    case 'ok':
      return { kind: 'ok', body: data }
    case 'empty':
      return { kind: 'empty' }
    case 'auth_expired':
    case 'no_data':
    case 'upstream_error':
      return { kind: 'error', code: data.kind }
    default:
      return { kind: 'error', code: 'upstream_error' }
  }
}
