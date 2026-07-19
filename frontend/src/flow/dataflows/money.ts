/**
 * Money in & out data flow (money-flow) — Wave B.
 *
 * Zero-slot: sticker tap (or keyword) → narrated fetch → one merged
 * passbook timeline (pay-in + pay-out, newest first). The backend fetches
 * both directions concurrently and serves one normalized stream — the flow
 * makes a single /api/data/money call.
 *
 * Note: the descriptor's single `trigger` string is both the sticker label
 * and the echoed user message; per tasks 7.1 and the prototype's sticker
 * row it reads "Pay in / out".
 */

import { MoneyCard } from '../../chat/datacards/MoneyCard'
import { fetchMoney } from '../../chat/datacards/money'
import { SwapIcon } from '../../icons'
import type { DataFlowDescriptor } from '../dataflow'

const money: DataFlowDescriptor = {
  kind: 'data',
  key: 'money',
  order: 5, // prototype home order: after Contract notes (4), before Brokerage (6)
  trigger: 'My pay-in / pay-out',
  stickerLabel: 'Pay in / out',
  keywords: /pay ?in|pay ?out|payin|payout|deposit|withdraw|add(ed)? money|my funds/i,
  sticker: { icon: SwapIcon, tint: 'emerald' },
  intro: "Here's the money moving through your account — newest first.",
  narration: ['Pulling your transactions…', 'Checking what landed…'],
  fetch: fetchMoney,
  Card: MoneyCard,
  emptyLine: 'No money movements in this period.',
  errorNoun: 'your transactions',
  followup: { text: 'Something not adding up?', linkLabel: 'Tell me.' },
  helpKind: 'payin',
}

export default money
