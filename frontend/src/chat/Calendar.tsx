import { useState } from 'react'
import { ChevronLeftIcon, ChevronRightIcon } from '../icons'
import { addYears, DOW, MONTHS_LONG, sameDay } from '../flow/dates'

/**
 * Constrained custom-range calendar for the `date` slot. Two taps: start,
 * then end. Enforces the flow's bounds — no date before `minDate`, none after
 * `maxDate` (today + futureDaysCap), and (once a start is picked) none beyond
 * `maxRangeYears` from it. Out-of-bounds days are visibly disabled.
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

  return (
    <div className="mt-3 rounded-xl border border-zinc-100 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          aria-label="Previous month"
          onClick={() => nav(-1)}
          className="grid size-7 place-items-center rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
        >
          <ChevronLeftIcon className="size-4" />
        </button>
        <span className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">
          {MONTHS_LONG[viewMonth]} {viewYear}
        </span>
        <button
          type="button"
          aria-label="Next month"
          onClick={() => nav(1)}
          className="grid size-7 place-items-center rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
        >
          <ChevronRightIcon className="size-4" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-0.5 text-center">
        {DOW.map((d, i) => (
          <div key={i} className="py-1 text-[10.5px] font-semibold text-zinc-400 dark:text-zinc-500">
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
                'rounded-md py-1.5 text-[12.5px] transition-colors',
                disabled
                  ? 'cursor-default text-zinc-300 dark:text-zinc-600'
                  : 'cursor-pointer text-zinc-700 hover:bg-accent-tint hover:text-accent dark:text-zinc-200 dark:hover:bg-accent/20 dark:hover:text-accent-soft',
                isStart ? 'bg-accent text-white hover:bg-accent hover:text-white' : '',
                isToday && !isStart ? 'outline outline-1 outline-accent-soft' : '',
              ].join(' ')}
            >
              {day.getDate()}
            </button>
          )
        })}
      </div>

      <p className="mt-2 text-[11.5px] text-zinc-400 dark:text-zinc-500">
        {start === null ? 'Pick a start date' : 'Pick an end date'}
      </p>
    </div>
  )
}
