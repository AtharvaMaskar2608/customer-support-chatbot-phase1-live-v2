/**
 * Chat-page side of the corner-widget bridge (widget-launcher capability).
 *
 * When the chat page runs inside the FinX website's corner panel
 * (platform=web), the header back arrow posts a close message to the parent
 * page; the embed script (src/widget/widget.ts) listens, verifies the
 * origin, and hides the panel. Messaging is origin-checked both ways: we
 * target the embedding origin (never "*" unless it is unknowable), and the
 * embed script only accepts messages from the chat page's origin.
 */

const CLOSE_MESSAGE_TYPE = 'choice-jini:close'

function embedTargetOrigin(): string {
  // ancestorOrigins: Chromium + WebKit. Firefox falls back to the referrer.
  const origins = window.location.ancestorOrigins as DOMStringList | undefined
  if (origins !== undefined && origins.length > 0) return origins[0]
  try {
    if (document.referrer !== '') return new URL(document.referrer).origin
  } catch {
    // Unparseable referrer — fall through.
  }
  return '*'
}

/** Ask the host page to close the corner panel. No-op outside an iframe. */
export function postCloseToHost(): void {
  if (window.parent === window) return
  window.parent.postMessage({ type: CLOSE_MESSAGE_TYPE }, embedTargetOrigin())
}
