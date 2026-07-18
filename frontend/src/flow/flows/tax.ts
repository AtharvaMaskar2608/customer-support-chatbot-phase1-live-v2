/**
 * Capital-gains (Tax) flow — Wave-1 placeholder. Its purpose in Wave 0 is to
 * prove the schema accommodates the `format` slot (PDF/Excel) before freezing.
 * Modelled, wired to the sticker, shows the "coming soon" stub until Wave 1.
 */

import { DownloadIcon, MailIcon, ReceiptIcon } from '../../icons'
import type { ChipsValue, FilledValues, FlowDescriptor, FormatValue } from '../types'

const fy = (v: FilledValues) => (v['fy'] as ChipsValue | undefined)?.label ?? ''
const format = (v: FilledValues) => (v['format'] as FormatValue | undefined)?.label ?? ''

const tax: FlowDescriptor = {
  key: 'tax',
  order: 3,
  trigger: 'Capital gains',
  keywords: /capital|tax|gains?/i,
  sticker: { icon: ReceiptIcon, tint: 'amber' },
  intro: "Sure — let's get your capital gains statement.",
  comingSoon: true,

  slots: [
    {
      key: 'fy',
      label: 'Financial year',
      type: 'chips',
      options: [
        { label: '2025-2026', value: '2025-2026' },
        { label: '2024-2025', value: '2024-2025' },
        { label: '2023-2024', value: '2023-2024' },
      ],
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
}

export default tax
