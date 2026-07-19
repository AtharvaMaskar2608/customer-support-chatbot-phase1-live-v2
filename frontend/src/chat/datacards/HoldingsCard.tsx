/**
 * The portfolio card (holdings-flow) — the answer lives IN the chat.
 *
 * Anatomy per the approved prototype (.hcard): hero (count-up value ·
 * holding count · Invested subline · 1D + Overall pills · freshness line) →
 * animated allocation bar (top-5 colored + gray Other lump) + legend →
 * top-4 expandable rows → "Show all n" → quiet footer (refresh copy +
 * Download CSV with on-button feedback).
 *
 * Time honesty: the pill is "1D", never "Today"; the freshness stamp comes
 * from the API's own asOf. Facts only — concentrations and losses render as
 * numbers, never advice.
 */

import { useRef, useState } from 'react'
import { CheckIcon, DownloadIcon } from '../../icons'
import type { DataCardProps } from '../../flow/dataflow'
import type { HoldingRow, HoldingsData } from './holdings'
import { downloadHoldingsCsv } from './holdingsCsv'
import { formatAsOf, formatInr } from './inr'
import {
  AllocationBar,
  CardFooter,
  CountUpValue,
  DataCardFrame,
  DetailCell,
  DetailGrid,
  ExpandableRow,
  FreshnessLine,
  HeroLabel,
  ShowMoreRow,
  StatPill,
  type AllocationSegment,
} from './primitives'
import { DOWN_TEXT, MINUS, UP_TEXT } from './tokens'

/** Ranked-segment palette (top 5 by current value); the tail is one gray lump. */
const SEG_COLORS = ['#7c3aed', '#2563eb', '#0d9488', '#d97706', '#db2777']
/** Row-dot gray for holdings beyond the top 5 (zinc-400, both themes). */
const DOT_GRAY = '#a1a1aa'

const ROWS_COLLAPSED = 4

export function HoldingsCard({ data, session }: Readonly<DataCardProps>) {
  // Sound narrow: the holdings descriptor pairs this card with fetchHoldings.
  const d = data as HoldingsData
  const [showAll, setShowAll] = useState(false)

  const visible = showAll ? d.rows : d.rows.slice(0, ROWS_COLLAPSED)
  const rest = d.rows.slice(SEG_COLORS.length)
  const segments: AllocationSegment[] = d.rows
    .slice(0, SEG_COLORS.length)
    .map((r, i) => ({ label: r.sym, pct: r.alloc, color: SEG_COLORS[i] }))
  if (rest.length > 0) {
    segments.push({
      label: `Other (${rest.length})`,
      pct: rest.reduce((sum, r) => sum + r.alloc, 0),
      className: 'bg-zinc-200 dark:bg-zinc-700',
    })
  }

  const t = d.totals
  return (
    <DataCardFrame>
      {/* hero */}
      <div className="px-4 pt-[15px] pb-3.5">
        <HeroLabel>
          Portfolio value · {t.count} {t.count === 1 ? 'holding' : 'holdings'}
        </HeroLabel>
        <CountUpValue value={t.current} format={formatInr} />
        <div className="mb-3 text-xs text-zinc-400 dark:text-zinc-500">
          Invested {formatInr(t.invested)}
        </div>
        <div className="flex flex-wrap gap-2">
          <StatPill label="1D" tone={t.day >= 0 ? 'up' : 'down'}>
            {t.day >= 0 ? '▴' : '▾'} {formatInr(t.day)} · {Math.abs(t.dayPct).toFixed(2)}%
          </StatPill>
          <StatPill label="Overall" tone={t.pnl >= 0 ? 'up' : 'down'}>
            {t.pnl >= 0 ? '▴' : '▾'} {formatInr(t.pnl)} · {Math.abs(t.pnlPct).toFixed(1)}%
          </StatPill>
        </div>
        <FreshnessLine>Prices as of {formatAsOf(d.asOf)} — last fetch, not live</FreshnessLine>
      </div>

      {/* allocation */}
      <AllocationBar segments={segments} />
      <Legend rows={d.rows} />

      {/* ranked expandable rows */}
      <div className="mt-[5px]">
        {visible.map((row, i) => (
          <HoldingRowItem key={row.sym} row={row} color={i < SEG_COLORS.length ? SEG_COLORS[i] : DOT_GRAY} />
        ))}
      </div>
      {!showAll && d.rows.length > ROWS_COLLAPSED && (
        <ShowMoreRow
          label={`Show all ${d.rows.length} holdings`}
          onClick={() => setShowAll(true)}
        />
      )}

      {/* quiet footer */}
      <CardFooter>
        <span className="text-[11px] text-zinc-400 dark:text-zinc-500">
          Ask again anytime — prices refetch on every request
        </span>
        <CsvButton rows={d.rows} userCode={session.userId ?? 'CLIENT'} />
      </CardFooter>
    </DataCardFrame>
  )
}

/** "BANKBARODA 50% · NIFTYBEES 24% · +8 more" under the bar. */
function Legend({ rows }: Readonly<{ rows: HoldingRow[] }>) {
  if (rows.length === 0) return null
  const named = rows.slice(0, 2)
  return (
    <p className="mx-4 mt-2 mb-[3px] text-[11px] leading-normal text-zinc-400 dark:text-zinc-500">
      {named.map((r, i) => (
        <span key={r.sym}>
          {i > 0 && ' · '}
          <b className="font-bold text-zinc-600 dark:text-zinc-300">{r.sym}</b> {r.alloc.toFixed(0)}%
        </span>
      ))}
      {rows.length > named.length && ` · +${rows.length - named.length} more`}
    </p>
  )
}

function HoldingRowItem({ row: r, color }: Readonly<{ row: HoldingRow; color: string }>) {
  const up = r.pnl >= 0
  const dayUp = r.day >= 0
  return (
    <ExpandableRow
      row={
        <>
          <div className="min-w-0">
            <div className="flex items-center gap-[7px] text-[13.5px] font-bold">
              <span className="size-2 shrink-0 rounded-full" style={{ background: color }} />
              {r.sym}
            </div>
            <div className="mt-0.5 pl-[15px] text-[11.5px] text-zinc-400 dark:text-zinc-500">
              {r.qty} qty · avg ₹{r.abp.toFixed(2)}
            </div>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-[13.5px] font-bold tabular-nums">{formatInr(r.current)}</div>
            <div className={`mt-0.5 text-[11.5px] font-bold ${up ? UP_TEXT : DOWN_TEXT}`}>
              {up ? '+' : MINUS}
              {Math.abs(r.pnlPct).toFixed(1)}%
            </div>
          </div>
        </>
      }
      detail={
        <DetailGrid>
          <DetailCell k="Invested">{formatInr(r.invested)}</DetailCell>
          <DetailCell k="Current">{formatInr(r.current)}</DetailCell>
          <DetailCell k="Last price">₹{r.ltp.toFixed(2)}</DetailCell>
          <DetailCell k="1D change" className={dayUp ? UP_TEXT : DOWN_TEXT}>
            {dayUp ? '▴' : '▾'} {formatInr(r.day)} · {Math.abs(r.dayPct).toFixed(2)}%
          </DetailCell>
          <DetailCell k="Overall P&L" className={up ? UP_TEXT : DOWN_TEXT}>
            {up ? '+' : MINUS}
            {formatInr(r.pnl)}
          </DetailCell>
          <DetailCell k="Allocation">{r.alloc.toFixed(1)}%</DetailCell>
        </DetailGrid>
      }
    />
  )
}

/**
 * Download-CSV footer action. All feedback happens ON the button
 * (spinner "Saving…" → green ✓ "Saved to downloads" → revert); the filename
 * is never echoed into the conversation.
 */
function CsvButton({
  rows,
  userCode,
}: Readonly<{ rows: readonly HoldingRow[]; userCode: string }>) {
  const [status, setStatus] = useState<'idle' | 'busy' | 'ok'>('idle')
  const busyRef = useRef(false)

  function handleClick() {
    if (busyRef.current) return
    busyRef.current = true
    downloadHoldingsCsv(rows, userCode)
    setStatus('busy')
    setTimeout(() => setStatus('ok'), 520)
    setTimeout(() => {
      setStatus('idle')
      busyRef.current = false
    }, 520 + 1700)
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`inline-flex shrink-0 items-center gap-1.5 text-xs font-semibold ${
        status === 'ok'
          ? 'cursor-default text-online dark:text-online-soft'
          : 'text-accent hover:underline dark:text-accent-soft'
      }`}
    >
      {status === 'idle' && (
        <>
          <DownloadIcon className="size-3.5" /> Download CSV
        </>
      )}
      {status === 'busy' && (
        <>
          <span className="size-2 animate-pulse rounded-full bg-accent" /> Saving…
        </>
      )}
      {status === 'ok' && (
        <>
          <CheckIcon className="size-3.5" /> Saved to downloads
        </>
      )}
    </button>
  )
}
