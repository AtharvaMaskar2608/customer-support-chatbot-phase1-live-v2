/** The admin-token gate. Validates the token with a lightweight probe before
 * storing it, and shows a clear disabled / unauthorized state. */

import { useState } from 'react'
import { AuthError, listThreads } from './api'
import { ThemeToggle } from './ThemeToggle'

const TOKEN_KEY = 'traces-token'

export function TokenGate({
  initialError,
  onAuthed,
  theme,
  onToggleTheme,
}: Readonly<{
  initialError: 'unauthorized' | 'disabled' | null
  onAuthed: (token: string) => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}>) {
  const [value, setValue] = useState('')
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(
    initialError ? messageFor(initialError) : null,
  )

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const token = value.trim()
    if (!token || checking) return
    setChecking(true)
    setError(null)
    try {
      await listThreads(token, 1, 0) // probe: validates the token
      try {
        localStorage.setItem(TOKEN_KEY, token)
      } catch {
        /* localStorage unavailable — token still used for this session */
      }
      onAuthed(token)
    } catch (err) {
      if (err instanceof AuthError) {
        setError(messageFor(err.status === 404 ? 'disabled' : 'unauthorized'))
      } else {
        setError('Could not reach the server. Try again.')
      }
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-zinc-50 p-4 dark:bg-zinc-950">
      <div className="absolute top-3 right-3">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Trace Viewer
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Admin access to the agent trace store. Enter the dashboard token.
        </p>

        <input
          type="password"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Admin token"
          className="mt-4 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-800 placeholder:text-zinc-400 focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
        />

        {error && (
          <p className="mt-3 rounded-lg border border-alert/30 bg-alert/5 px-3 py-2 text-sm text-alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={checking || value.trim().length === 0}
          className="mt-4 w-full rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-50"
        >
          {checking ? 'Checking…' : 'Unlock'}
        </button>
      </form>
    </div>
  )
}

function messageFor(kind: 'unauthorized' | 'disabled'): string {
  return kind === 'disabled'
    ? 'The trace dashboard is disabled on this server (no admin token configured).'
    : 'That token was not accepted.'
}
