/** localStorage helpers for the prompt playground (CHO-272). */

import type { SessionContext } from '../session'

const TOKEN_KEY = 'playground-token'
const CREDS_KEY = 'playground-creds'

export type StoredCreds = {
  userId: string
  sessionId: string
  accessToken: string
}

export function loadStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function loadStoredCreds(): StoredCreds | null {
  try {
    const raw = localStorage.getItem(CREDS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredCreds
    if (parsed?.userId && parsed?.sessionId && parsed?.accessToken) return parsed
  } catch {
    /* ignore */
  }
  return null
}

export function saveAuth(token: string, creds: StoredCreds) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(CREDS_KEY, JSON.stringify(creds))
  } catch {
    /* ignore */
  }
}

export function clearStoredToken() {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore */
  }
}

export function sessionFromCreds(creds: StoredCreds): SessionContext {
  return {
    userId: creds.userId,
    sessionId: creds.sessionId,
    accessToken: creds.accessToken,
    isDarkTheme: false,
    platform: null,
    obStatus: null,
    screenName: null,
  }
}
