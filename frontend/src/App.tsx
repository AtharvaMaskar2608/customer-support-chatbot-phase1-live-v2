import { useState } from 'react'
import { BackIcon, SparkleIcon } from './icons'
import { postCloseToHost } from './embed'
import { getSessionContext, hasCredentials } from './session'
import { useGreeting } from './useGreeting'
import { useWhatsNew } from './useWhatsNew'
import { WhatsNewModal } from './WhatsNewModal'
import { authHeaders } from './chat/agent'
import { ChatShell } from './chat/ChatShell'

function Header({
  userId,
  engaged,
  whatsNewDot,
  onWhatsNew,
  onRestart,
  onBack,
}: Readonly<{
  userId: string | null
  /** Conversation running → the pill slot shows Restart instead (CHO-216). */
  engaged: boolean
  whatsNewDot: boolean
  onWhatsNew: () => void
  onRestart: () => void
  onBack?: () => void
}>) {
  return (
    <header className="flex shrink-0 items-center gap-2.5 border-b border-zinc-100 px-4 pt-4 pb-3.5 dark:border-zinc-800/80">
      <button
        type="button"
        aria-label="Go back"
        onClick={onBack}
        className="-ml-1.5 grid size-9 shrink-0 place-items-center rounded-full text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      >
        <BackIcon className="size-5" />
      </button>

      <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-linear-to-br from-violet-500 to-accent-strong text-white shadow-md shadow-accent/25">
        <SparkleIcon className="size-5.5" />
      </div>

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[15px] font-semibold text-zinc-900 dark:text-zinc-50">
          Choice Jini
        </h1>
        <p className="flex items-center gap-1.5 text-xs leading-4">
          <span className="size-1.5 shrink-0 rounded-full bg-online dark:bg-online-soft" />
          <span className="truncate">
            <span className="font-medium text-online dark:text-online-soft">online</span>
            {userId !== null && (
              <span className="text-zinc-400 dark:text-zinc-500"> · {userId}</span>
            )}
          </span>
        </p>
      </div>

      {engaged ? (
        // Same pill slot: once a conversation kicks off, Restart takes over.
        // No unseen dot here — that belongs to What's New only.
        <button
          type="button"
          onClick={onRestart}
          className="relative shrink-0 rounded-full bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
        >
          <span>↻ Restart</span>
        </button>
      ) : (
        <button
          type="button"
          aria-haspopup="dialog"
          onClick={onWhatsNew}
          // Dark pill on light header; inverted to a light elevated pill in
          // dark mode so it stays clearly visible on the near-black header.
          className="relative shrink-0 rounded-full bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
        >
          <span>✨ What's new</span>
          {whatsNewDot && (
            <span
              aria-hidden="true"
              className="absolute -top-px -right-px size-2 rounded-full bg-alert ring-2 ring-white dark:ring-zinc-900"
            />
          )}
        </button>
      )}
    </header>
  )
}

export default function App() {
  const session = getSessionContext()
  const firstName = useGreeting(session)
  const userId = hasCredentials(session) ? session.userId : null

  const whatsNew = useWhatsNew()
  const [whatsNewOpen, setWhatsNewOpen] = useState(false)

  // CHO-216: conversation state drives the header pill; Restart bumps the
  // shell key (full remount = every message/stream/ref resets by
  // construction) and asks the backend for a fresh agent thread.
  const [engaged, setEngaged] = useState(false)
  const [shellKey, setShellKey] = useState(0)

  function closeWhatsNew() {
    whatsNew.markSeen()
    setWhatsNewOpen(false)
  }

  function handleRestart() {
    setEngaged(false)
    setShellKey((k) => k + 1)
    if (hasCredentials(session)) {
      // Fire-and-forget: the home screen appears immediately; a failed reset
      // degrades to the next message continuing the old thread — never blocks.
      void fetch('/api/chat/reset', {
        method: 'POST',
        headers: authHeaders(session),
      }).catch(() => {})
    }
  }

  return (
    // Full-bleed: the page IS the widget surface — the embed panel (web) or
    // webview (app) owns the card chrome. A bounded flex column so the
    // conversation scrolls between a pinned header and a pinned composer.
    <div className="h-dvh bg-white font-sans antialiased dark:bg-zinc-900">
      <main className="mx-auto flex h-dvh w-full max-w-[480px] flex-col">
        <Header
          userId={userId}
          engaged={engaged}
          whatsNewDot={whatsNew.hasUnseen}
          onWhatsNew={() => {
            // Content unavailable -> pill is a graceful no-op.
            if (whatsNew.items !== null) setWhatsNewOpen(true)
          }}
          onRestart={handleRestart}
          // Inside the website's corner panel the back arrow closes the
          // panel; on app webviews the host owns navigation (no-op).
          onBack={session.platform === 'web' ? postCloseToHost : undefined}
        />

        <ChatShell
          key={shellKey}
          session={session}
          firstName={firstName}
          onEngaged={() => setEngaged(true)}
        />
      </main>

      {whatsNewOpen && whatsNew.items !== null && (
        <WhatsNewModal items={whatsNew.items} onClose={closeWhatsNew} />
      )}
    </div>
  )
}
