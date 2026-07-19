/**
 * Agent chat transport (agent-loop, frontend half — CHO-213 task 5.1).
 *
 * Pinned SSE contract for POST /api/chat (the Wave-B backend must match):
 *
 *   POST /api/chat
 *     Headers: Authorization <raw SSO JWT>, X-Session-Id, X-User-Id,
 *              Content-Type: application/json
 *     Body:    {"message": "<user text>"}
 *     200 → text/event-stream with events (data is one JSON object each):
 *       event: text      {"delta": "..."}                     — assistant text as it generates
 *       event: tool      {"name": "...", "status": "started"|"finished",
 *                         "is_error": bool}                   — tool-round activity
 *       event: artifact  {"kind": "file", "file": {name,sizeLabel,format,
 *                         passwordProtected}, "fileToken": "...",
 *                         "flowKey"?: "pnl"|"ledger"|"tax"|"contract-notes"}
 *                        {"kind": "data", "tool": "get_holdings"|"get_money"|
 *                         "get_brokerage", ...ok-payload fields spread here}
 *       event: done      {"thread": {"taskTurns": n, "sessionTurns": n}}  — terminal
 *       event: error     {"error": "AGENT_UNAVAILABLE"|"AUTH_EXPIRED"}    — terminal
 *
 *   Pre-stream failures — HTTP 400 {"error":"MISSING_CREDENTIALS"} or any
 *   non-200 / non-SSE response — fold into AGENT_UNAVAILABLE (the shell's
 *   keyword-routing fallback), except an explicit AUTH_EXPIRED body, which
 *   passes through so the session-expired copy shows.
 *
 * EventSource cannot POST, so this is fetch + ReadableStream + TextDecoder
 * with a hand-rolled SSE parser: `event:`/`data:` field lines, blank-line
 * dispatch, multi-line data joined with \n, `:` keep-alive comments ignored,
 * CRLF tolerated, frames split across network chunks reassembled. Exactly one
 * terminal callback (onDone or onError) fires per stream — unless the caller
 * aborts, after which no callbacks fire at all.
 */

import { hasCredentials, type SessionContext } from '../session'
import { isFileInfo, type FileInfo } from '../flow/api'

/* ── event payload types (the shapes Wave B emits) ────────────────────── */

export interface AgentToolEvent {
  /** Registry tool name, e.g. "get_holdings" — mapped to friendly copy, never shown raw. */
  name: string
  status: 'started' | 'finished'
  is_error: boolean
}

/** A produced report file — same shape as the report flows' download payload,
 *  so the existing FileCard + /api/report/file/{token} mechanics apply as-is. */
export interface AgentFileArtifact {
  kind: 'file'
  file: FileInfo
  fileToken: string
  /** Optional producing-flow hint ("pnl"|"ledger"|"tax"|"contract-notes") —
   *  lets the card reuse that flow's password note and help copy. */
  flowKey?: string
}

/** A data answer — the /api/data/* endpoint's normalized `ok` payload fields
 *  spread beside `tool` (the envelope's own kind:"ok" is implied: only
 *  successful tool calls emit artifacts). */
export interface AgentDataArtifact {
  kind: 'data'
  /** Producing tool, e.g. "get_holdings" — maps to the data-card renderer. */
  tool: string
  [field: string]: unknown
}

/** A form handover (CHO-214) — boots the matching guided flow inline,
 *  pre-filled with the validated seed. The seed is re-validated against the
 *  flow descriptor before any value reaches a widget. */
export interface AgentFlowArtifact {
  kind: 'flow'
  /** Report-flow key: "pnl" | "ledger" | "tax" | "contract-notes". */
  flowKey: string
  /** Slot values the user stated, e.g. {segment, fromDate, toDate, delivery}. */
  seed: Record<string, unknown>
}

export type AgentArtifact = AgentFileArtifact | AgentDataArtifact | AgentFlowArtifact

export interface AgentDoneEvent {
  thread: { taskTurns: number; sessionTurns: number }
}

export type AgentErrorCode = 'AGENT_UNAVAILABLE' | 'AUTH_EXPIRED'

export interface AgentStreamHandlers {
  onText: (delta: string) => void
  onTool: (ev: AgentToolEvent) => void
  onArtifact: (artifact: AgentArtifact) => void
  onDone: (ev: AgentDoneEvent) => void
  onError: (code: AgentErrorCode) => void
}

/* ── payload validation (malformed frames are dropped, never rendered) ── */

function asRecord(x: unknown): Record<string, unknown> | null {
  return x !== null && typeof x === 'object' ? (x as Record<string, unknown>) : null
}

function parseArtifact(x: unknown): AgentArtifact | null {
  const a = asRecord(x)
  if (a === null) return null
  if (a.kind === 'file' && isFileInfo(a.file) && typeof a.fileToken === 'string') {
    return {
      kind: 'file',
      file: a.file,
      fileToken: a.fileToken,
      flowKey: typeof a.flowKey === 'string' ? a.flowKey : undefined,
    }
  }
  if (a.kind === 'data' && typeof a.tool === 'string') {
    return { ...a, kind: 'data', tool: a.tool }
  }
  if (a.kind === 'flow' && typeof a.flowKey === 'string') {
    const seed = asRecord(a.seed) ?? {}
    return { kind: 'flow', flowKey: a.flowKey, seed }
  }
  return null
}

function parseDone(x: unknown): AgentDoneEvent {
  const thread = asRecord(asRecord(x)?.thread) ?? {}
  const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : 0)
  return { thread: { taskTurns: num(thread.taskTurns), sessionTurns: num(thread.sessionTurns) } }
}

function parseErrorCode(x: unknown): AgentErrorCode {
  return asRecord(x)?.error === 'AUTH_EXPIRED' ? 'AUTH_EXPIRED' : 'AGENT_UNAVAILABLE'
}

/* ── SSE line parser ──────────────────────────────────────────────────── */

interface SseFrame {
  event: string
  data: string
}

/**
 * Read an SSE body, invoking `onFrame` per complete frame. `onFrame` returns
 * true for terminal frames — reading stops and the connection is released.
 * Resolves true iff a terminal frame was seen.
 */
async function readSse(
  body: ReadableStream<Uint8Array>,
  onFrame: (frame: SseFrame) => boolean,
): Promise<boolean> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = ''
  let dataLines: string[] = []

  // Blank line ends a frame; frames without data (pure keep-alives) no-op.
  const dispatch = (): boolean => {
    if (eventName === '' && dataLines.length === 0) return false
    const frame: SseFrame = { event: eventName, data: dataLines.join('\n') }
    eventName = ''
    dataLines = []
    return onFrame(frame)
  }

  const handleLine = (raw: string): boolean => {
    const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw
    if (line === '') return dispatch()
    if (line.startsWith(':')) return false // keep-alive comment
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') eventName = value
    else if (field === 'data') dataLines.push(value)
    // id / retry fields are irrelevant here and ignored.
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
        if (handleLine(line)) return true
        nl = buffer.indexOf('\n')
      }
    }
    // Stream closed: flush any trailing line + half-open frame.
    buffer += decoder.decode()
    if (buffer !== '' && handleLine(buffer)) return true
    return dispatch()
  } finally {
    // Terminal frame mid-stream → drop the rest of the connection.
    void reader.cancel().catch(() => {})
  }
}

/* ── the client ───────────────────────────────────────────────────────── */

/** Same credential triple as the report/data fetches. Raw JWT — no "Bearer". */
export function authHeaders(session: SessionContext): Record<string, string> {
  return {
    Authorization: session.accessToken!,
    'X-Session-Id': session.sessionId!,
    'X-User-Id': session.userId!,
  }
}

/**
 * POST the message to /api/chat and pump the SSE response into `handlers`.
 * Resolves when the stream ends (or errors); an aborted `signal` resolves
 * silently with no further callbacks.
 */
export async function streamAgentChat(
  message: string,
  session: SessionContext,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  // No credential triple → the backend would 400 MISSING_CREDENTIALS anyway;
  // degrade straight to the keyword-routing fallback.
  if (!hasCredentials(session)) {
    handlers.onError('AGENT_UNAVAILABLE')
    return
  }

  let res: Response
  try {
    res = await fetch('/api/chat', {
      method: 'POST',
      headers: { ...authHeaders(session), 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
      signal,
    })
  } catch {
    if (!signal?.aborted) handlers.onError('AGENT_UNAVAILABLE')
    return
  }

  const contentType = res.headers.get('content-type') ?? ''
  if (!res.ok || !contentType.includes('text/event-stream') || res.body === null) {
    // Pre-stream failure (400 MISSING_CREDENTIALS, 5xx, non-SSE body…).
    const body: unknown = await res.json().catch(() => null)
    if (!signal?.aborted) handlers.onError(parseErrorCode(body))
    return
  }

  let sawTerminal = false
  const handleFrame = (frame: SseFrame): boolean => {
    let data: unknown = null
    try {
      data = JSON.parse(frame.data) as unknown
    } catch {
      return false // malformed frame — skip, never render
    }
    switch (frame.event) {
      case 'text': {
        const delta = asRecord(data)?.delta
        if (typeof delta === 'string' && delta !== '') handlers.onText(delta)
        return false
      }
      case 'tool': {
        const t = asRecord(data)
        if (t !== null && typeof t.name === 'string' && (t.status === 'started' || t.status === 'finished')) {
          handlers.onTool({ name: t.name, status: t.status, is_error: t.is_error === true })
        }
        return false
      }
      case 'artifact': {
        const artifact = parseArtifact(data)
        if (artifact !== null) handlers.onArtifact(artifact)
        return false
      }
      case 'done': {
        sawTerminal = true
        handlers.onDone(parseDone(data))
        return true
      }
      case 'error': {
        sawTerminal = true
        handlers.onError(parseErrorCode(data))
        return true
      }
      default:
        return false // unknown event — forward-compatible skip
    }
  }

  try {
    await readSse(res.body, handleFrame)
  } catch {
    if (!signal?.aborted && !sawTerminal) handlers.onError('AGENT_UNAVAILABLE')
    return
  }
  // Stream ended without a terminal event → treat as an agent drop.
  if (!signal?.aborted && !sawTerminal) handlers.onError('AGENT_UNAVAILABLE')
}
