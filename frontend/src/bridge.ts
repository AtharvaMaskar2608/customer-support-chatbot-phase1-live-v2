/**
 * WebView file-delivery bridge (CHO-230).
 *
 * When the chat page runs inside the native Android host, generated files are
 * handed to the host instead of triggering a browser download. The host injects
 * a `window.Android.postMessage(string)` channel; we post a versioned
 * `file.ready` envelope and let native own the save. Every caller keeps its
 * existing browser download as the web fallback — `sendFileToHost` /
 * `sendInlineFileToHost` return false when no bridge is present, and the caller
 * then falls back.
 *
 * The reverse channel (`window.JiniBridge.onNativeEvent`) lets the host report
 * `file.downloaded` / `file.expired` back to the page, keyed by the correlation
 * id minted on the outbound envelope. Parsing is defensive: unknown or
 * malformed input is ignored, never thrown.
 */

import type { FileInfo } from './flow/api'

/** The injected native channel — present only inside the Android WebView. */
interface AndroidBridge {
  postMessage: (message: string) => void
}

/** Where a delivered file originated (for the host's own bookkeeping). */
export type FileSource = 'report' | 'contract-note' | 'holdings-csv'

/**
 * The native host, when present, exposes `window.Android.postMessage`. Returns
 * the bridge only when that channel is actually callable; otherwise null (the
 * plain browser, where callers keep their web-download fallback).
 */
export function androidBridge(): AndroidBridge | null {
  const android = (window as unknown as { Android?: Partial<AndroidBridge> }).Android
  return typeof android?.postMessage === 'function' ? (android as AndroidBridge) : null
}

let _seq = 0

/**
 * A unique-enough id for correlating an outbound envelope with the host's
 * reply. Prefers `crypto.randomUUID()`; falls back to time + a local counter
 * on hosts without it.
 */
export function correlationId(prefix: string): string {
  const unique =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${(_seq += 1).toString(36)}`
  return `${prefix}_${unique}`
}

/**
 * Hand a token-backed file (report / contract note) to the native host as a URL
 * the host fetches from our own token endpoint. Returns true once posted to the
 * bridge, false when there is no bridge (the caller then does the web download).
 */
export function sendFileToHost(
  fileToken: string,
  file: FileInfo,
  extras?: { ttlSeconds?: number | null; expiresAt?: string | null; source?: FileSource },
): boolean {
  const bridge = androidBridge()
  if (bridge === null) return false
  const payload = {
    type: 'file.ready',
    v: 1,
    id: correlationId('f'),
    ts: new Date().toISOString(),
    payload: {
      transport: 'url',
      url: `${window.location.origin}/api/report/file/${encodeURIComponent(fileToken)}`,
      filename: file.name,
      mimeType: file.format === 'PDF' ? 'application/pdf' : 'application/octet-stream',
      format: file.format,
      sizeLabel: file.sizeLabel,
      passwordProtected: file.passwordProtected,
      auth: 'none',
      ttlSeconds: extras?.ttlSeconds ?? null,
      tokenExpiresAt: extras?.expiresAt ?? null,
      source: extras?.source ?? 'report',
    },
  }
  bridge.postMessage(JSON.stringify(payload))
  return true
}

/**
 * Hand an in-memory file (built client-side, e.g. the holdings CSV) to the
 * native host as base64. Returns false when there is no bridge (the caller then
 * does the web download).
 */
export function sendInlineFileToHost(
  filename: string,
  text: string,
  mimeType = 'text/csv',
): boolean {
  const bridge = androidBridge()
  if (bridge === null) return false
  const payload = {
    type: 'file.ready',
    v: 1,
    id: correlationId('f'),
    ts: new Date().toISOString(),
    payload: {
      transport: 'inline',
      filename,
      mimeType,
      format: 'CSV',
      passwordProtected: false,
      auth: 'none',
      // btoa needs Latin-1; UTF-8 → percent-escape → Latin-1 round-trips safely.
      contentBase64: btoa(unescape(encodeURIComponent(text))),
      source: 'holdings-csv',
    },
  }
  bridge.postMessage(JSON.stringify(payload))
  return true
}

/* ── session expiry: one host signal per expiry (CHO-231) ───────────────── */

/** Which sink first observed the FinX session expiry (host bookkeeping only). */
export type SessionExpiredTrigger = 'profile' | 'agent' | 'report' | 'data'

/**
 * Tell the native host the FinX session has expired. Posts a versioned
 * `session.expired` envelope (same shape as `file.ready`) via the Android
 * bridge. Returns true once posted, false when there is no bridge — the plain
 * browser, where the page keeps showing its own session-expired copy.
 */
export function sendSessionExpiredToHost(trigger: SessionExpiredTrigger): boolean {
  const bridge = androidBridge()
  if (bridge === null) return false
  const payload = {
    type: 'session.expired',
    v: 1,
    id: correlationId('s'),
    ts: new Date().toISOString(),
    payload: { trigger },
  }
  bridge.postMessage(JSON.stringify(payload))
  return true
}

let sessionExpiredFired = false

/**
 * The single funnel every AUTH_EXPIRED sink calls. Fires the `session.expired`
 * host signal AT MOST ONCE per expiry (module-level latch) — the first sink to
 * observe the expiry posts it; later sinks are no-ops. It changes NO UI: each
 * caller keeps rendering its own session-expired copy exactly as before. A page
 * reload (the only way back in after reopening from FinX) resets the latch.
 */
export function handleAuthExpired(trigger: SessionExpiredTrigger): void {
  if (sessionExpiredFired) return
  sessionExpiredFired = true
  sendSessionExpiredToHost(trigger)
}

/* ── reverse channel: host → page (file.downloaded / file.expired) ──────── */

/** The host replies with one of these once it has acted on a `file.ready`. */
export type NativeEventKind = 'file.downloaded' | 'file.expired'
export type NativeEventHandler = (kind: NativeEventKind, payload: unknown) => void

const _subscribers = new Map<string, NativeEventHandler>()

/**
 * Register a callback for host replies correlated to `id` (the id minted on the
 * outbound `file.ready` envelope). Returns an unsubscribe function.
 */
export function onHostFileEvent(id: string, handler: NativeEventHandler): () => void {
  _subscribers.set(id, handler)
  return () => {
    _subscribers.delete(id)
  }
}

/**
 * Parse-safe receiver the native host calls with the event (a JSON string, or
 * an already-parsed object). Dispatches `file.downloaded` / `file.expired` to
 * the subscriber registered for the envelope's `id`. Anything unknown or
 * malformed is ignored — this never throws back into the host.
 */
function onNativeEvent(input: unknown): void {
  let msg: unknown = input
  if (typeof input === 'string') {
    try {
      msg = JSON.parse(input)
    } catch {
      return
    }
  }
  if (msg === null || typeof msg !== 'object') return
  const ev = msg as Record<string, unknown>
  if (ev.type !== 'file.downloaded' && ev.type !== 'file.expired') return
  if (typeof ev.id !== 'string') return
  const handler = _subscribers.get(ev.id)
  if (handler !== undefined) handler(ev.type, ev.payload)
}

/**
 * Install the reverse channel under `window.JiniBridge`, preserving any fields
 * an existing bridge already put there. Runs once on import.
 */
function installNativeReceiver(): void {
  if (typeof window === 'undefined') return
  const w = window as unknown as { JiniBridge?: Record<string, unknown> }
  const existing = w.JiniBridge ?? {}
  existing.onNativeEvent = onNativeEvent
  w.JiniBridge = existing
}

installNativeReceiver()
