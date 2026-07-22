/**
 * Holdings data flow (holdings-flow) — the reference data card, and the
 * first sticker on the home screen.
 *
 * Zero-slot: sticker tap (or keyword) → narrated fetch → the portfolio card.
 * No questions, no slot card, no delivery step. Time-honest throughout: the
 * intro and narration never claim live prices.
 */

import { HoldingsCard } from '../../chat/datacards/HoldingsCard'
import { fetchHoldings } from '../../chat/datacards/holdings'
import { PieIcon } from '../../icons'
import type { DataFlowDescriptor } from '../dataflow'

const holdings: DataFlowDescriptor = {
  kind: 'data',
  key: 'holdings',
  order: 0, // first position — ahead of the four file flows (P&L is 1)
  trigger: 'Show my holdings',
  stickerLabel: 'My holdings',
  keywords: /holding|portfolio|my stocks|my shares|invest/i,
  sticker: { icon: PieIcon, tint: 'cyan' },
  intro: "Sure — here's your portfolio at the last fetched prices.",
  narration: ['Fetching your holdings…', 'Valuing at last prices…'],
  fetch: fetchHoldings,
  Card: HoldingsCard,
  emptyLine: 'No holdings in your demat yet',
  errorNoun: 'your holdings',
  followup: { text: 'Tap any holding for the full breakdown', linkLabel: 'Something look off?' },
  refreshable: true, // CHO-248: offer a one-tap "Refresh prices" re-run
  helpKind: 'holding',
}

export default holdings
