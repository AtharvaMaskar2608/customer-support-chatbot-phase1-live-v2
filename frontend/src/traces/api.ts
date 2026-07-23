/**
 * Trace viewer API client (CHO-262).
 *
 * Read-only calls to the admin-gated backend router. The admin token rides in
 * the `X-Traces-Token` header on every request; a 401 (bad token) or 404
 * (dashboard disabled / token unset) surfaces as an {@link AuthError} so the UI
 * can drop back to the token gate. The token is never put in the URL.
 */

export type TraceListItem = {
  id: number
  created_at: string
  thread_id: string | null
  user_id: string | null
  model: string | null
  input_tokens: number | null
  output_tokens: number | null
  tools: string[]
  had_error: boolean | null
  latency_ms: number | null
  input: string | null
  output: string | null
}

export type Span = {
  id: string
  parent_id: string | null
  type: string // agent | llm | tool | retriever
  name: string
  offset_ms: number | null
  duration_ms: number | null
  input: unknown
  output: unknown
  metadata: Record<string, unknown>
}

export type TraceDetail = TraceListItem & { spans: Span[] }

export type Thread = {
  thread_id: string
  turns: number
  last_at: string
  total_input_tokens: number
  had_error: boolean
}

export type TraceFilters = {
  thread_id?: string
  model?: string
  had_error?: boolean
  tool?: string
  since?: string
  until?: string
}

/** Raised on 401 (bad token) or 404 (dashboard disabled) — the UI re-gates. */
export class AuthError extends Error {
  status: number
  constructor(status: number) {
    super(status === 404 ? 'disabled' : 'unauthorized')
    this.status = status
  }
}

type Params = Record<string, string | number | boolean | undefined>

async function request<T>(path: string, token: string, params?: Params): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== '') url.searchParams.set(key, String(value))
    }
  }
  const res = await fetch(url.toString(), {
    headers: { 'X-Traces-Token': token },
  })
  if (res.status === 401 || res.status === 404) throw new AuthError(res.status)
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return (await res.json()) as T
}

export function listTraces(
  token: string,
  filters: TraceFilters,
  limit: number,
  offset: number,
): Promise<{ traces: TraceListItem[]; total: number }> {
  return request('/api/traces', token, { ...filters, limit, offset })
}

export function getTrace(token: string, id: number): Promise<TraceDetail> {
  return request(`/api/traces/${id}`, token)
}

export function listThreads(
  token: string,
  limit: number,
  offset: number,
): Promise<{ threads: Thread[]; total: number }> {
  return request('/api/threads', token, { limit, offset })
}

export function getThread(
  token: string,
  threadId: string,
): Promise<{ traces: TraceDetail[] }> {
  return request(`/api/threads/${encodeURIComponent(threadId)}`, token)
}
