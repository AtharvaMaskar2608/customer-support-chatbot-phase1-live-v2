/**
 * The money in & out card (money-flow) — ONE passbook timeline, not tabs.
 *
 * Anatomy per the approved prototype (.mcard): header (label + period +
 * status count-chips that double as filters) → merged newest-first rows
 * (direction glyph ↓/↑ + paise-safe amount + meta line; status on the right,
 * success quiet ✓, exceptions carry the word and the color, failed/cancelled
 * dimmed) → first 6 + "Show all n" → landed-only footer totals.
 *
 * The card renders; it does not calculate — counts and landed totals come
 * from the backend. Pay-out's Reason shows verbatim in the wide "Why" cell,
 * displayed, never branched on. Facts only, no advice.
 */

import { useState } from 'react'
import type { DataCardProps } from '../../flow/dataflow'
import { formatInr } from './inr'
import type { MoneyData, MoneyTxn } from './money'
import {
  CardFooter,
  CountChip,
  DataCardFrame,
  DetailCell,
  DetailGrid,
  EmptyCardLine,
  ExpandableRow,
  HeroLabel,
  ShowMoreRow,
} from './primitives'
import { DIRECTION, STATUS_PRESENTATION, type CanonicalStatus } from './tokens'

const ROWS_COLLAPSED = 6

/** Chip order + labels per the prototype ("15 landed · 35 pending · …"). */
const CHIPS: readonly (readonly [CanonicalStatus, string])[] = [
  ['SUCCESS', 'landed'],
  ['PENDING', 'pending'],
  ['FAILURE', 'failed'],
  ['CANCELLED', 'cancelled'],
]

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function MoneyCard({ data }: Readonly<DataCardProps>) {
  // Sound narrow: the money descriptor pairs this card with fetchMoney.
  const d = data as MoneyData
  const [filter, setFilter] = useState<CanonicalStatus | null>(null)
  const [showAll, setShowAll] = useState(false)

  const rows = filter ? d.txns.filter((t) => t.st === filter) : d.txns
  const visible = showAll ? rows : rows.slice(0, ROWS_COLLAPSED)
  const chips = CHIPS.filter(([k]) => d.counts[k] > 0)

  /** Tap filters; tap again clears. Any filter change resets to the first 6. */
  function toggleChip(k: CanonicalStatus) {
    setFilter((prev) => (prev === k ? null : k))
    setShowAll(false)
  }

  return (
    <DataCardFrame>
      {/* header: label + period, status chips-as-filters (non-zero only) */}
      <div className="border-b border-zinc-100 px-4 pt-[13px] pb-3 dark:border-zinc-800">
        <HeroLabel>Money in &amp; out · {periodLabel()}</HeroLabel>
        {chips.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {chips.map(([k, label]) => (
              <CountChip
                key={k}
                count={d.counts[k]}
                label={label}
                dotClass={STATUS_PRESENTATION[k].dotClass}
                active={filter === k}
                onClick={() => toggleChip(k)}
              />
            ))}
          </div>
        )}
      </div>

      {/* one upstream direction failed — show what loaded, say so quietly */}
      {d.partial && (
        <p className="px-4 pt-2.5 pb-0.5 text-[11px] leading-normal text-zinc-400 dark:text-zinc-500">
          {"Couldn't reach one side of the ledger — showing what loaded."}
        </p>
      )}

      {/* merged newest-first timeline */}
      {rows.length === 0 ? (
        <EmptyCardLine>Nothing here.</EmptyCardLine>
      ) : (
        <div>
          {visible.map((t, i) => (
            <MoneyRowItem key={`${t.dt}·${t.dir}·${t.amt}·${t.ref ?? i}`} t={t} />
          ))}
        </div>
      )}
      {!showAll && rows.length > ROWS_COLLAPSED && (
        <ShowMoreRow label={`Show all ${rows.length}`} onClick={() => setShowAll(true)} />
      )}

      {/* landed-only totals — pending/failed never inflate these */}
      <CardFooter>
        <span className="text-[11px] leading-normal text-zinc-400 dark:text-zinc-500">
          Landed this period: {formatInr(d.landed.in)} in · {formatInr(d.landed.out)} out
        </span>
      </CardFooter>
    </DataCardFrame>
  )
}

/** One transaction: direction glyph + amount, meta line, quiet/loud status. */
function MoneyRowItem({ t }: Readonly<{ t: MoneyTxn }>) {
  const dir = DIRECTION[t.dir]
  const st = STATUS_PRESENTATION[t.st]
  const w = parseWhen(t.dt)
  const meta = [w ? `${w.day} ${w.mon}, ${w.hm}` : t.dt, t.mode, t.dest]
    .filter(Boolean)
    .join(' · ')
  return (
    <ExpandableRow
      dim={st.dim}
      row={
        <>
          <div className="min-w-0">
            <div className="flex items-center gap-[7px] text-sm font-bold tabular-nums">
              <span className={`text-xs font-extrabold ${dir.textClass}`}>{dir.glyph}</span>
              {formatInr(t.amt)}
            </div>
            <div className="mt-0.5 text-[11.5px] text-zinc-400 dark:text-zinc-500">{meta}</div>
          </div>
          <div className={`shrink-0 text-[11.5px] font-bold ${st.textClass}`} title={t.st}>
            {st.label}
          </div>
        </>
      }
      detail={
        <DetailGrid>
          <DetailCell k={`${t.dir === 'out' ? 'Withdrawal' : 'Deposit'} requested`}>
            {w ? `${w.day} ${w.mon} ${w.year}, ${w.hm}` : t.dt}
          </DetailCell>
          <DetailCell k="Mode">{t.mode ?? '—'}</DetailCell>
          <DetailCell k={t.dir === 'out' ? 'To your bank' : 'To account'}>
            {t.dest ?? '—'}
          </DetailCell>
          <DetailCell k="Reference">{t.ref ?? '—'}</DetailCell>
          {t.rsn && (
            <DetailCell k="Why" wide>
              {t.rsn}
            </DetailCell>
          )}
        </DetailGrid>
      }
    />
  )
}

/**
 * String-parse the ISO stamp (timezone-proof — the wall-clock time upstream
 * recorded is the truth to show): "2026-07-08T16:19:45" → 8 Jul, 4:19 pm.
 * Null when malformed; callers fall back to the raw string.
 */
function parseWhen(dt: string): { day: number; mon: string; year: number; hm: string } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(dt)
  if (!m) return null
  const [, y, mo, day, hRaw, mi] = m
  const monIdx = Number(mo) - 1
  if (monIdx < 0 || monIdx > 11) return null
  let h = Number(hRaw)
  const ap = h >= 12 ? 'pm' : 'am'
  h = h % 12 || 12
  return { day: Number(day), mon: MON[monIdx], year: Number(y), hm: `${h}:${mi} ${ap}` }
}

/**
 * The card's period: financial-year-to-date, matching the backend's default
 * window (FromDate = FY start, ToDate = today + 7 — the FinX app's own
 * range). "1 Apr – 25 Jul"; years appear only when the span crosses one.
 */
function periodLabel(now = new Date()): string {
  const fyStartYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 7)
  const sameYear = fyStartYear === end.getFullYear()
  const start = sameYear ? '1 Apr' : `1 Apr ${fyStartYear}`
  const endLabel = `${end.getDate()} ${MON[end.getMonth()]}${sameYear ? '' : ` ${end.getFullYear()}`}`
  return `${start} – ${endLabel}`
}
