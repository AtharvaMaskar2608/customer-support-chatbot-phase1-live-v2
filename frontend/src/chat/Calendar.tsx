import { useState } from 'react'
import { ChevronLeftIcon, ChevronRightIcon } from '../icons'
import { addYears, DOW, MONTHS_LONG, MONTHS_SHORT, sameDay } from '../flow/dates'

/** Which grid the calendar is showing: days, months of `viewYear`, or years. */
type View = 'day' | 'month' | 'year'

const CELL_BASE = 'rounded-md transition-colors'
const CELL_DISABLED = 'cursor-default text-zinc-300 dark:text-zinc-600'
const CELL_ENABLED =
  'cursor-pointer text-zinc-700 hover:bg-accent-tint hover:text-accent dark:text-zinc-200 dark:hover:bg-accent/20 dark:hover:text-accent-soft'
const CELL_CURRENT = 'outline outline-1 outline-accent-soft'

/** Header caption for the current drill-down level. */
function headerTextFor(view: View, monthYear: string, year: number, years: string): string {
  if (view === 'month') return `${year}`
  if (view === 'year') return years
  return monthYear
}

/** Spoken header label — names the level shown and where tapping leads. */
function headerLabelFor(view: View, monthYear: string, year: number): string {
  if (view === 'month') return `Choosing a month in ${year}. Choose a year instead`
  if (view === 'year') return `Choosing a year. Back to ${monthYear}`
  return `Showing ${monthYear}. Choose a year`
}

/** Footer hint for the current drill-down level / selection step. */
function hintFor(view: View, start: Date | null): string {
  if (view === 'year') return 'Pick a year'
  if (view === 'month') return 'Pick a month'
  return start === null ? 'Pick a start date' : 'Pick an end date'
}

/**
 * Constrained custom-range calendar for the `date` slot. Two taps: start,
 * then end. Enforces the flow's bounds — no date before `minDate`, none after
 * `maxDate` (today + futureDaysCap), and (once a start is picked) none beyond
 * `maxRangeYears` from it. Out-of-bounds days are visibly disabled.
 *
 * The header is a button that drills out to a year grid, then a month grid,
 * so the earliest permitted month is three taps away instead of ~100 chevron
 * taps. Year and month cells are disabled under exactly the bounds that
 * disable days, so no fully-disabled day grid is ever reachable.
 */
export function Calendar({
  minDate,
  maxDate,
  maxRangeYears,
  onSelect,
}: Readonly<{
  minDate: Date
  maxDate: Date
  maxRangeYears?: number
  onSelect: (from: Date, to: Date) => void
}>) {
  const [viewYear, setViewYear] = useState(maxDate.getFullYear())
  const [viewMonth, setViewMonth] = useState(maxDate.getMonth())
  const [view, setView] = useState<View>('day')
  const [start, setStart] = useState<Date | null>(null)

  const today = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate())

  function rangeCapFor(s: Date): Date {
    return maxRangeYears === undefined ? maxDate : addYears(s, maxRangeYears)
  }

  function isDisabled(day: Date): boolean {
    if (day < minDate || day > maxDate) return true
    if (start !== null && !sameDay(day, start)) {
      if (day < start) return true
      if (day > rangeCapFor(start)) return true
    }
    return false
  }

  // The effective selectable window — the same bounds `isDisabled` applies,
  // collapsed to a single interval so the year/month grids can reuse them
  // instead of becoming a third source of truth. Once a start is picked the
  // window is [start, min(maxDate, rangeCapFor(start))]; it is never empty
  // because `start` itself is always inside `minDate`..`maxDate`.
  const cap = start === null ? null : rangeCapFor(start)
  const effMin = start ?? minDate
  const effMax = cap === null || cap > maxDate ? maxDate : cap

  function yearDisabled(y: number): boolean {
    return y < effMin.getFullYear() || y > effMax.getFullYear()
  }

  /** First and last selectable month of an enabled year, inclusive. */
  function monthBoundsFor(y: number): [number, number] {
    return [
      y === effMin.getFullYear() ? effMin.getMonth() : 0,
      y === effMax.getFullYear() ? effMax.getMonth() : 11,
    ]
  }

  function monthDisabled(y: number, m: number): boolean {
    if (yearDisabled(y)) return true
    const [lo, hi] = monthBoundsFor(y)
    return m < lo || m > hi
  }

  function pick(day: Date) {
    if (isDisabled(day)) return
    if (start === null) {
      setStart(day)
      return
    }
    if (day < start) {
      setStart(day)
      return
    }
    onSelect(start, day)
  }

  function pickYear(y: number) {
    if (yearDisabled(y)) return
    const [lo, hi] = monthBoundsFor(y)
    setViewYear(y)
    // Clamp so the month grid never highlights — and the day grid never opens
    // on — a month the new year has disabled.
    setViewMonth(Math.min(Math.max(viewMonth, lo), hi))
    setView('month')
  }

  function pickMonth(m: number) {
    if (monthDisabled(viewYear, m)) return
    setViewMonth(m)
    setView('day')
  }

  function nav(delta: number) {
    let m = viewMonth + delta
    let y = viewYear
    if (m < 0) {
      m = 11
      y -= 1
    } else if (m > 11) {
      m = 0
      y += 1
    }
    setViewMonth(m)
    setViewYear(y)
  }

  const firstDow = new Date(viewYear, viewMonth, 1).getDay()
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()
  const cells: (Date | null)[] = []
  for (let i = 0; i < firstDow; i += 1) cells.push(null)
  for (let d = 1; d <= daysInMonth; d += 1) cells.push(new Date(viewYear, viewMonth, d))

  const years: number[] = []
  for (let y = minDate.getFullYear(); y <= maxDate.getFullYear(); y += 1) years.push(y)

  const monthYearLabel = `${MONTHS_LONG[viewMonth]} ${viewYear}`
  const yearsLabel = `${years[0]}–${years.at(-1)}`
  const headerText = headerTextFor(view, monthYearLabel, viewYear, yearsLabel)
  const headerLabel = headerLabelFor(view, monthYearLabel, viewYear)

  return (
    <div className="mt-3 rounded-xl border border-zinc-100 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-2 flex items-center justify-between">
        {view === 'day' ? (
          <button
            type="button"
            aria-label="Previous month"
            onClick={() => nav(-1)}
            className="grid size-7 place-items-center rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <ChevronLeftIcon className="size-4" />
          </button>
        ) : (
          <span className="size-7" />
        )}
        <button
          type="button"
          aria-label={headerLabel}
          onClick={() => setView(view === 'year' ? 'day' : 'year')}
          className="cursor-pointer rounded-md px-2 py-1 text-[13px] font-semibold text-zinc-900 transition-colors hover:bg-accent-tint hover:text-accent dark:text-zinc-100 dark:hover:bg-accent/20 dark:hover:text-accent-soft"
        >
          {headerText}
        </button>
        {view === 'day' ? (
          <button
            type="button"
            aria-label="Next month"
            onClick={() => nav(1)}
            className="grid size-7 place-items-center rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <ChevronRightIcon className="size-4" />
          </button>
        ) : (
          <span className="size-7" />
        )}
      </div>

      {view === 'year' && (
        <DrillGrid
          cells={years.map((y) => ({
            key: `${y}`,
            label: `${y}`,
            disabled: yearDisabled(y),
            current: y === viewYear,
            onPick: () => pickYear(y),
          }))}
        />
      )}

      {view === 'month' && (
        <DrillGrid
          cells={MONTHS_SHORT.map((label, m) => ({
            key: label,
            label,
            disabled: monthDisabled(viewYear, m),
            current: m === viewMonth,
            onPick: () => pickMonth(m),
          }))}
        />
      )}

      {view === 'day' && (
        <div className="grid grid-cols-7 gap-0.5 text-center">
          {DOW.map((d, i) => (
            <div
              key={i}
              className="py-1 text-[10.5px] font-semibold text-zinc-400 dark:text-zinc-500"
            >
              {d}
            </div>
          ))}
          {cells.map((day, i) => {
            if (day === null) return <div key={i} />
            const disabled = isDisabled(day)
            const isStart = start !== null && sameDay(day, start)
            const isToday = sameDay(day, today)
            return (
              <button
                key={i}
                type="button"
                disabled={disabled}
                onClick={() => pick(day)}
                className={[
                  CELL_BASE,
                  'py-1.5 text-[12.5px]',
                  disabled ? CELL_DISABLED : CELL_ENABLED,
                  isStart ? 'bg-accent text-white hover:bg-accent hover:text-white' : '',
                  isToday && !isStart ? CELL_CURRENT : '',
                ].join(' ')}
              >
                {day.getDate()}
              </button>
            )
          })}
        </div>
      )}

      <p className="mt-2 text-[11.5px] text-zinc-400 dark:text-zinc-500">{hintFor(view, start)}</p>
    </div>
  )
}

type DrillCell = Readonly<{
  key: string
  label: string
  disabled: boolean
  current: boolean
  onPick: () => void
}>

/** The 3-column grid shared by the year and month drill-down levels. Cells
 *  carry the same disabled styling as out-of-bounds days. */
function DrillGrid({ cells }: Readonly<{ cells: DrillCell[] }>) {
  return (
    <div className="grid grid-cols-3 gap-1 text-center">
      {cells.map((c) => (
        <button
          key={c.key}
          type="button"
          disabled={c.disabled}
          onClick={c.onPick}
          className={[
            CELL_BASE,
            'py-2.5 text-[12.5px]',
            c.disabled ? CELL_DISABLED : CELL_ENABLED,
            c.current && !c.disabled ? CELL_CURRENT : '',
          ].join(' ')}
        >
          {c.label}
        </button>
      ))}
    </div>
  )
}
