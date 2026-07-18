/**
 * Ledger flow — Wave-1 placeholder. Descriptor is modelled now (chips + date
 * + delivery, same shape family as P&L) to keep the sticker wired and prove
 * the schema; tapping it shows the "coming soon" stub until Wave 1 adds the
 * backend binding. Fan-out = drop `comingSoon` + add a `backend` block.
 */

import { DocumentIcon, LedgerIcon, MailIcon } from '../../icons'
import { REPORT_DATE_PRESETS } from '../dates'
import type { ChipsValue, DateRangeValue, FilledValues, FlowDescriptor } from '../types'

const chip = (v: FilledValues, key: string) => (v[key] as ChipsValue | undefined)?.label ?? ''
const range = (v: FilledValues) => (v['range'] as DateRangeValue | undefined)?.label ?? ''

const ledger: FlowDescriptor = {
  key: 'ledger',
  order: 2,
  trigger: 'Show my ledger',
  keywords: /ledger/i,
  sticker: { icon: LedgerIcon, tint: 'blue' },
  intro: "Sure — let's pull your ledger.",
  comingSoon: true,

  slots: [
    {
      key: 'book',
      label: 'Ledger',
      type: 'chips',
      options: [
        { label: 'Normal', value: 'Normal' },
        { label: 'MTF', value: 'MTF' },
      ],
    },
    {
      key: 'range',
      label: 'Date range',
      type: 'date',
      note: 'From Jan 2018 · up to 7 days ahead · max 2-year range',
      presets: REPORT_DATE_PRESETS,
      constraints: { minDate: '2018-01-01', futureDaysCap: 7, maxRangeYears: 2 },
    },
  ],

  delivery: [
    { label: 'PDF, right here', mode: 'download', icon: DocumentIcon, style: 'primary' },
    { label: 'Send to email', mode: 'email', icon: MailIcon, style: 'ghost' },
  ],

  narration: ['Gathering entries…', 'Balancing debits & credits…', 'Sealing with your PAN…'],

  result: {
    summary: (v, asOf) => `Your **${chip(v, 'book')}** ledger for **${range(v)}** (as of ${asOf}).`,
    emailNoun: (v) => `your **${chip(v, 'book')}** ledger for **${range(v)}**`,
    passwordNote: 'password: PAN',
    helpKind: 'pdf',
  },
}

export default ledger
