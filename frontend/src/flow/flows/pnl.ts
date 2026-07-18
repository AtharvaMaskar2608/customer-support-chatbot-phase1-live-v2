/**
 * P&L report flow — the Wave-0 reference flow, wired live to the backend.
 *
 * Shape: chips (segment) → date (range) → delivery. PDF-only, no format step.
 * Segment shows customer labels (Equity / F&O / Commodity), never the raw
 * upstream codes (Cash / Derv / Comm) — and the label is what we send: the
 * backend owns label→Group mapping so "Derv" never crosses our API.
 */

import { DocumentIcon, MailIcon, TrendingUpIcon } from '../../icons'
import { REPORT_DATE_PRESETS } from '../dates'
import type {
  ChipsValue,
  DateRangeValue,
  FilledValues,
  FlowDescriptor,
} from '../types'

const chip = (v: FilledValues, key: string) => (v[key] as ChipsValue | undefined)?.label ?? ''
const range = (v: FilledValues) => (v['range'] as DateRangeValue | undefined)?.label ?? ''

const pnl: FlowDescriptor = {
  key: 'pnl',
  order: 1,
  trigger: 'Get my P&L',
  keywords: /p ?& ?l|pnl|profit|p and l/i,
  sticker: { icon: TrendingUpIcon, tint: 'violet' },
  intro: "Sure — let's set it up.",

  slots: [
    {
      key: 'segment',
      label: 'Segment',
      type: 'chips',
      // value === label: the backend validates on the customer label and owns
      // the label→Group (Cash/Derv/Comm) mapping server-side.
      options: [
        { label: 'Equity', value: 'Equity' },
        { label: 'F&O', value: 'F&O' },
        { label: 'Commodity', value: 'Commodity' },
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

  narration: ['Pulling your trades…', 'Tallying charges…', 'Sealing with your PAN…'],

  result: {
    summary: (v, asOf) =>
      `Your **${chip(v, 'segment')}** P&L for **${range(v)}** (as of ${asOf}, incl. charges).`,
    emailNoun: (v) => `your **${chip(v, 'segment')}** P&L for **${range(v)}**`,
    passwordNote: 'password: PAN',
    helpKind: 'pdf',
  },

  backend: {
    endpoint: '/api/report/pnl',
    buildBody: (v, mode) => ({
      segment: (v['segment'] as ChipsValue).value,
      fromDate: (v['range'] as DateRangeValue).fromDate,
      toDate: (v['range'] as DateRangeValue).toDate,
      delivery: mode, // 'download' | 'email'
    }),
  },
}

export default pnl
