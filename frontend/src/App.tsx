import { useState, type ReactNode } from 'react'
import {
  ArrowUpIcon,
  BackIcon,
  LedgerIcon,
  PercentIcon,
  SparkleIcon,
  TicketIcon,
  TrendingUpIcon,
} from './icons'
import { postCloseToHost } from './embed'
import { getSessionContext, hasCredentials } from './session'
import { useGreeting } from './useGreeting'
import { useWhatsNew } from './useWhatsNew'
import { WhatsNewModal } from './WhatsNewModal'

const QUICK_ACTIONS: { label: string; icon: ReactNode }[] = [
  { label: 'Get my P&L', icon: <TrendingUpIcon className="size-3.5" /> },
  { label: 'Show my ledger', icon: <LedgerIcon className="size-3.5" /> },
  { label: 'Check my ticket status', icon: <TicketIcon className="size-3.5" /> },
  { label: 'What are my brokerage charges?', icon: <PercentIcon className="size-3.5" /> },
]

/**
 * Submits a user query. Chat handling lands in a later change — for now
 * this is the single stub code path shared by typing + send and the
 * quick-action chips.
 */
function submitQuery(text: string): void {
  console.log('[choice-jini] query submitted:', text)
}

function Header({
  userId,
  whatsNewDot,
  onWhatsNew,
  onBack,
}: Readonly<{
  userId: string | null
  whatsNewDot: boolean
  onWhatsNew: () => void
  onBack?: () => void
}>) {
  return (
    <header className="flex items-center gap-2.5 border-b border-zinc-100 px-4 pt-4 pb-3.5 dark:border-zinc-800/80">
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
    </header>
  )
}

function Hero({ firstName }: Readonly<{ firstName: string | null }>) {
  return (
    <section className="px-5 pt-5">
      <h2 className="text-[26px] leading-8 font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
        Hey <span className="text-accent dark:text-accent-soft">{firstName ?? 'there'}</span> — what
        do you need?
      </h2>
      <p className="mt-3 text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
        Reports, charges, processes, ticket status.
      </p>
      <p className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
        Files land right here —{' '}
        <span className="font-medium text-online dark:text-online-soft">
          no email verification.
        </span>
      </p>
    </section>
  )
}

function QuickActions({ onPick }: Readonly<{ onPick: (label: string) => void }>) {
  return (
    <section className="px-5 pt-6">
      <h3 className="text-[11px] font-semibold tracking-[0.14em] text-zinc-400 uppercase dark:text-zinc-500">
        Popular right now
      </h3>
      <div className="mt-3 flex flex-wrap gap-2">
        {QUICK_ACTIONS.map(({ label, icon }) => (
          <button
            key={label}
            type="button"
            onClick={() => onPick(label)}
            className="flex items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-3.5 py-2 text-[13px] font-medium text-zinc-700 transition-colors hover:border-accent/40 hover:bg-accent-tint/40 active:scale-[0.98] dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:border-accent-soft/50 dark:hover:bg-accent/15"
          >
            <span className="text-accent dark:text-accent-soft">{icon}</span>
            {label}
          </button>
        ))}
      </div>
    </section>
  )
}

function Composer({ onSubmit }: Readonly<{ onSubmit: (text: string) => void }>) {
  const [draft, setDraft] = useState('')

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        const text = draft.trim()
        if (text === '') return
        onSubmit(text)
        setDraft('')
      }}
      className="flex items-center gap-2 px-4 pt-4"
    >
      <input
        type="text"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="Reports, charges, processes, tickets…"
        aria-label="Ask Choice Jini"
        className="h-12 min-w-0 flex-1 rounded-full border border-zinc-200 bg-zinc-50 px-4.5 text-sm text-zinc-900 transition-shadow outline-none placeholder:text-zinc-400 focus:border-accent/50 focus:ring-2 focus:ring-accent/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500 dark:focus:border-accent-soft/50 dark:focus:ring-accent-soft/20"
      />
      <button
        type="submit"
        aria-label="Send"
        className="grid size-12 shrink-0 place-items-center rounded-full bg-accent text-white shadow-lg shadow-accent/30 transition hover:bg-accent-strong active:scale-95"
      >
        <ArrowUpIcon className="size-5" />
      </button>
    </form>
  )
}

export default function App() {
  const session = getSessionContext()
  const firstName = useGreeting(session)
  const userId = hasCredentials(session) ? session.userId : null

  const whatsNew = useWhatsNew()
  const [whatsNewOpen, setWhatsNewOpen] = useState(false)

  function closeWhatsNew() {
    whatsNew.markSeen()
    setWhatsNewOpen(false)
  }

  return (
    // Full-bleed: the page IS the widget surface — the embed panel (web) or
    // webview (app) owns the card chrome. No self-rounding, border, shadow,
    // or backdrop on any platform. Content column capped for wide standalone
    // windows; invisible at panel/webview widths.
    <div className="min-h-dvh bg-white font-sans antialiased dark:bg-zinc-900">
      <main className="mx-auto flex min-h-dvh w-full max-w-[480px] flex-col">
        <Header
          userId={userId}
          whatsNewDot={whatsNew.hasUnseen}
          onWhatsNew={() => {
            // Content unavailable -> pill is a graceful no-op.
            if (whatsNew.items !== null) setWhatsNewOpen(true)
          }}
          // Inside the website's corner panel the back arrow closes the
          // panel; on app webviews the host owns navigation (no-op).
          onBack={session.platform === 'web' ? postCloseToHost : undefined}
        />
        <Hero firstName={firstName} />
        <QuickActions onPick={submitQuery} />

        {/* mt-auto anchors divider/composer/footer to the bottom on tall
            viewports; pt-6 keeps the minimum gap when space is tight. */}
        <div className="mt-auto flex items-center gap-3 px-5 pt-6">
          <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
          <span className="text-xs text-zinc-400 dark:text-zinc-500">
            or ask anything about FinX
          </span>
          <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
        </div>

        <Composer onSubmit={submitQuery} />

        <p className="px-5 pt-4 pb-5 text-center text-[11px] text-zinc-400 dark:text-zinc-600">
          Factual answers only — never investment advice
        </p>
      </main>

      {whatsNewOpen && whatsNew.items !== null && (
        <WhatsNewModal items={whatsNew.items} onClose={closeWhatsNew} />
      )}
    </div>
  )
}
