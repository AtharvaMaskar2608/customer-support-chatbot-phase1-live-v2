import { useCallback, useEffect, useState } from 'react'

/**
 * "What's new" announcements (whats-new capability, frontend half).
 *
 * Pinned backend contract (no credentials required — broadcast content):
 *   GET /api/whats-new
 *   200 -> {"version": "<id>", "items": [{"emoji", "tint", "title", "description"}, ...]}
 *
 * The red dot on the header pill shows only while the fetched version
 * differs from the locally persisted seen version. Dismissing the modal
 * persists the current version so the dot stays hidden across reloads
 * until the backend publishes a newer version.
 *
 * Fetch failure -> content stays null: no dot, pill is a no-op, home
 * screen unaffected.
 */

const SEEN_VERSION_KEY = 'choiceJini.whatsNew.seenVersion'

export interface WhatsNewItem {
  emoji: string
  /** Icon tile color key (e.g. "indigo", "green"); unknown keys render neutral. */
  tint: string
  title: string
  description: string
}

interface WhatsNewContent {
  version: string
  items: WhatsNewItem[]
}

/* localStorage can throw in locked-down webviews — degrade to in-memory. */
function readSeenVersion(): string | null {
  try {
    return window.localStorage.getItem(SEEN_VERSION_KEY)
  } catch {
    return null
  }
}

function writeSeenVersion(version: string): void {
  try {
    window.localStorage.setItem(SEEN_VERSION_KEY, version)
  } catch {
    // Seen-state lives only in memory for this page load.
  }
}

function parseContent(body: unknown): WhatsNewContent | null {
  if (body === null || typeof body !== 'object') return null
  const { version, items } = body as { version?: unknown; items?: unknown }
  if (typeof version !== 'string' || version.trim() === '' || !Array.isArray(items)) return null

  const parsed: WhatsNewItem[] = []
  for (const item of items) {
    if (item === null || typeof item !== 'object') continue
    const { emoji, tint, title, description } = item as Record<string, unknown>
    if (typeof emoji !== 'string' || typeof title !== 'string' || typeof description !== 'string') {
      continue
    }
    parsed.push({ emoji, tint: typeof tint === 'string' ? tint : '', title, description })
  }

  return parsed.length > 0 ? { version, items: parsed } : null
}

export function useWhatsNew(): {
  /** Announcement items, or null while loading / when unavailable. */
  items: WhatsNewItem[] | null
  /** True when the current content version has not been dismissed on this device. */
  hasUnseen: boolean
  /** Persist the current version as seen (hides the dot until a newer version ships). */
  markSeen: () => void
} {
  const [content, setContent] = useState<WhatsNewContent | null>(null)
  const [seenVersion, setSeenVersion] = useState<string | null>(readSeenVersion)

  useEffect(() => {
    const controller = new AbortController()

    fetch('/api/whats-new', { signal: controller.signal })
      .then(async (res) => (res.ok ? parseContent(await res.json().catch(() => null)) : null))
      .then((parsed) => {
        if (parsed !== null && !controller.signal.aborted) setContent(parsed)
      })
      .catch(() => {
        // Unavailable -> no dot, pill no-op.
      })

    return () => controller.abort()
  }, [])

  const markSeen = useCallback(() => {
    if (content === null) return
    writeSeenVersion(content.version)
    setSeenVersion(content.version)
  }, [content])

  return {
    items: content?.items ?? null,
    hasUnseen: content !== null && content.version !== seenVersion,
    markSeen,
  }
}
