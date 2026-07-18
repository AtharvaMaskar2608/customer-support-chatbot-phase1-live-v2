import { useEffect, useRef, useState } from 'react'
import { ArrowUpIcon } from '../icons'
import { hasCredentials, type SessionContext } from '../session'
import { getFlow, matchFlow } from '../flow/registry'
import { submitReport, downloadReportFile, type ReportResult } from '../flow/api'
import { editSlot, fillSlot, lockRun, startRun, type FlowRun } from '../flow/engine'
import { toHuman, today } from '../flow/dates'
import type { DeliveryMode, FilledValues, FlowDescriptor, SlotValue } from '../flow/types'
import {
  errorLine,
  helpIntro,
  makeTicketId,
  nextId,
  type Message,
} from './messages'
import { EmptyState } from './EmptyState'
import { Stickers } from './Stickers'
import { FlowCard } from './FlowCard'
import { Typing, NarratePill } from './Indicators'
import { EmailCard, FileCard, HelpCard, TicketCard } from './ResultCards'
import { RichText } from './RichText'

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/**
 * The chat shell — one continuous conversation (report-chat-shell). The empty
 * state (greeting + stickers) collapses on first engagement; messages append
 * and auto-scroll; the composer is pinned and keyword-routes to a flow. Runs
 * the descriptor-driven engine inline and wires P&L to the backend.
 */
export function ChatShell({
  session,
  firstName,
}: Readonly<{ session: SessionContext; firstName: string | null }>) {
  const [messages, setMessages] = useState<Message[]>([])
  const [phase, setPhase] = useState<'empty' | 'collapsing' | 'chat'>('empty')
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to the newest message.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, phase])

  /* ── message list helpers (imperative, mirroring the prototype) ─────── */
  const append = (m: Message) => setMessages((prev) => [...prev, m])
  const remove = (id: string) => setMessages((prev) => prev.filter((m) => m.id !== id))
  const bot = (text: string) => append({ id: nextId(), kind: 'bot', text })
  const user = (text: string) => append({ id: nextId(), kind: 'user', text })

  function updateRun(msgId: string, fn: (run: FlowRun) => FlowRun) {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId && m.kind === 'flow' ? { ...m, run: fn(m.run) } : m)),
    )
  }
  function updateCaption(msgId: string, caption: string) {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId && m.kind === 'narrate' ? { ...m, caption } : m)),
    )
  }

  /** Show typing dots, then run `fn`. */
  function botThen(fn: () => void, ms = 480) {
    const id = nextId()
    append({ id, kind: 'typing' })
    setTimeout(() => {
      remove(id)
      fn()
    }, ms)
  }

  function engage() {
    setPhase((p) => (p === 'empty' ? 'collapsing' : p))
  }

  /* ── entry points ───────────────────────────────────────────────────── */

  function runFlowBody(descriptor: FlowDescriptor) {
    if (descriptor.comingSoon || descriptor.backend === undefined) {
      bot(
        `That one's coming in the next update — I'm still wiring it up. Right now I can pull your **P&L** live:`,
      )
      append({ id: nextId(), kind: 'actions' })
      return
    }
    bot(descriptor.intro)
    append({ id: nextId(), kind: 'flow', run: startRun(descriptor) })
  }

  /** Sticker tap. */
  function startFromSticker(descriptor: FlowDescriptor) {
    engage()
    user(descriptor.trigger)
    botThen(() => runFlowBody(descriptor))
  }

  /** Composer submit → keyword routing. */
  function onSend(text: string) {
    engage()
    user(text)
    const flow = matchFlow(text)
    botThen(() => {
      if (flow) {
        runFlowBody(flow)
      } else {
        bot('I can pull your P&L, ledger, capital gains and contract notes right now — tap one:')
        append({ id: nextId(), kind: 'actions' })
      }
    })
  }

  /* ── slot interactions ──────────────────────────────────────────────── */

  function handlePick(msgId: string, descriptor: FlowDescriptor, slotKey: string, value: SlotValue) {
    updateRun(msgId, (run) => fillSlot(descriptor, run, slotKey, value))
  }
  function handleEdit(msgId: string, slotKey: string) {
    updateRun(msgId, (run) => editSlot(run, slotKey))
  }
  function handleDeliver(msgId: string, descriptor: FlowDescriptor, run: FlowRun, mode: DeliveryMode) {
    updateRun(msgId, lockRun)
    void generate(descriptor, run.values, mode)
  }

  /* ── generation (narrated wait + backend call, overlapped) ──────────── */

  async function generate(descriptor: FlowDescriptor, values: FilledValues, mode: DeliveryMode) {
    const steps =
      mode === 'email'
        ? [...descriptor.narration.slice(0, -1), 'Emailing it to you…']
        : descriptor.narration.slice()

    const narrId = nextId()
    append({ id: narrId, kind: 'narrate', caption: steps[0] })

    // Fetch and narration run in parallel; the pill holds its last caption
    // until the response resolves.
    const resultP: Promise<ReportResult> = descriptor.backend
      ? submitReport(descriptor.backend, values, mode, session)
      : Promise.resolve({ kind: 'error', code: 'UPSTREAM_ERROR' })

    for (let i = 1; i < steps.length; i += 1) {
      await delay(720)
      updateCaption(narrId, steps[i])
    }
    await delay(560)
    const result = await resultP
    remove(narrId)
    renderResult(descriptor, values, result)
  }

  function renderResult(
    descriptor: FlowDescriptor,
    values: FlowRun['values'],
    result: ReportResult,
  ) {
    if (result.kind === 'error') {
      bot(errorLine(result.code))
      return
    }
    if (result.kind === 'email') {
      append({
        id: nextId(),
        kind: 'email',
        noun: descriptor.result.emailNoun(values),
        emailMasked: result.emailMasked,
      })
      return
    }
    // download
    bot(descriptor.result.summary(values, toHuman(today())))
    append({
      id: nextId(),
      kind: 'download',
      flowKey: descriptor.key,
      values,
      file: result.file,
      fileToken: result.fileToken,
      passwordNote: descriptor.result.passwordNote,
      helpKind: descriptor.result.helpKind,
    })
  }

  /* ── result-card actions ────────────────────────────────────────────── */

  function handleDownload(fileToken: string, fileName: string) {
    void downloadReportFile(fileToken, fileName)
  }
  function handleEmailIt(flowKey: string, values: FlowRun['values']) {
    const descriptor = getFlow(flowKey)
    if (!descriptor) return
    user('Email it to me')
    void generate(descriptor, values, 'email')
  }
  function openHelp(kind: 'pdf' | 'cn' | 'email') {
    botThen(() => {
      bot(helpIntro(kind))
      append({ id: nextId(), kind: 'help', helpKind: kind })
    }, 420)
  }
  function handleResend() {
    user('Resend it')
    botThen(() => bot('Resent — check again in a minute.'))
  }
  async function handleRaiseTicket() {
    user('Raise a ticket')
    const narrId = nextId()
    append({ id: narrId, kind: 'narrate', caption: 'Creating your ticket…' })
    await delay(720)
    updateCaption(narrId, 'Assigning to support…')
    await delay(720)
    remove(narrId)
    append({ id: nextId(), kind: 'ticket', ticketId: makeTicketId() })
  }

  /* ── render ─────────────────────────────────────────────────────────── */

  return (
    <>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
        <div className="flex min-h-full flex-col gap-3 p-4">
          {phase !== 'chat' && (
            <EmptyState
              firstName={firstName}
              collapsing={phase === 'collapsing'}
              onCollapsed={() => setPhase('chat')}
              onPick={startFromSticker}
            />
          )}

          {messages.map((m) => (
            <MessageView
              key={m.id}
              message={m}
              onPick={handlePick}
              onEdit={handleEdit}
              onDeliver={handleDeliver}
              onSticker={startFromSticker}
              onDownload={handleDownload}
              onEmailIt={handleEmailIt}
              onHelp={openHelp}
              onResend={handleResend}
              onRaiseTicket={handleRaiseTicket}
            />
          ))}
        </div>
      </div>

      <div className="shrink-0 border-t border-zinc-100 bg-white px-4 pt-3 pb-2.5 dark:border-zinc-800 dark:bg-zinc-900">
        <Composer onSubmit={onSend} disabled={!hasCredentials(session)} />
        <p className="mt-2 text-center text-[11px] text-zinc-400 dark:text-zinc-600">
          Factual answers only — never investment advice
        </p>
      </div>
    </>
  )
}

/* ── one message, dispatched by kind ──────────────────────────────────── */

function MessageView({
  message,
  onPick,
  onEdit,
  onDeliver,
  onSticker,
  onDownload,
  onEmailIt,
  onHelp,
  onResend,
  onRaiseTicket,
}: Readonly<{
  message: Message
  onPick: (msgId: string, descriptor: FlowDescriptor, slotKey: string, value: SlotValue) => void
  onEdit: (msgId: string, slotKey: string) => void
  onDeliver: (msgId: string, descriptor: FlowDescriptor, run: FlowRun, mode: DeliveryMode) => void
  onSticker: (descriptor: FlowDescriptor) => void
  onDownload: (fileToken: string, fileName: string) => void
  onEmailIt: (flowKey: string, values: FlowRun['values']) => void
  onHelp: (kind: 'pdf' | 'cn' | 'email') => void
  onResend: () => void
  onRaiseTicket: () => void
}>) {
  const m = message
  switch (m.kind) {
    case 'user':
      return (
        <div className="max-w-[82%] self-end rounded-[16px] rounded-br-[4px] bg-accent px-4 py-2.5 text-sm font-semibold text-white">
          {m.text}
        </div>
      )
    case 'bot':
      return (
        <p className="text-[14.5px] leading-normal text-zinc-800 dark:text-zinc-100">
          <RichText text={m.text} />
        </p>
      )
    case 'typing':
      return <Typing />
    case 'narrate':
      return <NarratePill caption={m.caption} />
    case 'actions':
      return <Stickers onPick={onSticker} />
    case 'flow': {
      const descriptor = getFlow(m.run.flowKey)
      if (!descriptor) return null
      return (
        <FlowCard
          descriptor={descriptor}
          run={m.run}
          onPick={(slotKey, value) => onPick(m.id, descriptor, slotKey, value)}
          onEdit={(slotKey) => onEdit(m.id, slotKey)}
          onDeliver={(mode) => onDeliver(m.id, descriptor, m.run, mode)}
        />
      )
    }
    case 'download':
      return (
        <FileCard
          file={m.file}
          passwordNote={m.passwordNote}
          onDownload={() => onDownload(m.fileToken, m.file.name)}
          onEmailIt={() => onEmailIt(m.flowKey, m.values)}
          onHelp={() => onHelp(m.helpKind)}
        />
      )
    case 'email':
      return <EmailCard noun={m.noun} emailMasked={m.emailMasked} onHelp={() => onHelp('email')} />
    case 'help':
      return <HelpCard helpKind={m.helpKind} onResend={onResend} onRaiseTicket={onRaiseTicket} />
    case 'ticket':
      return <TicketCard ticketId={m.ticketId} />
  }
}

/* ── pinned composer ──────────────────────────────────────────────────── */

function Composer({
  onSubmit,
  disabled,
}: Readonly<{ onSubmit: (text: string) => void; disabled: boolean }>) {
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
      className="flex items-center gap-2 rounded-full border-[1.5px] border-zinc-200 bg-white py-1 pr-1 pl-4 transition-colors focus-within:border-accent-soft dark:border-zinc-700 dark:bg-zinc-900"
    >
      <input
        type="text"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="Reports, charges, processes, tickets…"
        aria-label="Ask Choice Jini"
        className="min-w-0 flex-1 bg-transparent py-2 text-[13.5px] text-zinc-900 outline-none placeholder:text-zinc-400 dark:text-zinc-100 dark:placeholder:text-zinc-500"
      />
      <button
        type="submit"
        aria-label="Send"
        disabled={disabled}
        className="grid size-9 shrink-0 place-items-center rounded-full bg-accent text-white transition hover:bg-accent-strong active:scale-95 disabled:opacity-40"
      >
        <ArrowUpIcon className="size-4.5" />
      </button>
    </form>
  )
}
