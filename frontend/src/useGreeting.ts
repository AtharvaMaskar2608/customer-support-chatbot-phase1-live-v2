import { useEffect, useState } from 'react'
import { hasCredentials, type SessionContext } from './session'

/**
 * Personalized greeting (profile-greeting capability, frontend half).
 *
 * Pinned backend contract:
 *   GET /api/greeting
 *   Headers: Authorization: <raw SSO JWT>, X-Session-Id, X-User-Id
 *   200 -> {"firstName": "Pritam"} | {"firstName": null}
 *   400 {"error":"MISSING_CREDENTIALS"} / 401 {"error":"AUTH_EXPIRED"}
 *   502 {"error":"UPSTREAM_ERROR"}
 *
 * Any non-200, null/absent firstName, or fetch failure degrades to the
 * generic greeting (hook returns null). The call is skipped entirely when
 * the session credentials are incomplete.
 */
export function useGreeting(session: SessionContext): string | null {
  const [firstName, setFirstName] = useState<string | null>(null)

  useEffect(() => {
    if (!hasCredentials(session)) return

    const controller = new AbortController()

    fetch('/api/greeting', {
      headers: {
        // Raw JWT by contract — no "Bearer " prefix.
        Authorization: session.accessToken!,
        'X-Session-Id': session.sessionId!,
        'X-User-Id': session.userId!,
      },
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) return null
        const body: unknown = await res.json().catch(() => null)
        const name =
          body !== null && typeof body === 'object'
            ? (body as { firstName?: unknown }).firstName
            : null
        return typeof name === 'string' && name.trim() !== '' ? name.trim() : null
      })
      .then((name) => {
        if (name !== null && !controller.signal.aborted) setFirstName(name)
      })
      .catch(() => {
        // Network failure -> stay on the degraded greeting.
      })

    return () => controller.abort()
  }, [session])

  return firstName
}
