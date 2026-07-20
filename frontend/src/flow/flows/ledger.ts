/**
 * Ledger flow — Wave-1, wired live to the backend (CHO-208).
 *
 * Shape: chips (book) → date (range) → delivery. Same shape family as P&L,
 * PDF-only. The `book` chip shows customer labels (Normal / MTF) and the label
 * is what we send: the backend owns book→Margin (0/1) mapping so the raw
 * discriminator never crosses our API.
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

  narration: ['Gathering entries…', 'Balancing debits & credits…', 'Packaging your report…'],

  result: {
    summary: (v, asOf) => `Your **${chip(v, 'book')}** ledger for **${range(v)}** (as of ${asOf}).`,
    emailNoun: (v) => `your **${chip(v, 'book')}** ledger for **${range(v)}**`,
    passwordNote: null, // reports are not password-protected (CHO-220)
    helpKind: 'pdf',
  },

  backend: {
    endpoint: '/api/report/ledger',
    buildBody: (v, mode) => ({
      book: (v['book'] as ChipsValue).value,
      fromDate: (v['range'] as DateRangeValue).fromDate,
      toDate: (v['range'] as DateRangeValue).toDate,
      delivery: mode, // 'download' | 'email'
    }),
  },
}

export default ledger
