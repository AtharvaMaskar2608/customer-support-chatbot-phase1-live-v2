/** Prompt playground shell (CHO-272): editable prompts + live agent chat. */

import { useEffect, useRef, useState } from 'react'
import type { SessionContext } from '../session'
import {
  fetchDefaults,
  resetPlaygroundChat,
  streamPlaygroundChat,
} from './api'
import { Gate } from './Gate'
import {
  clearStoredToken,
  loadStoredCreds,
  loadStoredToken,
  sessionFromCreds,
} from './storage'

const DRAFT_KEY = 'playground-draft-v1'

type ChatLine =
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string }
  | { role: 'meta'; text: string }

type Draft = {
  systemPrompt: string
  primedInstructions: string
}

function loadDraft(): Draft | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Draft
    if (typeof parsed?.systemPrompt === 'string' && typeof parsed?.primedInstructions === 'string') {
      return parsed
    }
  } catch {
    /* ignore */
  }
  return null
}

function saveDraft(draft: Draft) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  } catch {
    /* ignore */
  }
}

function Workspace({
  token,
  session,
  onSignOut,
}: Readonly<{
  token: string
  session: SessionContext
  onSignOut: () => void
}>) {
  const [systemPrompt, setSystemPrompt] = useState('')
  const [primedInstructions, setPrimedInstructions] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [tab, setTab] = useState<'system' | 'primed'>('system')
  const [input, setInput] = useState('')
  const [lines, setLines] = useState<ChatLine[]>([])
  const [busy, setBusy] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const draft = loadDraft()
      if (draft) {
        if (!cancelled) {
          setSystemPrompt(draft.systemPrompt)
          setPrimedInstructions(draft.primedInstructions)
          setLoaded(true)
        }
        return
      }
      try {
        const defaults = await fetchDefaults(token)
        if (!cancelled) {
          setSystemPrompt(defaults.systemPrompt)
          setPrimedInstructions(defaults.primedInstructions)
          setLoaded(true)
        }
      } catch {
        if (!cancelled) setLoaded(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    if (!loaded) return
    saveDraft({ systemPrompt, primedInstructions })
  }, [systemPrompt, primedInstructions, loaded])

  useEffect(() => {
    scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight })
  }, [lines, busy])

  async function reloadDefaults() {
    const defaults = await fetchDefaults(token)
    setSystemPrompt(defaults.systemPrompt)
    setPrimedInstructions(defaults.primedInstructions)
  }

  async function resetThread() {
    abortRef.current?.abort()
    await resetPlaygroundChat(token, session)
    setLines([])
  }

  async function send() {
    const message = input.trim()
    if (!message || busy) return
    setInput('')
    setLines((prev) => [...prev, { role: 'user', text: message }])
    setBusy(true)
    const ac = new AbortController()
    abortRef.current = ac
    let assistant = ''
    setLines((prev) => [...prev, { role: 'assistant', text: '' }])

    await streamPlaygroundChat(
      message,
      session,
      token,
      { systemPrompt, primedInstructions },
      {
        onText(delta) {
          assistant += delta
          const snapshot = assistant
          setLines((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last?.role === 'assistant') {
              next[next.length - 1] = { role: 'assistant', text: snapshot }
            }
            return next
          })
        },
        onTool(ev) {
          const label =
            ev.status === 'started'
              ? `tool ${ev.name}…`
              : `tool ${ev.name}${ev.is_error ? ' (error)' : ''} ✓`
          setLines((prev) => [...prev, { role: 'meta', text: label }])
        },
        onArtifact(art) {
          const kind =
            art && typeof art === 'object' && 'kind' in art
              ? String((art as { kind: string }).kind)
              : 'artifact'
          setLines((prev) => [
            ...prev,
            { role: 'meta', text: `artifact: ${kind}` },
          ])
        },
        onDone() {
          setBusy(false)
        },
        onError(code) {
          setLines((prev) => [
            ...prev,
            { role: 'meta', text: `error: ${code}` },
          ])
          setBusy(false)
        },
      },
      ac.signal,
    )
    setBusy(false)
  }

  return (
    <div className="flex h-dvh flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div>
          <h1 className="text-sm font-semibold">AskFinX Prompt Playground</h1>
          <p className="text-xs text-zinc-500">
            Client {session.userId} · drafts stay in this browser only
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void reloadDefaults()}
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs dark:border-zinc-700"
          >
            Reset to production prompts
          </button>
          <button
            type="button"
            onClick={() => void resetThread()}
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs dark:border-zinc-700"
          >
            New chat
          </button>
          <button
            type="button"
            onClick={onSignOut}
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs dark:border-zinc-700"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-2">
        <section className="flex min-h-0 flex-col border-b border-zinc-200 lg:border-r lg:border-b-0 dark:border-zinc-800">
          <div className="flex gap-1 border-b border-zinc-200 p-2 dark:border-zinc-800">
            <button
              type="button"
              onClick={() => setTab('system')}
              className={`rounded-md px-3 py-1.5 text-xs ${
                tab === 'system'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                  : 'text-zinc-600 dark:text-zinc-400'
              }`}
            >
              System prompt
            </button>
            <button
              type="button"
              onClick={() => setTab('primed')}
              className={`rounded-md px-3 py-1.5 text-xs ${
                tab === 'primed'
                  ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                  : 'text-zinc-600 dark:text-zinc-400'
              }`}
            >
              Primed instructions
            </button>
          </div>
          <textarea
            value={tab === 'system' ? systemPrompt : primedInstructions}
            onChange={(e) =>
              tab === 'system'
                ? setSystemPrompt(e.target.value)
                : setPrimedInstructions(e.target.value)
            }
            spellCheck={false}
            className="min-h-0 flex-1 resize-none bg-transparent p-3 font-mono text-xs leading-5 outline-none"
          />
        </section>

        <section className="flex min-h-0 flex-col">
          <div ref={scrollerRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
            {lines.length === 0 && (
              <p className="text-sm text-zinc-500">
                Edit prompts on the left, then chat here. Same tools as
                production; session is namespaced so it won&apos;t touch live
                threads.
              </p>
            )}
            {lines.map((line, i) => (
              <div
                key={`${i}-${line.role}`}
                className={
                  line.role === 'user'
                    ? 'ml-8 rounded-2xl bg-zinc-900 px-3 py-2 text-sm text-white dark:bg-zinc-100 dark:text-zinc-900'
                    : line.role === 'meta'
                      ? 'text-xs text-zinc-500'
                      : 'mr-8 whitespace-pre-wrap rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-900'
                }
              >
                {line.text || (busy && line.role === 'assistant' ? '…' : '')}
              </div>
            ))}
          </div>
          <form
            className="flex gap-2 border-t border-zinc-200 p-3 dark:border-zinc-800"
            onSubmit={(e) => {
              e.preventDefault()
              void send()
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Message the experimental agent…"
              disabled={busy}
              className="min-w-0 flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
            >
              Send
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}

export function PlaygroundApp() {
  const [auth, setAuth] = useState<{
    token: string
    session: SessionContext
  } | null>(() => {
    const token = loadStoredToken()
    const creds = loadStoredCreds()
    if (token && creds) return { token, session: sessionFromCreds(creds) }
    return null
  })

  if (!auth) {
    return (
      <Gate
        onReady={(token, session) => setAuth({ token, session })}
      />
    )
  }

  return (
    <Workspace
      token={auth.token}
      session={auth.session}
      onSignOut={() => {
        clearStoredToken()
        setAuth(null)
      }}
    />
  )
}
