/** Token + FinX credential gate for the prompt playground. */

import { useState, type FormEvent } from 'react'
import { AuthError, fetchDefaults } from './api'
import type { SessionContext } from '../session'
import {
  loadStoredCreds,
  loadStoredToken,
  saveAuth,
  sessionFromCreds,
  type StoredCreds,
} from './storage'

export function Gate({
  onReady,
}: Readonly<{
  onReady: (token: string, session: SessionContext) => void
}>) {
  const [token, setToken] = useState(loadStoredToken() ?? '')
  const [userId, setUserId] = useState(loadStoredCreds()?.userId ?? '')
  const [sessionId, setSessionId] = useState(loadStoredCreds()?.sessionId ?? '')
  const [accessToken, setAccessToken] = useState(
    loadStoredCreds()?.accessToken ?? '',
  )
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const t = token.trim()
    const creds: StoredCreds = {
      userId: userId.trim(),
      sessionId: sessionId.trim(),
      accessToken: accessToken.trim(),
    }
    if (!t || !creds.userId || !creds.sessionId || !creds.accessToken || checking) {
      setError('Playground token and FinX credentials are required.')
      return
    }
    setChecking(true)
    setError(null)
    try {
      await fetchDefaults(t)
      saveAuth(t, creds)
      onReady(t, sessionFromCreds(creds))
    } catch (err) {
      if (err instanceof AuthError) {
        setError(
          err.status === 404
            ? 'Playground is disabled (PLAYGROUND_TOKEN unset on the backend).'
            : 'Invalid playground token.',
        )
      } else {
        setError('Could not reach the server. Try again.')
      }
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-zinc-50 p-4 dark:bg-zinc-950">
      <form
        onSubmit={submit}
        className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Prompt Playground
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Experiment with AskFinX prompts without touching production chat.
          Requires <code className="text-xs">PLAYGROUND_TOKEN</code> and live
          FinX credentials for tool calls.
        </p>

        <label className="mt-4 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
          Playground token
          <input
            type="password"
            autoFocus
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
        </label>

        <label className="mt-3 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
          Client ID (userId)
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
        </label>
        <label className="mt-3 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
          Session ID
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
        </label>
        <label className="mt-3 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
          Access token (SSO JWT)
          <textarea
            value={accessToken}
            onChange={(e) => setAccessToken(e.target.value)}
            rows={3}
            className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
        </label>

        {error && (
          <p className="mt-3 rounded-lg border border-red-300/40 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={checking}
          className="mt-4 w-full rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {checking ? 'Checking…' : 'Open playground'}
        </button>
      </form>
    </div>
  )
}
