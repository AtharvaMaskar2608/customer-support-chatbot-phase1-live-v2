import { useEffect, useRef, useState } from 'react'
import { ArrowUpIcon } from '../icons'
import { hasCredentials, type SessionContext } from '../session'
import { getFlow, matchFlow } from '../flow/registry'
import { getDataFlow, matchDataFlow } from '../flow/dataRegistry'
import { isDataFlow, type AnyFlowDescriptor, type DataFlowDescriptor } from '../flow/dataflow'
import { submitReport, downloadReportFile, type FileInfo, type ReportResult } from '../flow/api'
import { handleAuthExpired, sendFileToHost } from '../bridge'
import { editSlot, fillSlot, lockRun, startRun, type FlowRun } from '../flow/engine'
import { toHuman, today } from '../flow/dates'
import type {
  DateRangeValue,
  DeliveryMode,
  FilledValues,
  FlowDescriptor,
  HelpKind,
  SelectionSlot,
  SlotValue,
} from '../flow/types'
import {
  agentInterruptLine,
  dataErrorLine,
  errorLine,
  helpIntro,
  nextId,
  toolCaption,
  type Message,
} from './messages'
import { authHeaders, streamAgentChat, type AgentArtifact } from './agent'
import { parseDataArtifact, parseFlowArtifact } from './agentArtifacts'
import { downloadContractNote, fetchContractNotes, type ClientNote } from './notes'
import { EmptyState } from './EmptyState'
import { FeedbackChip, type FeedbackRating } from './FeedbackChip'
import { Stickers } from './Stickers'
import { FlowCard } from './FlowCard'
import { NotesList, ChangeDatesButton } from './NotesList'
import { Typing, NarratePill } from './Indicators'
import { EmailCard, FileCard, HelpCard, TicketCard } from './ResultCards'
import { DataCardFrame, DataFollowup, EmptyCardLine } from './datacards/primitives'
import { RichText } from './RichText'

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/**
 * Cycle a narrate pill through `steps` at `stepMs` until `pending` settles.
 * Caller shows steps[0] before starting the fetch; this advances (wrapping to 0)
 * while the promise is still pending, then returns promptly — no post-sequence
 * tail delay. CHO-251.
 */
async function cycleNarration(
  narrId: string,
  steps: readonly string[],
  pending: Promise<unknown>,
  updateCaption: (id: string, caption: string) => void,
  stepMs = 720,
): Promise<void> {
  if (steps.length === 0) return
  let settled = false
  const untilDone = pending.then(
    () => {
      settled = true
      return 'done' as const
    },
    () => {
      settled = true
      return 'done' as const
    },
  )
  let i = 0
  for (;;) {
    const winner = await Promise.race([delay(stepMs).then(() => 'tick' as const), untilDone])
    if (winner === 'done' || settled) return
    i = (i + 1) % steps.length
    if (settled) return
    updateCaption(narrId, steps[i])
  }
}

/** A flow is live when it has a backend binding (P&L/Ledger/Tax) or a selection
 *  slot (Contract Notes drives its own list + download calls, not the generic
 *  delivery step). `comingSoon` still forces the stub. */
function isLive(descriptor: FlowDescriptor): boolean {
  if (descriptor.comingSoon) return false
  return (
    descriptor.backend !== undefined ||
    descriptor.slots.some((slot) => slot.type === 'selection')
  )
}

/**
 * The chat shell — one continuous conversation (report-chat-shell). The empty
 * state (greeting + stickers) collapses on first engagement; messages append
 * and auto-scroll; the composer is pinned and keyword-routes to a flow. Runs
 * the descriptor-driven engine inline and wires P&L to the backend.
 */
export function ChatShell({
  session,
  firstName,
  onEngaged,
}: Readonly<{
  session: SessionContext
  firstName: string | null
  /** Fired when the conversation kicks off (sticker tap or first submit) —
   *  the header swaps What's New for Restart (CHO-216). */
  onEngaged?: () => void
}>) {
  const [messages, setMessages] = useState<Message[]>([])
  const [phase, setPhase] = useState<'empty' | 'collapsing' | 'chat'>('empty')
  const scrollRef = useRef<HTMLDivElement>(null)
  // Flow message ids whose selection step has already been fetched (fetch once,
  // re-armed when the date is edited). Keeps the effect below idempotent.
  const selectionStarted = useRef<Set<string>>(new Set())

  // Auto-scroll to the newest message.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, phase])

  // Drive the selection step: when a flow's active step becomes a selection
  // slot (Contract Notes, once the date is picked), fetch the list once and
  // render the tap-to-get UI as its own messages.
  useEffect(() => {
    for (const m of messages) {
      if (m.kind !== 'flow') continue
      const descriptor = getFlow(m.run.flowKey)
      if (!descriptor) continue
      const activeSlot = descriptor.slots.find((s) => s.key === m.run.active)
      if (activeSlot?.type === 'selection' && !selectionStarted.current.has(m.id)) {
        selectionStarted.current.add(m.id)
        void runSelection(descriptor, m.id, m.run.values, activeSlot)
      }
    }
    // runSelection is a stable closure over the imperative helpers below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages])

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
    onEngaged?.()
  }

  /* ── entry points ───────────────────────────────────────────────────── */

  function runFlowBody(descriptor: FlowDescriptor) {
    if (!isLive(descriptor)) {
      bot(
        `That one's coming in the next update — I'm still wiring it up. Right now I can pull your **P&L** live:`,
      )
      append({ id: nextId(), kind: 'actions' })
      return
    }
    bot(descriptor.intro)
    append({ id: nextId(), kind: 'flow', run: startRun(descriptor) })
  }

  /** Zero-slot data flow: intro line → narrated fetch → the card. */
  function runDataFlowBody(descriptor: DataFlowDescriptor) {
    bot(descriptor.intro)
    void generateData(descriptor)
  }

  /** Sticker tap (file or data flow). */
  function startFromSticker(descriptor: AnyFlowDescriptor) {
    engage()
    user(descriptor.trigger)
    botThen(() =>
      isDataFlow(descriptor) ? runDataFlowBody(descriptor) : runFlowBody(descriptor),
    )
  }

  /** Composer submit → the agent first (free text is the agent's job;
   *  keyword routing survives only as the AGENT_UNAVAILABLE fallback). */
  function onSend(text: string) {
    engage()
    user(text)
    void runAgent(text)
  }

  /** The pre-agent behavior: keyword-route (data flows first, then file
   *  flows), else offer the sticker row. Now the degraded fallback. */
  function routeByKeyword(text: string) {
    const flow: AnyFlowDescriptor | null = matchDataFlow(text) ?? matchFlow(text)
    if (flow) {
      if (isDataFlow(flow)) runDataFlowBody(flow)
      else runFlowBody(flow)
    } else {
      bot(
        'I can show your holdings, money in/out and brokerage, or pull your P&L, ledger, capital gains and contract notes — tap one:',
      )
      append({ id: nextId(), kind: 'actions' })
    }
  }

  /* ── agent path (free text → POST /api/chat SSE) ────────────────────── */

  /** In-flight agent stream — superseded (aborted) by the next submit. */
  const agentAbort = useRef<AbortController | null>(null)

  // Restart remounts the shell (CHO-216) — a stream must not outlive it.
  useEffect(() => () => agentAbort.current?.abort(), [])

  /**
   * Stream one agent exchange: typing dots until the first event, text
   * deltas growing an in-place bot message, tool rounds as a progress pill,
   * artifacts through the existing file/data cards. AGENT_UNAVAILABLE falls
   * back to keyword routing for the same text; AUTH_EXPIRED uses the shell's
   * session-expired copy.
   */
  async function runAgent(text: string) {
    agentAbort.current?.abort()
    const controller = new AbortController()
    agentAbort.current = controller

    let indicatorId: string | null = nextId()
    append({ id: indicatorId, kind: 'typing' })
    let streamId: string | null = null // the currently-growing agent message
    let rendered = false // any text/artifact on screen yet?
    // This exchange's answer messages: artifact cards + the LAST text bubble
    // (mid-stream bubbles never carry chips). Stamped with done.lastSeq so
    // their feedback chips anchor to exactly this exchange (CHO-217).
    const answerIds: string[] = []
    let lastBubbleId: string | null = null

    const clearIndicator = () => {
      if (indicatorId !== null) {
        remove(indicatorId)
        indicatorId = null
      }
    }
    const showProgress = (caption: string) => {
      clearIndicator()
      indicatorId = nextId()
      append({ id: indicatorId, kind: 'narrate', caption })
    }

    await streamAgentChat(
      text,
      session,
      {
        onText: (delta) => {
          clearIndicator()
          rendered = true
          if (streamId === null) {
            streamId = nextId()
            lastBubbleId = streamId
            append({ id: streamId, kind: 'agent', text: delta })
          } else {
            appendAgentDelta(streamId, delta)
          }
        },
        onTool: (ev) => {
          // Text after a tool round is a fresh assistant message → new bubble.
          streamId = null
          if (ev.status === 'started') showProgress(toolCaption(ev.name))
          // 'finished' keeps the pill up; the next text/artifact replaces it.
        },
        onArtifact: (artifact) => {
          clearIndicator()
          streamId = null
          rendered = true
          renderAgentArtifact(artifact, (id) => answerIds.push(id))
        },
        onDone: (ev) => {
          clearIndicator()
          stampAnchor(
            ev.thread.lastSeq,
            lastBubbleId === null ? answerIds : [...answerIds, lastBubbleId],
          )
          // Defensive: an empty reply must never leave dead air.
          if (!rendered) routeByKeyword(text)
        },
        onError: (code) => {
          clearIndicator()
          if (code === 'AUTH_EXPIRED') {
            handleAuthExpired('agent') // notify the host once (CHO-231)
            bot(errorLine('AUTH_EXPIRED')) // the shell's session-expired copy
            return
          }
          // AGENT_UNAVAILABLE → degraded mode: the pre-agent keyword routing.
          if (!rendered) routeByKeyword(text)
          else bot(agentInterruptLine())
        },
      },
      controller.signal,
    )
    // A superseded (aborted) stream fires no callbacks — drop its indicator.
    if (controller.signal.aborted) clearIndicator()
  }

  function appendAgentDelta(msgId: string, delta: string) {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId && m.kind === 'agent' ? { ...m, text: m.text + delta } : m)),
    )
  }

  /* ── answer feedback (CHO-217) ──────────────────────────────────────── */

  /** Can this message carry a feedback chip? (Narrowing helper for TS.) */
  function isRatable(
    m: Message,
  ): m is Extract<Message, { kind: 'agent' | 'download' | 'email' | 'datacard' }> {
    return m.kind === 'agent' || m.kind === 'download' || m.kind === 'email' || m.kind === 'datacard'
  }

  /** Stamp the exchange's `done.lastSeq` onto the answer messages it just
   *  rendered — one exchange, one anchor: the chip on any of them rates the
   *  same feedback row. */
  function stampAnchor(anchorSeq: number, ids: string[]) {
    if (anchorSeq <= 0 || ids.length === 0) return
    const idSet = new Set(ids)
    setMessages((prev) =>
      prev.map((m) => (idSet.has(m.id) && isRatable(m) ? { ...m, anchorSeq } : m)),
    )
  }

  /** Optimistic rating + fire-and-forget submit (design D2): the chip
   *  reflects the tap immediately; a lost rating never surfaces an error. */
  function handleRate(msgId: string, rating: FeedbackRating) {
    const msg = messages.find((m) => m.id === msgId)
    if (!msg || !isRatable(msg) || msg.feedback === rating) return
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId && isRatable(m) ? { ...m, feedback: rating } : m)),
    )
    if (!hasCredentials(session)) return
    // Agent-path messages carry the exchange anchor; sticker-path cards have
    // none — the backend then anchors to the thread's latest turn.
    const stickerSource = msg.kind === 'datacard' ? 'data' : 'flow'
    const source =
      msg.kind === 'agent' || msg.anchorSeq !== undefined ? 'agent' : stickerSource
    void fetch('/api/feedback', {
      method: 'POST',
      headers: { ...authHeaders(session), 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating, anchorSeq: msg.anchorSeq, source }),
    }).catch(() => {}) // silent failure by design
  }

  /** Render an artifact event through the EXISTING result renderers.
   *  The model is silent after artifact rounds (CHO-215) — any connective
   *  copy is rendered HERE, deterministically: zero tokens, and this code
   *  actually knows the layout. `onAnswer` collects the ids of the answer
   *  messages (file/data cards) so onDone can stamp the feedback anchor. */
  function renderAgentArtifact(artifact: AgentArtifact, onAnswer: (id: string) => void) {
    if (artifact.kind === 'file') {
      bot('Your report is ready:')
      // Same card + /api/report/file/{token} mechanics as the report flows.
      const descriptor = artifact.flowKey !== undefined ? getFlow(artifact.flowKey) : undefined
      const cardId = nextId()
      onAnswer(cardId)
      append({
        id: cardId,
        kind: 'download',
        flowKey: artifact.flowKey ?? '',
        values: {},
        file: artifact.file,
        fileToken: artifact.fileToken,
        passwordNote: descriptor?.result.passwordNote ?? null,
        helpKind: descriptor?.result.helpKind ?? 'pdf',
        // "Email it" replays a slot-filled flow; the agent card has no slot
        // values to replay — delivery changes go back through chat instead.
        emailable: false,
      })
      return
    }
    if (artifact.kind === 'ticket') {
      // A raised support ticket (CHO-218): the same confirmation card the
      // help-card path renders, with the REAL Freshdesk id.
      append({ id: nextId(), kind: 'ticket', ticketId: String(artifact.ticketId) })
      return
    }
    if (artifact.kind === 'flow') {
      // Form handover (CHO-214): boot the guided FlowCard seeded with the
      // re-validated values; the engine asks the first unfilled gap. The
      // agent's own streamed line is the intro — no extra bot copy here.
      const parsed = parseFlowArtifact(artifact)
      if (parsed === null) return
      const descriptor = getFlow(parsed.flowKey)
      if (!descriptor || !isLive(descriptor)) return
      // Deterministic handoff line: the sticker intro for an unseeded form,
      // a "finish it" line when values are pre-filled.
      bot(
        Object.keys(parsed.seed).length === 0
          ? descriptor.intro
          : "Here you go — fill in the rest and it's on its way.",
      )
      append({
        id: nextId(),
        kind: 'flow',
        run: startRun(descriptor, parsed.seed),
        preferredDelivery: parsed.preferredDelivery,
      })
      return
    }
    const parsed = parseDataArtifact(artifact)
    if (parsed === null) return // unknown tool — the agent's text narrates
    if (parsed.kind === 'error') {
      // Malformed payload degrades exactly like the deterministic flow would.
      bot(dataErrorLine(parsed.code, getDataFlow(parsed.flowKey)?.errorNoun ?? 'that'))
      return
    }
    if (parsed.kind === 'empty') {
      append({ id: nextId(), kind: 'dataEmpty', flowKey: parsed.flowKey })
      return
    }
    const cardId = nextId()
    onAnswer(cardId)
    append({ id: cardId, kind: 'datacard', flowKey: parsed.flowKey, data: parsed.data })
    if (getDataFlow(parsed.flowKey)?.followup) {
      append({ id: nextId(), kind: 'dataFollowup', flowKey: parsed.flowKey })
    }
  }

  /* ── slot interactions ──────────────────────────────────────────────── */

  function handlePick(msgId: string, descriptor: FlowDescriptor, slotKey: string, value: SlotValue) {
    updateRun(msgId, (run) => fillSlot(descriptor, run, slotKey, value))
  }
  function handleEdit(msgId: string, slotKey: string) {
    const flowMsg = messages.find((m) => m.id === msgId)
    updateRun(msgId, (run) => editSlot(run, slotKey))
    const descriptor = flowMsg?.kind === 'flow' ? getFlow(flowMsg.run.flowKey) : undefined
    if (descriptor?.slots.some((s) => s.type === 'selection')) {
      // Editing the date invalidates the fetched list below — drop everything
      // after the flow card and re-arm the fetch for the next range.
      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === msgId)
        return idx === -1 ? prev : prev.slice(0, idx + 1)
      })
      selectionStarted.current.delete(msgId)
    }
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

    // Fetch and narration run in parallel; captions cycle until the response
    // resolves so a slow fetch never freezes on the last step (CHO-251).
    const resultP: Promise<ReportResult> = descriptor.backend
      ? submitReport(descriptor.backend, values, mode, session)
      : Promise.resolve({ kind: 'error', code: 'UPSTREAM_ERROR' })

    await cycleNarration(narrId, steps, resultP, updateCaption)
    const result = await resultP
    remove(narrId)
    renderResult(descriptor, values, result)
  }

  /** Data-flow generation: narrated wait + fetch overlapped, then the card
   *  (or the calm empty state / graceful error line). */
  async function generateData(descriptor: DataFlowDescriptor) {
    const narrId = nextId()
    append({ id: narrId, kind: 'narrate', caption: descriptor.narration[0] })

    const resultP = descriptor.fetch(session)
    await cycleNarration(narrId, descriptor.narration, resultP, updateCaption)
    const result = await resultP
    remove(narrId)

    if (result.kind === 'error') {
      if (result.code === 'auth_expired') handleAuthExpired('data') // CHO-231
      bot(dataErrorLine(result.code, descriptor.errorNoun))
      return
    }
    if (result.kind === 'empty') {
      append({ id: nextId(), kind: 'dataEmpty', flowKey: descriptor.key })
      return
    }
    append({ id: nextId(), kind: 'datacard', flowKey: descriptor.key, data: result.data })
    if (descriptor.followup) {
      append({ id: nextId(), kind: 'dataFollowup', flowKey: descriptor.key })
    }
  }

  /** CHO-248: re-run a refreshable data flow (holdings) for fresher prices,
   *  appending a fresh card below as a continuation. */
  function handleRefreshData(flowKey: string) {
    const descriptor = getDataFlow(flowKey)
    if (descriptor) void generateData(descriptor)
  }

  /** CHO-256: spawn a FRESH seeded flow card below a NO-DATA report result so
   *  the user can pick a different range and run it again — the earlier message
   *  stays as history (spawn-fresh-below), never mutated in place. Guided-flow
   *  reports only (they carry the attempted slot values to seed). */
  function handleAdjustRerun(flowKey: string, values: FilledValues) {
    const descriptor = getFlow(flowKey)
    if (!descriptor) return
    bot('Sure — tweak anything and send it again.')
    append({ id: nextId(), kind: 'flow', run: startRun(descriptor, values) })
  }

  function renderResult(
    descriptor: FlowDescriptor,
    values: FlowRun['values'],
    result: ReportResult,
  ) {
    if (result.kind === 'error') {
      if (result.code === 'AUTH_EXPIRED') handleAuthExpired('report') // CHO-231
      bot(errorLine(result.code))
      // CHO-256: a no-data result offers a fresh "try a different range" flow;
      // AUTH_EXPIRED / generic errors keep text-only remediation (a range
      // change does not resolve them).
      if (result.code === 'NO_DATA') {
        append({ id: nextId(), kind: 'reportRetry', flowKey: descriptor.key, values })
      }
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
      ttlSeconds: result.ttlSeconds,
      expiresAt: result.expiresAt,
      passwordNote: descriptor.result.passwordNote,
      helpKind: descriptor.result.helpKind,
    })
  }

  /* ── contract-notes selection step (list → tap → download) ──────────── */

  async function runSelection(
    descriptor: FlowDescriptor,
    flowMsgId: string,
    values: FilledValues,
    slot: SelectionSlot,
  ) {
    const range = values['range'] as DateRangeValue | undefined
    if (range?.type !== 'date') return

    const narration = descriptor.narration.length > 0 ? descriptor.narration : ['Looking up your notes…']
    const narrId = nextId()
    append({ id: narrId, kind: 'narrate', caption: narration[0] })

    const listP = fetchContractNotes(slot.source.endpoint, range.fromDate, range.toDate, session)
    await cycleNarration(narrId, narration, listP, updateCaption)
    const result = await listP
    remove(narrId)

    if (result.kind === 'error') {
      if (result.code === 'AUTH_EXPIRED') handleAuthExpired('report') // CHO-231
      bot(errorLine(result.code))
      append({ id: nextId(), kind: 'notesAction', flowMsgId, label: 'Change dates' })
      return
    }
    if (result.notes.length === 0) {
      bot(`I couldn't find any contract notes for **${range.label}**. Want to try a different date range?`)
      append({ id: nextId(), kind: 'notesAction', flowMsgId, label: 'Change dates' })
      return
    }
    if (result.notes.length === 1) {
      // Single-note shortcut: skip the list, download the one note directly.
      await deliverNote(descriptor, slot.source.download, result.notes[0], true)
      return
    }
    bot(`Found **${result.notes.length}** contract notes for **${range.label}** — tap any to get it here.`)
    append({
      id: nextId(),
      kind: 'notesList',
      flowMsgId,
      downloadEndpoint: slot.source.download,
      notes: result.notes,
    })
  }

  async function deliverNote(
    descriptor: FlowDescriptor,
    downloadEndpoint: string,
    note: ClientNote,
    single: boolean,
  ) {
    const result = await downloadContractNote(downloadEndpoint, note.id, session)
    if (result.kind === 'error') {
      if (result.code === 'AUTH_EXPIRED') handleAuthExpired('report') // CHO-231
      bot(errorLine(result.code))
      return
    }
    const segment = note.segment ? ` (${note.segment})` : ''
    bot(`Here's your contract note for **${note.date}**${single ? '' : segment} ✓`)
    append({
      id: nextId(),
      kind: 'download',
      flowKey: descriptor.key,
      values: {},
      file: result.file,
      fileToken: result.fileToken,
      ttlSeconds: result.ttlSeconds,
      expiresAt: result.expiresAt,
      source: 'contract-note',
      passwordNote: descriptor.result.passwordNote,
      helpKind: descriptor.result.helpKind,
      emailable: false, // contract notes have no email delivery
    })
    // CHO-255: a delivered note is a success — no "Change dates" affordance here
    // (it belongs only on the empty/error result).
  }

  function handleNoteTap(flowMsgId: string, downloadEndpoint: string, note: ClientNote) {
    const flowMsg = messages.find((m) => m.id === flowMsgId)
    const descriptor = flowMsg?.kind === 'flow' ? getFlow(flowMsg.run.flowKey) : undefined
    if (!descriptor) return
    void deliverNote(descriptor, downloadEndpoint, note, false)
  }

  function handleChangeDates(flowMsgId: string) {
    const flowMsg = messages.find((m) => m.id === flowMsgId)
    const descriptor = flowMsg?.kind === 'flow' ? getFlow(flowMsg.run.flowKey) : undefined
    if (!descriptor) return
    // CHO-255: start a FRESH flow as a new message (its own intro + a new date
    // prompt) rather than re-opening the empty/error card's date step in place.
    runFlowBody(descriptor)
  }

  /* ── result-card actions ────────────────────────────────────────────── */

  function handleDownload(
    fileToken: string,
    file: FileInfo,
    ttlSeconds?: number,
    expiresAt?: string,
    source: 'report' | 'contract-note' = 'report',
  ) {
    // Native host first (CHO-230): hand the file to Android via the bridge.
    // No bridge → the browser download stays the web fallback.
    if (sendFileToHost(fileToken, file, { source, ttlSeconds, expiresAt })) return
    void downloadReportFile(fileToken, file.name)
  }
  function handleEmailIt(flowKey: string, values: FlowRun['values']) {
    const descriptor = getFlow(flowKey)
    if (!descriptor) return
    user('Email it to me')
    void generate(descriptor, values, 'email')
  }
  function openHelp(kind: HelpKind) {
    botThen(() => {
      bot(helpIntro(kind))
      append({ id: nextId(), kind: 'help', helpKind: kind })
    }, 420)
  }
  function handleResend() {
    user('Resend it')
    botThen(() => bot('Resent — check again in a minute.'))
  }
  /** Help-card escalation (CHO-218): a REAL Freshdesk ticket via
   *  POST /api/ticket. Busy pill while in flight; on failure a graceful
   *  line — the help card stays on screen, so the action remains available. */
  async function handleRaiseTicket() {
    user('Raise a ticket')
    const narrId = nextId()
    append({ id: narrId, kind: 'narrate', caption: 'Raising your ticket…' })
    const fail = () => {
      remove(narrId)
      bot("Couldn't raise the ticket just now — mind trying again in a moment?")
    }
    if (!hasCredentials(session)) {
      fail()
      return
    }
    try {
      const res = await fetch('/api/ticket', {
        method: 'POST',
        headers: { ...authHeaders(session), 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'General Query' }),
      })
      if (!res.ok) {
        fail()
        return
      }
      const data = (await res.json()) as { ticketId?: unknown }
      const ticketId = data.ticketId
      if (typeof ticketId !== 'string' && typeof ticketId !== 'number') {
        fail()
        return
      }
      remove(narrId)
      append({ id: nextId(), kind: 'ticket', ticketId: String(ticketId) })
    } catch {
      fail()
    }
  }

  /* ── render ─────────────────────────────────────────────────────────── */

  return (
    <>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
        <div className="flex min-h-full flex-col gap-3 pt-14 px-4 pb-4">
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
              session={session}
              onPick={handlePick}
              onEdit={handleEdit}
              onDeliver={handleDeliver}
              onSticker={startFromSticker}
              onDownload={handleDownload}
              onEmailIt={handleEmailIt}
              onHelp={openHelp}
              onRefreshData={handleRefreshData}
              onAdjustRerun={handleAdjustRerun}
              onResend={handleResend}
              onRaiseTicket={handleRaiseTicket}
              onNoteTap={handleNoteTap}
              onChangeDates={handleChangeDates}
              onRate={handleRate}
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
  session,
  onPick,
  onEdit,
  onDeliver,
  onSticker,
  onDownload,
  onEmailIt,
  onHelp,
  onRefreshData,
  onAdjustRerun,
  onResend,
  onRaiseTicket,
  onNoteTap,
  onChangeDates,
  onRate,
}: Readonly<{
  message: Message
  session: SessionContext
  onPick: (msgId: string, descriptor: FlowDescriptor, slotKey: string, value: SlotValue) => void
  onEdit: (msgId: string, slotKey: string) => void
  onDeliver: (msgId: string, descriptor: FlowDescriptor, run: FlowRun, mode: DeliveryMode) => void
  onSticker: (descriptor: AnyFlowDescriptor) => void
  onDownload: (fileToken: string, file: FileInfo, ttlSeconds?: number, expiresAt?: string, source?: 'report' | 'contract-note') => void
  onEmailIt: (flowKey: string, values: FlowRun['values']) => void
  onHelp: (kind: HelpKind) => void
  onRefreshData: (flowKey: string) => void
  onAdjustRerun: (flowKey: string, values: FilledValues) => void
  onResend: () => void
  onRaiseTicket: () => void
  onNoteTap: (flowMsgId: string, downloadEndpoint: string, note: ClientNote) => void
  onChangeDates: (flowMsgId: string) => void
  onRate: (msgId: string, rating: FeedbackRating) => void
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
    case 'agent':
      // Streamed reply — same look as `bot`, pre-wrap so the model's line
      // breaks and paragraphs survive (raw markdown beyond ** is not sent).
      // The chip appears only once done.lastSeq is stamped — exchange-final
      // bubbles only, never mid-stream text (CHO-217).
      return (
        <div className="flex flex-col gap-1.5">
          <p className="text-[14.5px] leading-normal whitespace-pre-wrap text-zinc-800 dark:text-zinc-100">
            <RichText text={m.text} />
          </p>
          {m.anchorSeq !== undefined && (
            <FeedbackChip rating={m.feedback} onRate={(rating) => onRate(m.id, rating)} />
          )}
        </div>
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
          preferredDelivery={m.preferredDelivery}
          onPick={(slotKey, value) => onPick(m.id, descriptor, slotKey, value)}
          onEdit={(slotKey) => onEdit(m.id, slotKey)}
          onDeliver={(mode) => onDeliver(m.id, descriptor, m.run, mode)}
        />
      )
    }
    case 'download':
      return (
        <div className="flex flex-col gap-1.5">
          <FileCard
            file={m.file}
            passwordNote={m.passwordNote}
            emailable={m.emailable ?? true}
            onDownload={() => onDownload(m.fileToken, m.file, m.ttlSeconds, m.expiresAt, m.source)}
            onEmailIt={() => onEmailIt(m.flowKey, m.values)}
            onHelp={() => onHelp(m.helpKind)}
          />
          <FeedbackChip rating={m.feedback} onRate={(rating) => onRate(m.id, rating)} />
        </div>
      )
    case 'email':
      return (
        <div className="flex flex-col gap-1.5">
          <EmailCard noun={m.noun} emailMasked={m.emailMasked} onHelp={() => onHelp('email')} />
          <FeedbackChip rating={m.feedback} onRate={(rating) => onRate(m.id, rating)} />
        </div>
      )
    case 'notesList':
      return (
        <NotesList
          notes={m.notes}
          onPick={(note) => onNoteTap(m.flowMsgId, m.downloadEndpoint, note)}
        />
      )
    case 'notesAction':
      return <ChangeDatesButton label={m.label} onClick={() => onChangeDates(m.flowMsgId)} />
    case 'reportRetry':
      // CHO-256: no-data report → a calendar pill (like contract notes) that
      // spawns a fresh seeded flow to try a different range.
      return (
        <ChangeDatesButton
          label="Try a different range"
          onClick={() => onAdjustRerun(m.flowKey, m.values)}
        />
      )
    case 'help':
      return <HelpCard helpKind={m.helpKind} onResend={onResend} onRaiseTicket={onRaiseTicket} />
    case 'ticket':
      return <TicketCard ticketId={m.ticketId} />
    case 'datacard': {
      const descriptor = getDataFlow(m.flowKey)
      if (!descriptor) return null
      const Card = descriptor.Card
      return (
        <div className="flex flex-col gap-1.5">
          <Card data={m.data} session={session} />
          <FeedbackChip rating={m.feedback} onRate={(rating) => onRate(m.id, rating)} />
        </div>
      )
    }
    case 'dataEmpty': {
      const descriptor = getDataFlow(m.flowKey)
      if (!descriptor) return null
      return (
        <DataCardFrame>
          <EmptyCardLine>{descriptor.emptyLine}</EmptyCardLine>
        </DataCardFrame>
      )
    }
    case 'dataFollowup': {
      const descriptor = getDataFlow(m.flowKey)
      if (!descriptor?.followup) return null
      return (
        <DataFollowup
          text={descriptor.followup.text}
          linkLabel={descriptor.followup.linkLabel}
          onClick={() => onHelp(descriptor.helpKind)}
          onRefresh={descriptor.refreshable ? () => onRefreshData(m.flowKey) : undefined}
        />
      )
    }
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
        aria-label="Ask AskFinX"
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
