/**
 * The brokerage rate card (brokerage-flow) — a pricing reference, never
 * charges billed.
 *
 * CHO-259 anatomy: segment accordion (Equity → Derivative → Commodity →
 * Currency) with FinX 22px colour tiles, ₹-primary rate lines, and a
 * statutory-charges footer. Equity expands by default; panels toggle
 * independently. Unparseable desc shows upstream text verbatim per line.
 */

import { useState, type ReactNode, type SVGProps } from 'react'
import type { DataCardProps } from '../../flow/dataflow'
import {
  orderBrokerageGroups,
  parseRate,
  rateDisplay,
  type BrokerageData,
  type BrokerageGroup,
  type BrokerageItem,
} from './brokerageCluster'
import { DataCardFrame } from './primitives'

const SEGMENT_TILE: Record<string, { bg: string; fg: string }> = {
  Equity: { bg: '#E8F0FE', fg: '#1D4FB8' },
  Derivative: { bg: '#F0EBFE', fg: '#6941C6' },
  Commodity: { bg: '#FEF4E6', fg: '#B76E00' },
  Currency: { bg: '#E9F9F0', fg: '#17B26A' },
}

const NEUTRAL_TILE = { bg: '#F4F4F5', fg: '#71717A' }

export function BrokerageCard({ data }: Readonly<DataCardProps>) {
  const d = data as BrokerageData
  const groups = orderBrokerageGroups(d.groups)
  const defaultKey = groups.some((g) => g.title === 'Equity')
    ? 'Equity'
    : (groups[0]?.title ?? null)

  const [open, setOpen] = useState<ReadonlySet<string>>(() =>
    defaultKey ? new Set([defaultKey]) : new Set(),
  )

  function toggle(title: string) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(title)) next.delete(title)
      else next.add(title)
      return next
    })
  }

  return (
    <DataCardFrame>
      {groups.map((g) => (
        <SegmentPanel
          key={g.title}
          group={g}
          expanded={open.has(g.title)}
          onToggle={() => toggle(g.title)}
        />
      ))}

      <div className="border-t border-zinc-100 px-4 py-[11px] text-[11px] leading-normal text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
        Plus statutory charges (STT, exchange fees, GST, stamp duty). These are your plan&rsquo;s
        rates — a trade&rsquo;s actual charges are on its contract note.
      </div>
    </DataCardFrame>
  )
}

function SegmentPanel({
  group,
  expanded,
  onToggle,
}: Readonly<{ group: BrokerageGroup; expanded: boolean; onToggle: () => void }>) {
  const tile = SEGMENT_TILE[group.title] ?? NEUTRAL_TILE
  const count = group.list.length
  const rateLabel = count === 1 ? '1 rate' : `${count} rates`

  return (
    <div className="border-t border-zinc-100 first:border-t-0 dark:border-zinc-800">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left"
      >
        <span
          className="inline-flex size-[22px] shrink-0 items-center justify-center rounded-md"
          style={{ backgroundColor: tile.bg, color: tile.fg }}
          aria-hidden
        >
          <SegmentIcon title={group.title} className="size-3" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12px] font-bold tracking-[0.06em] text-zinc-800 uppercase dark:text-zinc-100">
            {group.title}
          </span>
          <span className="mt-0.5 block text-[11px] text-zinc-400 dark:text-zinc-500">
            {rateLabel}
          </span>
        </span>
        <ChevronIcon open={expanded} className="size-4 shrink-0 text-zinc-400 dark:text-zinc-500" />
      </button>

      {expanded && (
        <div>
          {group.list.map((it) => (
            <RateRow key={it.title} item={it} />
          ))}
        </div>
      )}
    </div>
  )
}

function RateRow({ item }: Readonly<{ item: BrokerageItem }>) {
  const parsed = parseRate(item.desc)
  const right = parsed ? rateDisplay(parsed) : item.desc
  return (
    <div className="flex items-center justify-between gap-3 border-t border-zinc-100 px-4 py-3 dark:border-zinc-800">
      <div className="min-w-0 text-[13.5px] font-bold">{item.title}</div>
      <div className="shrink-0 text-right text-[13px] font-semibold tabular-nums text-zinc-700 dark:text-zinc-200">
        {right}
      </div>
    </div>
  )
}

function ChevronIcon({ open, className }: Readonly<{ open: boolean; className?: string }>) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      {open ? <path d="M4 10l4-4 4 4" /> : <path d="M4 6l4 4 4-4" />}
    </svg>
  )
}

function SegmentIcon({
  title,
  className,
}: Readonly<{ title: string; className?: string }>): ReactNode {
  const props: SVGProps<SVGSVGElement> = {
    viewBox: '0 0 16 16',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    className,
    'aria-hidden': true,
  }
  switch (title) {
    case 'Equity':
      // line-chart
      return (
        <svg {...props}>
          <path d="M2 12 V3.5" />
          <path d="M2 12 H13.5" />
          <path d="M4 9.5 L7 6.5 L9.5 8.5 L13 4.5" />
        </svg>
      )
    case 'Derivative':
      // bar-chart
      return (
        <svg {...props}>
          <path d="M3.5 12 V7.5" />
          <path d="M8 12 V4" />
          <path d="M12.5 12 V8.5" />
        </svg>
      )
    case 'Commodity':
      // coin
      return (
        <svg {...props}>
          <circle cx="8" cy="8" r="5.25" />
          <path d="M8 5.25 V10.75" />
          <path d="M6.25 6.5 C6.25 5.7 7 5.25 8 5.25 C9 5.25 9.75 5.7 9.75 6.5 C9.75 7.5 6.25 7.75 6.25 8.75 C6.25 9.55 7 10 8 10 C9 10 9.75 9.55 9.75 8.75" />
        </svg>
      )
    case 'Currency':
      // exchange / circular arrows
      return (
        <svg {...props}>
          <path d="M3.5 6.5 A4.5 4.5 0 0 1 12 5.5" />
          <path d="M11 3.5 L12 5.5 L10 6" />
          <path d="M12.5 9.5 A4.5 4.5 0 0 1 4 10.5" />
          <path d="M5 12.5 L4 10.5 L6 10" />
        </svg>
      )
    default:
      return (
        <svg {...props}>
          <circle cx="8" cy="8" r="5.25" />
        </svg>
      )
  }
}
