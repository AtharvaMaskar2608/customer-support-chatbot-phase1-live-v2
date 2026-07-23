/**
 * Unit checks for CHO-259 brokerage helpers.
 * Run: npx --yes tsx src/chat/datacards/brokerageCluster.test.ts
 */
import assert from 'node:assert/strict'
import {
  formatRateInr,
  orderBrokerageGroups,
  parseRate,
  rateDisplay,
  type BrokerageGroup,
} from './brokerageCluster'

function groups(...titles: string[]): BrokerageGroup[] {
  return titles.map((title) => ({ title, list: [{ title: 'X', desc: '₹1.00 per order' }] }))
}

/* ── orderBrokerageGroups ─────────────────────────────────────────────── */

{
  const ordered = orderBrokerageGroups(groups('Currency', 'Equity', 'Derivative'))
  assert.deepEqual(
    ordered.map((g) => g.title),
    ['Equity', 'Derivative', 'Currency'],
  )
}

{
  const ordered = orderBrokerageGroups(groups('Currency', 'Mystery', 'Equity', 'Other'))
  assert.deepEqual(
    ordered.map((g) => g.title),
    ['Equity', 'Currency', 'Mystery', 'Other'],
  )
}

{
  const ordered = orderBrokerageGroups(groups('Commodity', 'Currency'))
  assert.deepEqual(
    ordered.map((g) => g.title),
    ['Commodity', 'Currency'],
  )
}

/* ── rateDisplay / formatRateInr ──────────────────────────────────────── */

assert.equal(rateDisplay({ amt: 1, unit: 'per10k' }), '₹1 per ₹10,000 traded')
assert.equal(rateDisplay({ amt: 0.1, unit: 'per10k' }), '₹0.10 per ₹10,000 traded')
assert.equal(rateDisplay({ amt: 20, unit: 'order' }), '₹20 flat per order')
assert.equal(formatRateInr(20), '₹20')
assert.equal(formatRateInr(20.0), '₹20')
assert.equal(formatRateInr(0.1), '₹0.10')

/* ── parseRate shapes used by the card ────────────────────────────────── */

assert.deepEqual(parseRate('₹1.00 for trade value of 10 thousand'), { amt: 1, unit: 'per10k' })
assert.deepEqual(parseRate('₹20.00 per order'), { amt: 20, unit: 'order' })
assert.equal(parseRate('weird upstream text'), null)

console.log('brokerageCluster.test.ts: all assertions passed')
