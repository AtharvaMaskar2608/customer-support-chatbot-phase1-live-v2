/**
 * Report-flow engine — frozen descriptor schema (CHO-207, Wave 0).
 *
 * The insight the prototype validates: N report APIs are not N flows — they
 * are one slot-filling engine plus N declarative descriptors. A flow is data
 * (`FlowDescriptor`); the engine is flow-agnostic. Adding a report means
 * dropping a descriptor file into `flows/` — never touching engine code.
 *
 * The schema is hand-validated against three shapes before freezing:
 *   - P&L            → chips + date + delivery                 (simple, LIVE)
 *   - Capital gains  → chips + `format` + delivery             (adds format)
 *   - Contract notes → date + `selection` + delivery           (adds selection)
 * Only P&L is wired to a backend in Wave 0; the other descriptors exist so
 * the schema is proven to accommodate `format` and `selection` now.
 */

import type { ComponentType, SVGProps } from 'react'

export type IconComponent = ComponentType<SVGProps<SVGSVGElement>>

/** Sticker/icon tint key → static Tailwind classes (see Sticker component). */
export type TintKey = 'violet' | 'blue' | 'amber' | 'teal'

/* ── Slot definitions (the ordered questions a flow asks) ─────────────── */

export interface ChipOption {
  /** Customer-facing label, e.g. "Equity". Never a raw upstream code. */
  label: string
  /** Value carried in the collected slot + sent to the backend, e.g. "Equity". */
  value: string
}

/** Single-choice pills (segment, ledger book, financial year, …). */
export interface ChipsSlot {
  key: string
  label: string
  type: 'chips'
  options: ChipOption[]
}

export interface DatePreset {
  label: string
  /** Resolves the preset to a concrete range relative to `today`. */
  resolve: (today: Date) => DateRangeValue
}

/** Date-range step: quick presets + a constrained custom calendar. */
export interface DateSlot {
  key: string
  label: string
  type: 'date'
  /** Hint line under the presets, e.g. "From Jan 2018 · up to 7 days ahead · max 2-year range". */
  note: string
  presets: DatePreset[]
  constraints: DateConstraints
}

export interface DateConstraints {
  /** Earliest selectable date (inclusive), e.g. 2018-01-01. */
  minDate: string
  /** How many days past today are still selectable (settlement lookahead). */
  futureDaysCap: number
  /** Longest allowed range, in years (e.g. 2). Omit for no limit. */
  maxRangeYears?: number
}

/** File-format step (PDF vs Excel). Same UI as chips; distinct type so the
 *  engine and descriptors read intent, and so a flow's endpoint mapping can
 *  key format-specific constants (FileFormat 1/2) off it. */
export interface FormatSlot {
  key: string
  label: string
  type: 'format'
  options: ChipOption[]
}

/** Choose one/many from a list fetched at runtime (Contract Notes). The
 *  descriptor declares only the source + arity; the engine fetches, renders
 *  the month-grouped list, and downloads each tapped item. */
export interface SelectionSlot {
  key: string
  label: string
  type: 'selection'
  /** false → single pick, true → multi-select. */
  multiple: boolean
  /** Backend endpoints the engine drives: `endpoint` fetches the pickable list
   *  from the collected date range; `download` fetches one tapped item's file. */
  source: { endpoint: string; download: string }
}

export type Slot = ChipsSlot | DateSlot | FormatSlot | SelectionSlot

/* ── Delivery (the universal terminal step: download vs email) ────────── */

export type DeliveryMode = 'download' | 'email'

export interface DeliveryOption {
  label: string
  mode: DeliveryMode
  icon: IconComponent
  /** 'primary' → filled accent button, 'ghost' → outlined accent button. */
  style: 'primary' | 'ghost'
}

/* ── Collected slot values (what the engine accumulates) ──────────────── */

export interface ChipsValue {
  type: 'chips'
  label: string
  value: string
}
export interface DateRangeValue {
  type: 'date'
  label: string
  fromDate: string
  toDate: string
}
export interface FormatValue {
  type: 'format'
  label: string
  value: string
}
export interface SelectionValue {
  type: 'selection'
  items: { id: string; label: string }[]
}
export type SlotValue = ChipsValue | DateRangeValue | FormatValue | SelectionValue

/** Map of slot key → collected value. Missing key = unfilled. */
export type FilledValues = Record<string, SlotValue>

/* ── Result mapping + backend binding ─────────────────────────────────── */

/** Which help copy the "Tell me" affordance opens: a PAN-locked report PDF,
 *  an (unprotected) contract note, or an email-delivery hiccup. */
export type HelpKind = 'pdf' | 'cn' | 'email'

export interface ResultConfig {
  /** Bot line above the file/email card. `**bold**` marks emphasis. */
  summary: (values: FilledValues, asOf: string) => string
  /** Email-confirmation noun, e.g. "your **Equity** P&L for **FY 2026-27**". */
  emailNoun: (values: FilledValues) => string
  /** Extra note appended to the file card sub-line (e.g. "password: PAN"), or null. */
  passwordNote: string | null
  /** Which help copy the "Tell me" affordance opens. */
  helpKind: HelpKind
}

/** Per-descriptor backend binding. Present ⇒ the flow is live. The body
 *  shape (and any per-endpoint constants) lives here, never in shared code. */
export interface BackendConfig {
  endpoint: string
  buildBody: (values: FilledValues, mode: DeliveryMode) => Record<string, unknown>
}

/* ── The descriptor ───────────────────────────────────────────────────── */

export interface FlowDescriptor {
  /** Stable key, also the flow's identity in the registry, e.g. "pnl". */
  key: string
  /** Home-screen ordering (ascending). */
  order: number
  /** Sticker label + the phrase echoed as the user's message on tap. */
  trigger: string
  /** Composer keyword routing: text matching this starts the flow. */
  keywords: RegExp
  /** Sticker presentation. */
  sticker: { icon: IconComponent; tint: TintKey }
  /** First bot line once the flow starts. */
  intro: string
  /** The ordered questions. */
  slots: Slot[]
  /** Terminal delivery options (download / email). */
  delivery: DeliveryOption[]
  /** Narrated-generation captions (last one is swapped for email). */
  narration: string[]
  result: ResultConfig
  /** Live backend binding. Absent ⇒ not yet wired (Wave-1 flow). */
  backend?: BackendConfig
  /** When true the sticker shows a "coming soon in this build" stub instead
   *  of running — Wave-0 placeholder for the Wave-1 flows. */
  comingSoon?: boolean
}
