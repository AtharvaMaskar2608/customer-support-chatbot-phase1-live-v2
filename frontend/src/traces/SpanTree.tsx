/**
 * The execution graph for one turn: agent → llm / tool → retriever, nested by
 * `parent_id`. Each row shows the span type, name, duration and the key
 * metadata for its kind (llm: model + token split; tool: error flag; retriever:
 * chunk count + embedder). A row expands to reveal its masked input/output.
 */

import { useState } from 'react'
import type { Span } from './api'
import { fmtMs, fmtPayload, num, str } from './format'
import { TypePill } from './ui'

type SpanNode = { span: Span; children: SpanNode[] }

function buildTree(spans: Span[]): SpanNode[] {
  const byId = new Map<string, SpanNode>()
  for (const span of spans) byId.set(span.id, { span, children: [] })
  const roots: SpanNode[] = []
  for (const span of spans) {
    const node = byId.get(span.id)
    if (!node) continue
    const parent = span.parent_id ? byId.get(span.parent_id) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  const byOffset = (a: SpanNode, b: SpanNode) =>
    (a.span.offset_ms ?? 0) - (b.span.offset_ms ?? 0)
  roots.sort(byOffset)
  for (const node of byId.values()) node.children.sort(byOffset)
  return roots
}

function MetaLine({ span }: Readonly<{ span: Span }>) {
  const m = span.metadata ?? {}
  const bits: string[] = []
  if (span.type === 'llm') {
    const model = str(m.model)
    if (model) bits.push(model)
    const inTok = num(m.input_tokens)
    const outTok = num(m.output_tokens)
    if (inTok != null || outTok != null) bits.push(`${inTok ?? 0}→${outTok ?? 0} tok`)
    const cacheRead = num(m.cache_read_input_tokens)
    if (cacheRead) bits.push(`cache-read ${cacheRead}`)
    const cacheNew = num(m.cache_creation_input_tokens)
    if (cacheNew) bits.push(`cache-new ${cacheNew}`)
    const stop = str(m.stop_reason)
    if (stop) bits.push(stop)
  } else if (span.type === 'tool') {
    bits.push(m.is_error ? 'error' : 'ok')
    const code = str(m.error_code)
    if (code) bits.push(code)
  } else if (span.type === 'retriever') {
    const ctx = m.retrieval_context
    const outObj = span.output as { count?: unknown } | null
    const count = Array.isArray(ctx)
      ? ctx.length
      : num(outObj?.count)
    if (count != null) bits.push(`${count} chunk${count === 1 ? '' : 's'}`)
    const embedder = str(m.embedder)
    if (embedder) bits.push(embedder)
  }
  if (bits.length === 0) return null
  return (
    <span className="truncate text-[11px] text-zinc-500 dark:text-zinc-400">
      {bits.join(' · ')}
    </span>
  )
}

function Row({ node, depth }: Readonly<{ node: SpanNode; depth: number }>) {
  const { span } = node
  const [open, setOpen] = useState(false)
  const inputText = fmtPayload(span.input)
  const outputText = fmtPayload(span.output)
  const hasIo = inputText.length > 0 || outputText.length > 0
  const isError = span.type === 'tool' && span.metadata?.is_error === true

  return (
    <li>
      <div
        style={{ paddingLeft: `${depth * 16}px` }}
        className="flex items-center gap-2 border-l-2 border-transparent py-1"
      >
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          disabled={!hasIo}
          className="flex min-w-0 flex-1 items-center gap-2 rounded px-1.5 py-1 text-left hover:bg-zinc-100 disabled:cursor-default disabled:hover:bg-transparent dark:hover:bg-zinc-800/70"
        >
          <span className="w-3 shrink-0 text-[10px] text-zinc-400">
            {hasIo ? (open ? '▾' : '▸') : ''}
          </span>
          <TypePill type={span.type} />
          <span
            className={`truncate font-mono text-xs ${isError ? 'text-alert' : 'text-zinc-700 dark:text-zinc-200'}`}
          >
            {span.name}
          </span>
          <MetaLine span={span} />
        </button>
        <span className="shrink-0 font-mono text-[11px] text-zinc-400 tabular-nums dark:text-zinc-500">
          {fmtMs(span.duration_ms)}
        </span>
      </div>

      {open && hasIo && (
        <div
          style={{ marginLeft: `${depth * 16 + 20}px` }}
          className="mb-1 space-y-1.5"
        >
          {inputText && <Payload label="input" text={inputText} />}
          {outputText && <Payload label="output" text={outputText} />}
        </div>
      )}

      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <Row key={child.span.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  )
}

function Payload({ label, text }: Readonly<{ label: string; text: string }>) {
  return (
    <div>
      <div className="mb-0.5 text-[10px] font-semibold tracking-wide text-zinc-400 uppercase">
        {label}
      </div>
      <pre className="max-h-64 overflow-auto rounded-md bg-zinc-100 p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
        {text}
      </pre>
    </div>
  )
}

export function SpanTree({ spans }: Readonly<{ spans: Span[] }>) {
  if (!spans || spans.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">No spans recorded.</p>
    )
  }
  const roots = buildTree(spans)
  return (
    <ul>
      {roots.map((node) => (
        <Row key={node.span.id} node={node} depth={0} />
      ))}
    </ul>
  )
}
