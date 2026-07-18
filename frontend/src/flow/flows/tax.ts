/**
 * Capital-gains (Tax) flow — Wave-1, wired live to the backend. The ONE flow
 * with a `format` step: PDF or Excel. Capital-gain intent routes here (there is
 * no separate CG API).
 *
 * Shape: chips (financial year) → format (PDF/Excel) → delivery. The FinYear
 * window is DYNAMIC — the current Indian FY plus the previous two, computed here
 * so it rolls forward on its own each April and is never a hardcoded list.
 */

import { DownloadIcon, MailIcon, ReceiptIcon } from '../../icons'
import type {
  ChipOption,
  ChipsValue,
  FilledValues,
  FlowDescriptor,
  FormatValue,
} from '../types'

const fy = (v: FilledValues) => (v['finYear'] as ChipsValue | undefined)?.label ?? ''
const format = (v: FilledValues) => (v['format'] as FormatValue | undefined)?.label ?? ''

/**
 * The selectable financial years: current FY + the previous two, newest first.
 * The Indian FY runs April–March, so before April we are still in the FY that
 * began the previous calendar year (getMonth() is 0-based; March = 2, April = 3).
 */
function financialYearOptions(today: Date = new Date()): ChipOption[] {
  const startYear =
    today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1
  return [0, 1, 2].map((back) => {
    const s = startYear - back
    const label = `${s}-${s + 1}`
    return { label, value: label }
  })
}

const tax: FlowDescriptor = {
  key: 'tax',
  order: 3,
  trigger: 'Capital gains',
  keywords: /capital|tax|gains?/i,
  sticker: { icon: ReceiptIcon, tint: 'amber' },
  intro: "Sure — let's get your capital gains statement.",

  slots: [
    {
      key: 'finYear',
      label: 'Financial year',
      type: 'chips',
      // Dynamic window (current FY + last 2) — never a hardcoded list.
      options: financialYearOptions(),
    },
    {
      key: 'format',
      label: 'Format',
      type: 'format',
      options: [
        { label: 'PDF', value: 'PDF' },
        { label: 'Excel', value: 'Excel' },
      ],
    },
  ],

  delivery: [
    { label: 'Download here', mode: 'download', icon: DownloadIcon, style: 'primary' },
    { label: 'Send to email', mode: 'email', icon: MailIcon, style: 'ghost' },
  ],

  narration: ['Matching buys & sells…', 'Computing your gains…', 'Formatting your statement…'],

  result: {
    summary: (v) => `Your capital gains statement for **FY ${fy(v)}** (${format(v)}).`,
    emailNoun: (v) => `your capital gains statement for **FY ${fy(v)}**`,
    passwordNote: 'password: PAN',
    helpKind: 'pdf',
  },

  backend: {
    endpoint: '/api/report/tax',
    buildBody: (v, mode) => ({
      finYear: (v['finYear'] as ChipsValue).value,
      format: (v['format'] as FormatValue).value, // 'PDF' | 'Excel'
      delivery: mode, // 'download' | 'email'
    }),
  },
}

export default tax
