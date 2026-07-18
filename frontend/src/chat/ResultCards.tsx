import { useRef, useState } from 'react'
import { CheckIcon, DownloadIcon, MailIcon, TicketIcon } from '../icons'
import type { FileInfo } from '../flow/api'
import type { HelpKind } from '../flow/types'
import { RichText } from './RichText'

/* ── file-type badge (the little "PDF"/"XLS" tile) ────────────────────── */
function FormatBadge({ format }: Readonly<{ format: string }>) {
  const isExcel = /xls|excel/i.test(format)
  const label = isExcel ? 'XLS' : 'PDF'
  return (
    <span
      className={
        isExcel
          ? 'grid h-[50px] w-10 shrink-0 place-items-center rounded-lg border border-green-200 bg-green-50 text-[9.5px] font-extrabold text-green-700 dark:border-green-900 dark:bg-green-950/50 dark:text-green-400'
          : 'grid h-[50px] w-10 shrink-0 place-items-center rounded-lg border border-red-200 bg-red-50 text-[9.5px] font-extrabold text-red-600 dark:border-red-900 dark:bg-red-950/50 dark:text-red-400'
      }
    >
      {label}
    </span>
  )
}

function IconButton({
  title,
  onClick,
  children,
  variant = 'idle',
}: Readonly<{
  title: string
  onClick: () => void
  children: React.ReactNode
  variant?: 'idle' | 'done'
}>) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={[
        'grid size-9 place-items-center rounded-lg border transition-colors',
        variant === 'done'
          ? 'border-online bg-transparent text-online'
          : 'border-zinc-200 bg-white text-accent hover:border-accent-soft hover:bg-accent-tint dark:border-zinc-700 dark:bg-zinc-900 dark:text-accent-soft dark:hover:bg-accent/15',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

/**
 * Downloaded-report file card. The download button gives in-place feedback:
 * busy dot → green check → revert, so the tap is never silent (the real file
 * fetch happens via `onDownload`).
 */
export function FileCard({
  file,
  passwordNote,
  emailable = true,
  onDownload,
  onEmailIt,
  onHelp,
}: Readonly<{
  file: FileInfo
  passwordNote: string | null
  /** Contract notes have no email delivery → the "Email it" button is hidden. */
  emailable?: boolean
  onDownload: () => void
  onEmailIt?: () => void
  onHelp: () => void
}>) {
  const [status, setStatus] = useState<'idle' | 'busy' | 'done'>('idle')
  const busyRef = useRef(false)

  function handleDownload() {
    if (busyRef.current) return
    busyRef.current = true
    setStatus('busy')
    onDownload()
    setTimeout(() => setStatus('done'), 600)
    setTimeout(() => {
      setStatus('idle')
      busyRef.current = false
    }, 2300)
  }

  const sub = [file.sizeLabel, file.format, passwordNote].filter(Boolean).join(' · ')

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center gap-3 rounded-2xl border border-zinc-200 bg-white p-3.5 dark:border-zinc-700 dark:bg-zinc-900/60">
        <FormatBadge format={file.format} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            {file.name}
          </p>
          <p className="mt-0.5 text-[11.5px] text-zinc-400 dark:text-zinc-500">{sub}</p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <IconButton
            title="Download"
            onClick={handleDownload}
            variant={status === 'done' ? 'done' : 'idle'}
          >
            {status === 'busy' && <span className="size-2 animate-pulse rounded-full bg-accent" />}
            {status === 'done' && <CheckIcon className="size-4" />}
            {status === 'idle' && <DownloadIcon className="size-4" />}
          </IconButton>
          {emailable && onEmailIt && (
            <IconButton title="Email it" onClick={onEmailIt}>
              <MailIcon className="size-4" />
            </IconButton>
          )}
        </div>
      </div>
      <Followup label="Trouble opening it?" onHelp={onHelp} />
    </div>
  )
}

/** Masked-email confirmation card. */
export function EmailCard({
  noun,
  emailMasked,
  onHelp,
}: Readonly<{ noun: string; emailMasked: string; onHelp: () => void }>) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="rounded-2xl border border-zinc-200 bg-white p-3.5 dark:border-zinc-700 dark:bg-zinc-900/60">
        <p className="text-[14.5px] leading-relaxed text-zinc-800 dark:text-zinc-100">
          Done — <RichText text={noun} /> is on its way to{' '}
          <span className="font-semibold">{emailMasked}</span>{' '}
          <span className="font-extrabold text-online">✓</span>
        </p>
        <p className="mt-1.5 text-xs text-zinc-400 dark:text-zinc-500">
          Usually arrives within 2 minutes.
        </p>
      </div>
      <Followup label="Didn't get it?" onHelp={onHelp} />
    </div>
  )
}

function Followup({ label, onHelp }: Readonly<{ label: string; onHelp: () => void }>) {
  return (
    <p className="text-[13px] text-zinc-500 dark:text-zinc-400">
      {label}{' '}
      <button
        type="button"
        onClick={onHelp}
        className="font-semibold text-accent dark:text-accent-soft"
      >
        Tell me.
      </button>
    </p>
  )
}

/** Actionable help card (context options + raise a ticket). */
export function HelpCard({
  helpKind,
  onResend,
  onRaiseTicket,
}: Readonly<{ helpKind: HelpKind; onResend: () => void; onRaiseTicket: () => void }>) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-3.5 dark:border-zinc-700 dark:bg-zinc-900/60">
      <div className="flex flex-wrap gap-2">
        {helpKind === 'email' && (
          <button
            type="button"
            onClick={onResend}
            className="inline-flex items-center gap-2 rounded-full border-[1.5px] border-zinc-200 bg-white px-3.5 py-2 text-[13.5px] font-semibold text-zinc-700 hover:border-accent-soft hover:text-accent dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:text-accent-soft"
          >
            <MailIcon className="size-4 text-accent dark:text-accent-soft" />
            Resend email
          </button>
        )}
        <button
          type="button"
          onClick={onRaiseTicket}
          className="inline-flex items-center gap-2 rounded-full border-[1.5px] border-accent bg-accent px-3.5 py-2 text-[13.5px] font-semibold text-white hover:bg-accent-strong"
        >
          <TicketIcon className="size-4" />
          Raise a ticket
        </button>
      </div>
    </div>
  )
}

/** Ticket-confirmation card (stub id + open status). */
export function TicketCard({ ticketId }: Readonly<{ ticketId: string }>) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-3.5 dark:border-zinc-700 dark:bg-zinc-900/60">
      <div className="flex items-center gap-3">
        <span className="grid h-[50px] w-10 shrink-0 place-items-center rounded-lg border border-accent-soft bg-accent-tint text-accent dark:bg-accent/20 dark:text-accent-soft">
          <TicketIcon className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            Ticket #{ticketId} raised
          </p>
          <p className="mt-0.5 text-[11.5px] text-zinc-400 dark:text-zinc-500">
            Status: Open · we'll email you updates
          </p>
        </div>
      </div>
      <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
        Usually resolved within 24 hours — you can check progress anytime by asking "my ticket
        status".
      </p>
    </div>
  )
}
