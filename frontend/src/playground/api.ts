/** Prompt playground API client (CHO-272). */

import {
  authHeaders,
  type AgentStreamHandlers,
  type AgentErrorCode,
} from '../chat/agent'
import { hasCredentials, type SessionContext } from '../session'

export class AuthError extends Error {
  status: number
  constructor(status: number) {
    super(`playground auth ${status}`)
    this.status = status
  }
}

const TOKEN_HEADER = 'X-Playground-Token'

export async function fetchDefaults(token: string): Promise<{
  systemPrompt: string
  primedInstructions: string
}> {
  const res = await fetch('/api/playground/defaults', {
    headers: { [TOKEN_HEADER]: token },
  })
  if (res.status === 404 || res.status === 401) throw new AuthError(res.status)
  if (!res.ok) throw new Error(`defaults ${res.status}`)
  return (await res.json()) as {
    systemPrompt: string
    primedInstructions: string
  }
}

export async function resetPlaygroundChat(
  token: string,
  session: SessionContext,
): Promise<void> {
  if (!hasCredentials(session)) return
  await fetch('/api/playground/chat/reset', {
    method: 'POST',
    headers: { ...authHeaders(session), [TOKEN_HEADER]: token },
  })
}

/**
 * Same SSE contract as /api/chat, posted to /api/playground/chat with the
 * editable prompt fields. Reuses the production frame parser via a thin fork.
 */
export async function streamPlaygroundChat(
  message: string,
  session: SessionContext,
  token: string,
  prompts: { systemPrompt: string; primedInstructions: string },
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  if (!hasCredentials(session)) {
    handlers.onError('AGENT_UNAVAILABLE')
    return
  }

  let res: Response
  try {
    res = await fetch('/api/playground/chat', {
      method: 'POST',
      headers: {
        ...authHeaders(session),
        [TOKEN_HEADER]: token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        systemPrompt: prompts.systemPrompt,
        primedInstructions: prompts.primedInstructions,
      }),
      signal,
    })
  } catch {
    if (!signal?.aborted) handlers.onError('AGENT_UNAVAILABLE')
    return
  }

  if (res.status === 401 || res.status === 404) {
    if (!signal?.aborted) handlers.onError('AGENT_UNAVAILABLE')
    return
  }

  const contentType = res.headers.get('content-type') ?? ''
  if (!res.ok || !contentType.includes('text/event-stream') || res.body === null) {
    const body: unknown = await res.json().catch(() => null)
    const code =
      body &&
      typeof body === 'object' &&
      'error' in body &&
      typeof (body as { error: unknown }).error === 'string'
        ? ((body as { error: string }).error as AgentErrorCode)
        : 'AGENT_UNAVAILABLE'
    if (!signal?.aborted) handlers.onError(code)
    return
  }

  // Inline SSE pump (mirrors agent.ts — kept local so playground stays
  // independent of private helpers).
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = ''
  let dataLines: string[] = []
  let sawTerminal = false

  const dispatch = (): boolean => {
    if (eventName === '' && dataLines.length === 0) return false
    const dataRaw = dataLines.join('\n')
    eventName = eventName || 'message'
    const ev = eventName
    eventName = ''
    dataLines = []
    let data: unknown = null
    try {
      data = JSON.parse(dataRaw) as unknown
    } catch {
      return false
    }
    const rec = data && typeof data === 'object' ? (data as Record<string, unknown>) : null
    switch (ev) {
      case 'text': {
        if (typeof rec?.delta === 'string' && rec.delta !== '') handlers.onText(rec.delta)
        return false
      }
      case 'tool': {
        if (
          typeof rec?.name === 'string' &&
          (rec.status === 'started' || rec.status === 'finished')
        ) {
          handlers.onTool({
            name: rec.name,
            status: rec.status,
            is_error: Boolean(rec.is_error),
          })
        }
        return false
      }
      case 'artifact': {
        if (rec && typeof rec.kind === 'string') {
          handlers.onArtifact(rec as never)
        }
        return false
      }
      case 'done': {
        sawTerminal = true
        const thread =
          rec?.thread && typeof rec.thread === 'object'
            ? (rec.thread as Record<string, unknown>)
            : {}
        const num = (v: unknown) =>
          typeof v === 'number' && Number.isFinite(v) ? v : 0
        handlers.onDone({
          thread: {
            taskTurns: num(thread.taskTurns),
            sessionTurns: num(thread.sessionTurns),
            lastSeq: num(thread.lastSeq),
          },
        })
        return true
      }
      case 'error': {
        sawTerminal = true
        const code =
          typeof rec?.error === 'string'
            ? (rec.error as AgentErrorCode)
            : 'AGENT_UNAVAILABLE'
        handlers.onError(code)
        return true
      }
      default:
        return false
    }
  }

  const handleLine = (raw: string): boolean => {
    const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw
    if (line === '') return dispatch()
    if (line.startsWith(':')) return false
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') eventName = value
    else if (field === 'data') dataLines.push(value)
    return false
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let nl = buffer.indexOf('\n')
      while (nl !== -1) {
        const line = buffer.slice(0, nl)
        buffer = buffer.slice(nl + 1)
        if (handleLine(line)) return
        nl = buffer.indexOf('\n')
      }
    }
    buffer += decoder.decode()
    if (buffer !== '' && handleLine(buffer)) return
    dispatch()
    if (!sawTerminal && !signal?.aborted) handlers.onError('AGENT_UNAVAILABLE')
  } finally {
    void reader.cancel().catch(() => {})
  }
}
