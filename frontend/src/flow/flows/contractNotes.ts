/**
 * Contract Notes flow — Wave-1 placeholder, and the schema's stress test.
 * Its job in Wave 0 is to prove the descriptor schema accommodates the
 * `selection` slot (date → fetch a list → pick one/many → download) BEFORE
 * the schema is frozen. Modelled and sticker-wired; shows the "coming soon"
 * stub until Wave 1 wires the list + download endpoints.
 *
 * Note the delivery/result differences the schema must carry: contract notes
 * are NOT password-protected (passwordNote: null) and the help copy differs.
 */

import { DocumentIcon, DownloadIcon } from '../../icons'
import type { DateRangeValue, FilledValues, FlowDescriptor } from '../types'

const range = (v: FilledValues) => (v['range'] as DateRangeValue | undefined)?.label ?? ''

const contractNotes: FlowDescriptor = {
  key: 'contract-notes',
  order: 4,
  trigger: 'Contract notes',
  keywords: /contract/i,
  sticker: { icon: DocumentIcon, tint: 'teal' },
  intro: 'Sure — which days do you need?',
  comingSoon: true,

  slots: [
    {
      key: 'range',
      label: 'Date range',
      type: 'date',
      note: 'From Jan 2018 · up to today · no range limit',
      // Contract notes has its own preset labels in the prototype; the shape
      // is the reusable date slot — presets resolved the same way.
      presets: [],
      constraints: { minDate: '2018-01-01', futureDaysCap: 0 },
    },
    {
      key: 'notes',
      label: 'Contract notes',
      type: 'selection',
      multiple: true,
      source: { endpoint: '/api/report/contract-notes/list' },
    },
  ],

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
