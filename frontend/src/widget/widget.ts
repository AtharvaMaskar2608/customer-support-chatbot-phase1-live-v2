/**
 * Choice Jini corner widget embed (widget-launcher capability).
 *
 * Framework-free launcher the FinX website includes with one script tag:
 *
 *   <script src="https://<our-host>/widget.js"></script>
 *   <script>ChoiceJini.init({ userId, sessionId, accessToken, isDarkTheme, ... })</script>
 *
 * Built as a separate Vite entry (IIFE, no React — see vite.widget.config.ts,
 * output dist/widget.js). In development the same module is served by the Vite
 * dev server and loaded from demo/index.html via
 * `<script type="module" src="/src/widget/widget.ts">`.
 *
 * Renders (inside a shadow root, so host CSS cannot leak in):
 * - a circular blue launcher bubble fixed bottom-right over host content
 * - a corner panel (~380x640 desktop, full-screen under 480px) holding an
 *   iframe of the chat page with the init params as query string plus
 *   `platform=web`
 *
 * Panel lifecycle (design decision 11): closing only hides via CSS — the
 * iframe mounts on first open and stays mounted, so the chat page boots once
 * per host page load. The chat page's back arrow posts
 * `{type: "choice-jini:close"}` which we accept only from the chat origin.
 */

export interface ChoiceJiniInitOptions {
  /** Absolute or root-relative URL of the chat page. Default: "/" on the host's origin. */
  chatUrl?: string
  userId?: string
  sessionId?: string
  accessToken?: string
  isDarkTheme?: boolean
  obStatus?: string
  screenName?: string
}

declare global {
  interface Window {
    ChoiceJini?: { init: (options?: ChoiceJiniInitOptions) => void }
  }
}

const CLOSE_MESSAGE_TYPE = 'choice-jini:close'

const SPARKLE_PATH =
  'M12 2.6c.96 4.9 3.6 7.55 8.5 8.5-4.9.96-7.54 3.6-8.5 8.5-.96-4.9-3.6-7.54-8.5-8.5 4.9-.95 7.54-3.6 8.5-8.5Z'

const STYLE = `
:host { all: initial; }
* { box-sizing: border-box; }

.bubble {
  position: fixed;
  right: 20px;
  bottom: 20px;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  border: none;
  padding: 0;
  cursor: pointer;
  background: linear-gradient(135deg, #4a90f5 0%, #1d5fd0 100%);
  color: #fff;
  box-shadow: 0 8px 24px rgba(29, 95, 208, 0.45), 0 2px 6px rgba(0, 0, 0, 0.15);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  z-index: 2147483001;
}
.bubble:hover {
  transform: scale(1.06);
  box-shadow: 0 10px 28px rgba(109, 40, 217, 0.5), 0 2px 6px rgba(0, 0, 0, 0.15);
}
.bubble:active { transform: scale(0.97); }

.icon {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 26px;
  height: 26px;
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.icon-close { opacity: 0; transform: rotate(-90deg) scale(0.5); }
.root.open .icon-sparkle { opacity: 0; transform: rotate(90deg) scale(0.5); }
.root.open .icon-close { opacity: 1; transform: none; }

.panel {
  position: fixed;
  right: 20px;
  bottom: 90px;
  width: 380px;
  height: 640px;
  max-width: calc(100vw - 40px);
  max-height: calc(100vh - 110px);
  border-radius: 24px;
  overflow: hidden;
  background: #ffffff;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.3), 0 4px 16px rgba(0, 0, 0, 0.12);
  opacity: 0;
  visibility: hidden;
  transform: translateY(14px) scale(0.97);
  transform-origin: bottom right;
  transition: opacity 0.22s ease, transform 0.22s ease, visibility 0s linear 0.22s;
  z-index: 2147483000;
}
.panel.dark { background: #18181b; }
.root.open .panel {
  opacity: 1;
  visibility: visible;
  transform: none;
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.frame { display: block; width: 100%; height: 100%; border: 0; }

@media (max-width: 480px) {
  .panel {
    inset: 0;
    width: 100%;
    height: 100%;
    max-width: none;
    max-height: none;
    border-radius: 0;
  }
}
`

function buildChatSrc(options: ChoiceJiniInitOptions): URL {
  const url = new URL(options.chatUrl ?? '/', window.location.href)
  const params = url.searchParams
  params.set('platform', 'web')
  params.set('isDarkTheme', options.isDarkTheme === true ? 'true' : 'false')
  if (options.userId) params.set('userId', options.userId)
  if (options.sessionId) params.set('sessionId', options.sessionId)
  if (options.accessToken) params.set('accessToken', options.accessToken)
  if (options.obStatus) params.set('obStatus', options.obStatus)
  if (options.screenName) params.set('screenName', options.screenName)
  return url
}

let initialized = false

export function init(options: ChoiceJiniInitOptions = {}): void {
  if (initialized) {
    console.warn('[choice-jini] ChoiceJini.init() called more than once; ignoring')
    return
  }
  initialized = true

  const chatSrc = buildChatSrc(options)
  const chatOrigin = chatSrc.origin

  const host = document.createElement('div')
  host.id = 'choice-jini-widget'
  const shadow = host.attachShadow({ mode: 'open' })

  const style = document.createElement('style')
  style.textContent = STYLE

  const root = document.createElement('div')
  root.className = 'root'

  const panel = document.createElement('div')
  panel.className = options.isDarkTheme === true ? 'panel dark' : 'panel'

  const bubble = document.createElement('button')
  bubble.type = 'button'
  bubble.className = 'bubble'
  bubble.setAttribute('aria-label', 'Open AskFinX support chat')
  bubble.setAttribute('aria-expanded', 'false')
  bubble.innerHTML = `
    <svg class="icon icon-sparkle" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${SPARKLE_PATH}"/></svg>
    <svg class="icon icon-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>`

  let iframe: HTMLIFrameElement | null = null
  let open = false

  function ensureIframe(): void {
    if (iframe !== null) return
    iframe = document.createElement('iframe')
    iframe.className = 'frame'
    iframe.title = 'AskFinX support chat'
    iframe.src = chatSrc.href
    panel.appendChild(iframe)
  }

  function setOpen(next: boolean): void {
    open = next
    // Mounted on first open, never unmounted — close only hides with CSS so
    // the chat page keeps its state and boots once per host page load.
    if (open) ensureIframe()
    root.classList.toggle('open', open)
    bubble.setAttribute('aria-expanded', String(open))
  }

  bubble.addEventListener('click', () => setOpen(!open))

  window.addEventListener('message', (event: MessageEvent) => {
    if (event.origin !== chatOrigin) return
    const data: unknown = event.data
    if (
      data !== null &&
      typeof data === 'object' &&
      (data as { type?: unknown }).type === CLOSE_MESSAGE_TYPE
    ) {
      setOpen(false)
    }
  })

  root.append(panel, bubble)
  shadow.append(style, root)
  document.body.appendChild(host)
}

window.ChoiceJini = { init }
