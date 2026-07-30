/**
 * Unit checks for CHO-282 pipe-table detection.
 * Run: npx --yes tsx src/chat/pipeTable.test.ts
 */
import assert from 'node:assert/strict'
import { splitPipeTables, type MessageSegment } from './pipeTable'

function tableAt(segments: MessageSegment[], i: number) {
  const seg = segments[i]
  assert.equal(seg.kind, 'table')
  if (seg.kind !== 'table') throw new Error('unreachable')
  return seg.table
}

/* ── non-table text is passed through untouched ───────────────────────── */

{
  const text = 'Intraday positions are squared off before market close.'
  assert.deepEqual(splitPipeTables(text), [{ kind: 'text', text }])
}

{
  // The record-oriented convention the prompt asks for: bold + plain lines.
  const text = '**Net Qty**\nNet position after buys and sells\n\n**Realized P&L**\nBooked gain or loss'
  assert.deepEqual(splitPipeTables(text), [{ kind: 'text', text }])
}

{
  // Multi-line text keeps its exact bytes — line breaks matter under pre-wrap.
  const text = 'Line one\n\nLine two\n  indented'
  assert.deepEqual(splitPipeTables(text), [{ kind: 'text', text }])
}

/* ── a valid pipe table is detected and parsed ────────────────────────── */

{
  const segments = splitPipeTables('| Column | Meaning |\n|---|---|\n| Net Qty | Net position |')
  assert.equal(segments.length, 1)
  assert.deepEqual(tableAt(segments, 0), {
    header: ['Column', 'Meaning'],
    rows: [['Net Qty', 'Net position']],
  })
}

{
  // Alignment colons, and rows without the optional outer pipes.
  const segments = splitPipeTables('| A | B |\n| :--- | ---: |\nx | y')
  assert.deepEqual(tableAt(segments, 0), { header: ['A', 'B'], rows: [['x', 'y']] })
}

{
  // Ragged rows are padded/truncated against the header, as GFM does.
  const segments = splitPipeTables('| A | B |\n|---|---|\n| only |\n| a | b | c |')
  assert.deepEqual(tableAt(segments, 0).rows, [
    ['only', ''],
    ['a', 'b'],
  ])
}

/* ── text around a table is preserved as its own segments ─────────────── */

{
  const segments = splitPipeTables('Here you go:\n| A | B |\n|---|---|\n| 1 | 2 |\nAnything else?')
  assert.equal(segments.length, 3)
  assert.deepEqual(segments[0], { kind: 'text', text: 'Here you go:' })
  assert.deepEqual(tableAt(segments, 1), { header: ['A', 'B'], rows: [['1', '2']] })
  assert.deepEqual(segments[2], { kind: 'text', text: 'Anything else?' })
}

{
  // A blank line ends the table; the trailing prose is a separate segment.
  const segments = splitPipeTables('| A | B |\n|---|---|\n| 1 | 2 |\n\nThat is the breakdown.')
  assert.equal(segments.length, 2)
  assert.equal(segments[0].kind, 'table')
  assert.deepEqual(segments[1], { kind: 'text', text: '\nThat is the breakdown.' })
}

{
  const segments = splitPipeTables('| A |\n|---|\n| 1 |\n\n| B |\n|---|\n| 2 |')
  assert.deepEqual(
    segments.map((s) => s.kind),
    ['table', 'table'],
  )
}

/* ── incidental pipes are NOT mistaken for a table ────────────────────── */

{
  // Pipes in prose with no delimiter row underneath.
  const text = 'Use the Buy | Sell toggle at the top of the screen.'
  assert.deepEqual(splitPipeTables(text), [{ kind: 'text', text }])
}

{
  // A pipe line followed by an unrelated line, not a delimiter row.
  const text = '| A | B |\nthese are the two options'
  assert.deepEqual(splitPipeTables(text), [{ kind: 'text', text }])
}

{
  // Delimiter cell count must match the header's — 2 columns vs 3 dashes.
  const text = '| A | B |\n|---|---|---|\n| 1 | 2 |'
  assert.deepEqual(splitPipeTables(text), [{ kind: 'text', text }])
}

{
  // A horizontal rule is not a delimiter row (no pipes).
  const text = 'Heading\n---\nBody text'
  assert.deepEqual(splitPipeTables(text), [{ kind: 'text', text }])
}

{
  // Dashes in a real sentence under a pipe-bearing line stay text.
  const text = 'Equity | Derivative\n- both are covered'
  assert.deepEqual(splitPipeTables(text), [{ kind: 'text', text }])
}

console.log('pipeTable: all assertions passed')
