import { useEffect, useSyncExternalStore } from 'react'
import { hasCredentials, type SessionContext } from './session'
import { handleAuthExpired } from './bridge'

/**
 * Personalized greeting (profile-greeting capability, frontend half).
 *
 * Pinned backend contract:
 *   GET /api/greeting
 *   Headers: Authorization: <raw SSO JWT>, X-Session-Id, X-User-Id
 *   200 -> {"firstName": "Pritam" | null,
 *           "greetingKey": "MARKET",
 *           "template": "Hi {clientRef} — markets are live. …"}
 *   400 {"error":"MISSING_CREDENTIALS"} / 401 {"error":"AUTH_EXPIRED"}
 *   502 {"error":"UPSTREAM_ERROR"}
 *
 * `greetingKey` + `template` are CHO-226: the backend picks the window off
 * the IST market clock and ships the copy with its `{clientRef}` placeholder
 * intact, so EmptyState can keep rendering the name inside its accent span.
 * Any non-200, fetch failure, or missing/partial field degrades to the
 * existing static greeting — a missing template is never a blank headline.
 *
 * The payload lives in a tiny module store rather than component state
 * because two consumers need different halves of it: App passes `firstName`
 * down the existing prop chain, while EmptyState reads the template directly.
 * One fetch, two readers, no prop-drilling of a second value through
 * ChatShell.
 */
export interface Greeting {
  firstName: string | null
  greetingKey: string | null
  template: string | null
}

let current: Greeting | null = null
let inFlight = false
let lastSession: SessionContext | null = null
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function getSnapshot(): Greeting | null {
  return current
}

function readString(body: Record<string, unknown>, key: string): string | null {
  const value = body[key]
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : null
}

async function load(session: SessionContext): Promise<void> {
  if (inFlight) return
  inFlight = true
  lastSession = session
  try {
    const res = await fetch('/api/greeting', {
      headers: {
        // Raw JWT by contract — no "Bearer " prefix.
        Authorization: session.accessToken!,
        'X-Session-Id': session.sessionId!,
        'X-User-Id': session.userId!,
      },
    })
    if (!res.ok) {
      // 401 AUTH_EXPIRED (per the pinned contract) → notify the host once; the
      // greeting itself still degrades silently to the static copy, unchanged.
      if (res.status === 401) handleAuthExpired('profile')
      return
    }
    const body: unknown = await res.json().catch(() => null)
    if (body === null || typeof body !== 'object') return
    const record = body as Record<string, unknown>
    current = {
      firstName: readString(record, 'firstName'),
      greetingKey: readString(record, 'greetingKey'),
      template: readString(record, 'template'),
    }
    emit()
  } catch {
    // Network failure -> stay on the degraded greeting.
  } finally {
    inFlight = false
  }
}

/**
 * The customer's first name, or null while unknown. Signature unchanged from
 * CHO-207 so App/ChatShell keep passing it down as before.
 */
export function useGreeting(session: SessionContext): string | null {
  const greeting = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  useEffect(() => {
    if (!hasCredentials(session)) return
    void load(session)
  }, [session])

  return greeting?.firstName ?? null
}

/**
 * The selected key + template for the entry screen (EmptyState).
 *
 * Returns null until the fetch lands, and null forever if it fails — the
 * caller renders the static greeting in that case. Remounting recomputes
 * (design D6: Restart bumps the shell key, which remounts EmptyState, and a
 * customer looking at a visibly reset screen should not see a stale
 * greeting). The first mount rides along on the fetch `useGreeting` already
 * started, so this costs no extra request at boot.
 */
export function useEntryGreeting(): Greeting | null {
  const greeting = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  useEffect(() => {
    if (current !== null && lastSession !== null) void load(lastSession)
    // Mount-only: the greeting is static once painted and must not swap when
    // a window boundary passes while the screen is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return greeting
}
