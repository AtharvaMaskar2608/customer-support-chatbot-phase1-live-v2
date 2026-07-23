/**
 * Trace viewer dashboard (CHO-262) — admin-gated read UI over the agent_traces
 * store. Isolated third Vite entry (traces.html): its own React root, no shared
 * state with the chat app or the widget.
 */

import { useCallback, useState } from 'react'
import { AuthError } from './api'
import type { TraceFilters } from './api'
import { FilterBar } from './FilterBar'
import { ThemeToggle } from './ThemeToggle'
import { ThreadDetail } from './ThreadDetail'
import { ThreadList } from './ThreadList'
import { TokenGate } from './TokenGate'
import { TraceDetail } from './TraceDetail'
import { TraceList } from './TraceList'
import { useTheme } from './useTheme'

const TOKEN_KEY = 'traces-token'
type View = 'traces' | 'threads'
type Selection =
  | { kind: 'trace'; id: number }
  | { kind: 'thread'; id: string }
  | null

export function TracesApp() {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  )
  const [authError, setAuthError] = useState<'unauthorized' | 'disabled' | null>(
    null,
  )
  const [view, setView] = useState<View>('traces')
  const [filters, setFilters] = useState<TraceFilters>({})
  const [selection, setSelection] = useState<Selection>(null)
  const { theme, toggle } = useTheme()

  // A 401/404 mid-session (e.g. token rotated) drops back to the gate.
  const handleError = useCallback((e: unknown) => {
    if (e instanceof AuthError) {
      setAuthError(e.status === 404 ? 'disabled' : 'unauthorized')
      setToken(null)
      setSelection(null)
      try {
        localStorage.removeItem(TOKEN_KEY)
      } catch {
        /* ignore */
      }
    }
  }, [])

  const signOut = useCallback(() => {
    setToken(null)
    setAuthError(null)
    setSelection(null)
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  }, [])

  const openThread = useCallback((id: string) => {
    setView('threads')
    setSelection({ kind: 'thread', id })
  }, [])

  const openTrace = useCallback((id: number) => {
    setView('traces')
    setSelection({ kind: 'trace', id })
  }, [])

  if (token === null) {
    return (
      <TokenGate
        initialError={authError}
        onAuthed={(t) => {
          setAuthError(null)
          setToken(t)
        }}
        theme={theme}
        onToggleTheme={toggle}
      />
    )
  }

  return (
    <div className="min-h-dvh bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/90 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/90">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3">
          <h1 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
            Trace Viewer
          </h1>
          <nav className="flex gap-1 rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-800">
            {(['traces', 'threads'] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => {
                  setView(v)
                  setSelection(null)
                }}
                className={`rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors ${
                  view === v
                    ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-50'
                    : 'text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200'
                }`}
              >
                {v}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle theme={theme} onToggle={toggle} />
            <button
              type="button"
              onClick={signOut}
              className="rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Lock
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-5">
        {view === 'traces' && (
          <div className="space-y-4">
            <FilterBar
              value={filters}
              onChange={(f) => {
                setFilters(f)
                setSelection(null)
              }}
            />
            <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
              <TraceList
                token={token}
                filters={filters}
                selectedId={selection?.kind === 'trace' ? selection.id : null}
                onSelect={(id) => setSelection({ kind: 'trace', id })}
                onError={handleError}
              />
              <div className="min-w-0">
                {selection?.kind === 'trace' ? (
                  <TraceDetail
                    token={token}
                    id={selection.id}
                    onError={handleError}
                    onOpenThread={openThread}
                  />
                ) : (
                  <Placeholder text="Select a trace to inspect its span tree." />
                )}
              </div>
            </div>
          </div>
        )}

        {view === 'threads' && (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
            <ThreadList
              token={token}
              selectedId={selection?.kind === 'thread' ? selection.id : null}
              onSelect={(id) => setSelection({ kind: 'thread', id })}
              onError={handleError}
            />
            <div className="min-w-0">
              {selection?.kind === 'thread' ? (
                <ThreadDetail
                  token={token}
                  threadId={selection.id}
                  onError={handleError}
                  onOpenTrace={openTrace}
                />
              ) : (
                <Placeholder text="Select a thread to see its turns and token trend." />
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

function Placeholder({ text }: Readonly<{ text: string }>) {
  return (
    <div className="grid h-full min-h-40 place-items-center rounded-xl border border-dashed border-zinc-200 p-8 text-center text-sm text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
      {text}
    </div>
  )
}
