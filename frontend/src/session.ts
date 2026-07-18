/**
 * Session bootstrap (session-bootstrap capability).
 *
 * FinX (web + app webviews) opens this page with identity/session handoff
 * query params. We read them exactly once at boot, keep them in an
 * in-memory module context, and strip ALL query params from the address
 * bar via history.replaceState so tokens do not persist in webview
 * history or screenshots.
 *
 * `userId` arrives already decrypted (a Choice service handles that) and is
 * trusted as received — e.g. "X008593". `obStatus` is stored but MUST NOT
 * gate or alter any behavior.
 */

export interface SessionContext {
  /** Decrypted USER_ID / client code, e.g. "X008593". */
  userId: string | null
  sessionId: string | null
  /** Raw SSO JWT (8h expiry). Sent as-is in the Authorization header. */
  accessToken: string | null
  /** Host-controlled theme flag; theming itself is applied pre-paint in index.html. */
  isDarkTheme: boolean
  platform: string | null
  /** Stored only — never gates any feature. */
  obStatus: string | null
  /** Optional screen/page name the host opened us from. */
  screenName: string | null
}

let context: SessionContext | null = null

/** Screen-name param has no fixed key yet; accept the likely candidates. */
const SCREEN_NAME_KEYS = ['screenName', 'screen', 'pageName', 'page'] as const

function readParam(params: URLSearchParams, key: string): string | null {
  const value = params.get(key)
  if (value === null) return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

/**
 * Parse the handoff params once and scrub them from the URL.
 * Idempotent: repeat calls return the already-built context.
 */
export function bootstrapSession(): SessionContext {
  if (context) return context

  const params = new URLSearchParams(window.location.search)

  context = {
    userId: readParam(params, 'userId'),
    sessionId: readParam(params, 'sessionId'),
    accessToken: readParam(params, 'accessToken'),
    isDarkTheme: (readParam(params, 'isDarkTheme') ?? '').toLowerCase() === 'true',
    platform: readParam(params, 'platform'),
    obStatus: readParam(params, 'obStatus'),
    screenName: SCREEN_NAME_KEYS.reduce<string | null>(
      (found, key) => found ?? readParam(params, key),
      null,
    ),
  }

  // Strip ALL query params from the visible URL (tokens must not linger).
  if (window.location.search) {
    window.history.replaceState(null, '', window.location.pathname + window.location.hash)
  }

  return context
}

/** The in-memory session context (call bootstrapSession() first). */
export function getSessionContext(): SessionContext {
  return context ?? bootstrapSession()
}

/**
 * True only when the full credential triple is present. Everything that
 * needs credentials (greeting fetch, client code in the header) keys off
 * this; when false the app renders the degraded, non-personalized state.
 */
export function hasCredentials(ctx: SessionContext): boolean {
  return ctx.userId !== null && ctx.sessionId !== null && ctx.accessToken !== null
}
