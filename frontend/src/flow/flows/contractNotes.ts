/**
 * Contract Notes flow (CHO-210, Wave 1) — the selection-step flow, wired live.
 *
 * Unlike P&L/Ledger/Tax (chips/date → one delivery step → one file), contract
 * notes are two-step: pick a date range, then the engine fetches a LIST of
 * notes and each tap downloads that note's PDF. There is no generic delivery
 * step and no email — the selection IS the delivery. The chat shell renders the
 * month-grouped tap-to-get list and drives both the list and download calls.
 *
 * Delivery/result differences the schema carries: contract notes are NOT
 * password-protected (passwordNote: null) and the help copy is the `cn` variant.
 */

import { DocumentIcon, DownloadIcon } from '../../icons'
import { addDays, customRangeValue, MONTHS_LONG, toIso } from '../dates'
import type {
  DatePreset,
  DateRangeValue,
  FilledValues,
  FlowDescriptor,
} from '../types'

const range = (v: FilledValues) => (v['range'] as DateRangeValue | undefined)?.label ?? ''

const shortMon = (d: Date) => MONTHS_LONG[d.getMonth()].slice(0, 3)

/** Most recent weekday strictly before `t` — a contract note settles the day
 *  after its trade, so "last trading day" is yesterday, skipping the weekend. */
function lastTradingDay(t: Date): Date {
  let d = addDays(t, -1)
  while (d.getDay() === 0 || d.getDay() === 6) d = addDays(d, -1)
  return d
}

/** Contract-note date presets (distinct from the P&L/Ledger set): a single
 *  trading day, the trailing week, and month-to-date. No 2-year cap. */
const CONTRACT_NOTE_PRESETS: DatePreset[] = [
  {
    label: 'Last trading day',
    resolve: (t) => {
      const d = lastTradingDay(t)
      const iso = toIso(d)
      return {
        type: 'date',
        label: `${d.getDate()} ${shortMon(d)} ${d.getFullYear()}`,
        fromDate: iso,
        toDate: iso,
      }
    },
  },
  {
    label: 'Last 7 days',
    resolve: (t) => customRangeValue(addDays(t, -6), t),
  },
  {
    label: 'This month',
    resolve: (t) => customRangeValue(new Date(t.getFullYear(), t.getMonth(), 1), t),
  },
]

const contractNotes: FlowDescriptor = {
  key: 'contract-notes',
  order: 4,
  trigger: 'Contract notes',
  keywords: /contract/i,
  sticker: { icon: DocumentIcon, tint: 'teal' },
  intro: 'Sure — which days do you need?',

  slots: [
    {
      key: 'range',
      label: 'Date range',
      type: 'date',
      note: 'From Jan 2018 · up to today · no range limit',
      presets: CONTRACT_NOTE_PRESETS,
      // Future cap = today (notes settle the next day); no 2-year range limit.
      constraints: { minDate: '2018-01-01', futureDaysCap: 0 },
    },
    {
      key: 'notes',
      label: 'Contract notes',
      type: 'selection',
      multiple: true,
      source: {
        endpoint: '/api/report/contract-notes/list',
        download: '/api/report/contract-notes/download',
      },
    },
  ],

  // Present for schema completeness; contract notes never reach the generic
  // delivery step (each note tap downloads directly).
  delivery: [
    { label: 'Download here', mode: 'download', icon: DownloadIcon, style: 'primary' },
  ],

  narration: ['Looking up your notes…', 'Sorting by date…'],

  result: {
    summary: (v) => `Your contract notes for **${range(v)}**.`,
    emailNoun: (v) => `your contract notes for **${range(v)}**`,
    passwordNote: null, // contract notes are not PAN-protected
    helpKind: 'cn',
  },
}

export default contractNotes
