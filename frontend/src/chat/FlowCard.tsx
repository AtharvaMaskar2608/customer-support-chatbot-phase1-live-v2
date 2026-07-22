import { useMemo, useState, type ReactNode } from 'react'
import { CalendarIcon } from '../icons'
import { DELIVERY_STEP, LOCKED, type FlowRun } from '../flow/engine'
import { addDays, customRangeValue, fromIso, today } from '../flow/dates'
import type {
  ChipsSlot,
  DateSlot,
  DeliveryMode,
  FlowDescriptor,
  FormatSlot,
  Slot,
  SlotValue,
} from '../flow/types'
import { Calendar } from './Calendar'

function chipLabel(value: SlotValue): string {
  switch (value.type) {
    case 'chips':
    case 'format':
    case 'date':
      return value.label
    case 'selection':
      return value.items.map((i) => i.label).join(', ')
  }
}

/* ── shared bits ──────────────────────────────────────────────────────── */

function SlotRow({
  n,
  label,
  children,
}: Readonly<{ n: number; label: string; children: ReactNode }>) {
  // CHO-247: filled slots carry a single edit affordance — the chip itself
  // (tap-to-edit, with a ✎ glyph). No separate row-header "Edit" button.
  return (
    <div className="border-b border-zinc-100 py-3 first:pt-0.5 last:border-b-0 last:pb-0.5 dark:border-zinc-800">
      <div className="mb-2">
        <span className="text-[11px] font-bold tracking-[0.06em] text-zinc-400 uppercase dark:text-zinc-500">
          <span className="text-accent-soft">{n} ·</span> {label.toUpperCase()}
        </span>
      </div>
      {children}
    </div>
  )
}

function FilledChip({
  label,
  locked,
  onClick,
}: Readonly<{ label: string; locked: boolean; onClick: () => void }>) {
  return (
    <button
      type="button"
      disabled={locked}
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-full border-[1.5px] border-accent-soft bg-accent-tint/60 px-3 py-1.5 text-[13.5px] font-semibold text-accent enabled:hover:border-accent disabled:cursor-default dark:bg-accent/15 dark:text-accent-soft"
    >
      {label}
      {!locked && <span className="text-xs opacity-60">✎</span>}
    </button>
  )
}

const OPTION_BASE =
  'inline-flex items-center gap-2 rounded-full border-[1.5px] px-3.5 py-2 text-[13.5px] font-semibold transition-colors'

function OptionPills({
  options,
  selected,
  onPick,
}: Readonly<{
  options: { label: string; value: string }[]
  selected: string | undefined
  onPick: (opt: { label: string; value: string }) => void
}>) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = selected === opt.value
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onPick(opt)}
            className={[
              OPTION_BASE,
              active
                ? 'border-accent bg-accent text-white hover:bg-accent-strong'
                : 'border-zinc-200 bg-white text-zinc-700 hover:border-accent-soft hover:text-accent dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:text-accent-soft',
            ].join(' ')}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

function DateWidget({
  slot,
  onPick,
}: Readonly<{ slot: DateSlot; onPick: (value: SlotValue) => void }>) {
  const [showCal, setShowCal] = useState(false)
  const t = useMemo(() => today(), [])
  const minDate = useMemo(() => fromIso(slot.constraints.minDate), [slot.constraints.minDate])
  const maxDate = useMemo(
    () => addDays(t, slot.constraints.futureDaysCap),
    [t, slot.constraints.futureDaysCap],
  )

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {slot.presets.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => onPick(preset.resolve(t))}
            className={`${OPTION_BASE} border-zinc-200 bg-white text-zinc-700 hover:border-accent-soft hover:text-accent dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:text-accent-soft`}
          >
            {preset.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setShowCal((v) => !v)}
          className={[
            OPTION_BASE,
            showCal
              ? 'border-accent text-accent dark:text-accent-soft'
              : 'border-zinc-200 bg-white text-zinc-700 hover:border-accent-soft hover:text-accent dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:text-accent-soft',
          ].join(' ')}
        >
          <CalendarIcon className="size-4 text-accent dark:text-accent-soft" />
          Custom range
        </button>
      </div>

      {showCal && (
        <Calendar
          minDate={minDate}
          maxDate={maxDate}
          maxRangeYears={slot.constraints.maxRangeYears}
          onSelect={(from, to) => onPick(customRangeValue(from, to))}
        />
      )}

      <p className="mt-2.5 text-[11.5px] text-zinc-400 dark:text-zinc-500">{slot.note}</p>
    </div>
  )
}

function SlotWidget({
  slot,
  value,
  onPick,
}: Readonly<{ slot: Slot; value: SlotValue | undefined; onPick: (value: SlotValue) => void }>) {
  switch (slot.type) {
    case 'chips': {
      const s = slot as ChipsSlot
      return (
        <OptionPills
          options={s.options}
          selected={value?.type === 'chips' ? value.value : undefined}
          onPick={(o) => onPick({ type: 'chips', label: o.label, value: o.value })}
        />
      )
    }
    case 'format': {
      const s = slot as FormatSlot
      return (
        <OptionPills
          options={s.options}
          selected={value?.type === 'format' ? value.value : undefined}
          onPick={(o) => onPick({ type: 'format', label: o.label, value: o.value })}
        />
      )
    }
    case 'date':
      return <DateWidget slot={slot} onPick={onPick} />
    case 'selection':
      // The selection step is driven by the chat shell (fetched list + result
      // cards render as their own messages, not inside this card).
      return null
  }
}

function DeliveryStep({
  descriptor,
  preferred,
  onDeliver,
}: Readonly<{
  descriptor: FlowDescriptor
  /** Agent-stated delivery preference — highlighted only; never auto-fires. */
  preferred?: DeliveryMode
  onDeliver: (mode: DeliveryMode) => void
}>) {
  return (
    <div className="flex flex-wrap gap-2">
      {descriptor.delivery.map((opt) => {
        const Icon = opt.icon
        const primary = opt.style === 'primary'
        return (
          <button
            key={opt.mode}
            type="button"
            onClick={() => onDeliver(opt.mode)}
            className={[
              OPTION_BASE,
              primary
                ? 'border-accent bg-accent text-white hover:bg-accent-strong'
                : 'border-zinc-200 bg-white text-zinc-700 hover:border-accent-soft hover:text-accent dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:text-accent-soft',
              preferred === opt.mode
                ? 'ring-2 ring-accent/60 ring-offset-1 dark:ring-offset-zinc-900'
                : '',
            ].join(' ')}
          >
            <Icon className={`size-4 ${primary ? 'text-white' : 'text-accent dark:text-accent-soft'}`} />
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

/* ── the card ─────────────────────────────────────────────────────────── */

export function FlowCard({
  descriptor,
  run,
  preferredDelivery,
  onPick,
  onEdit,
  onDeliver,
}: Readonly<{
  descriptor: FlowDescriptor
  run: FlowRun
  preferredDelivery?: DeliveryMode
  onPick: (slotKey: string, value: SlotValue) => void
  onEdit: (slotKey: string) => void
  onDeliver: (mode: DeliveryMode) => void
}>) {
  const locked = run.active === LOCKED
  const rows: ReactNode[] = []

  for (let i = 0; i < descriptor.slots.length; i += 1) {
    const slot = descriptor.slots[i]
    if (run.active === slot.key) {
      // The selection step renders outside the card (the chat shell drives the
      // fetched list + downloads); the card shows only the filled steps above.
      if (slot.type !== 'selection') {
        rows.push(
          <SlotRow key={slot.key} n={i + 1} label={slot.label}>
            <SlotWidget
              slot={slot}
              value={run.values[slot.key]}
              onPick={(value) => onPick(slot.key, value)}
            />
          </SlotRow>,
        )
      }
      break
    }
    const value = run.values[slot.key]
    if (value !== undefined) {
      rows.push(
        <SlotRow key={slot.key} n={i + 1} label={slot.label}>
          <FilledChip label={chipLabel(value)} locked={locked} onClick={() => onEdit(slot.key)} />
        </SlotRow>,
      )
      continue
    }
    // Unfilled and not active → stop (one slot at a time).
    break
  }

  if (run.active === DELIVERY_STEP) {
    rows.push(
      <SlotRow key="__delivery__" n={descriptor.slots.length + 1} label="How do you want it?">
        <DeliveryStep descriptor={descriptor} preferred={preferredDelivery} onDeliver={onDeliver} />
      </SlotRow>,
    )
  }

  return (
    <div className="flex flex-col rounded-2xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-700 dark:bg-zinc-900/60">
      {rows}
    </div>
  )
}
