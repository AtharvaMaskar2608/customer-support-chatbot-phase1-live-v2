/**
 * GFM pipe-table detection for streamed agent text (CHO-282).
 *
 * The model is instructed to present multi-fact content as records (bold
 * headline + plain field lines), never as a markdown table — see the
 * record-oriented convention in `backend/app/agent/prompt.py`. Prompt
 * compliance is probabilistic, so this is the safety net: when a pipe table
 * slips through anyway, we detect it here and render a real table rather
 * than letting literal `|`/`-` text reach the user.
 *
 * Detection is deliberately line-pattern based, not a markdown library: the
 * only gap being closed is pipe tables, and the app has stayed parser-free
 * for text rendering. The signature required is the same one GFM parsers
 * use — a pipe-bearing header line immediately followed by a delimiter line
 * whose cell count matches the header's — which is specific enough that
 * incidental pipes in prose do not match.
 */

export type PipeTable = Readonly<{ header: string[]; rows: string[][] }>

export type MessageSegment =
  | Readonly<{ kind: 'text'; text: string }>
  | Readonly<{ kind: 'table'; table: PipeTable }>

/** A delimiter cell: dashes, optionally alignment-colonned (`:--`, `--:`). */
const DELIMITER_CELL = /^:?-+:?$/

/** Split one table line into trimmed cells, dropping the optional outer pipes. */
function splitCells(line: string): string[] {
  let s = line.trim()
  if (s.startsWith('|')) s = s.slice(1)
  if (s.endsWith('|')) s = s.slice(0, -1)
  return s.split('|').map((cell) => cell.trim())
}

/** True when `line` is a GFM delimiter row of exactly `width` cells. */
function isDelimiterRow(line: string | undefined, width: number): boolean {
  if (line === undefined || !line.includes('|')) return false
  const cells = splitCells(line)
  return cells.length === width && cells.every((cell) => DELIMITER_CELL.test(cell))
}

/** True when line `i` opens a table — a header row plus a matching delimiter. */
function opensTable(lines: string[], i: number): boolean {
  const header = lines[i]
  if (!header.includes('|')) return false
  return isDelimiterRow(lines[i + 1], splitCells(header).length)
}

/**
 * Split message text into plain-text and table segments.
 *
 * When the text contains no table signature the whole string comes back as a
 * single text segment, byte-identical to the input — the no-table path (the
 * overwhelmingly common one) must not change behaviour at all.
 */
export function splitPipeTables(text: string): MessageSegment[] {
  const lines = text.split('\n')
  if (!lines.some((_, i) => opensTable(lines, i))) {
    return [{ kind: 'text', text }]
  }

  const segments: MessageSegment[] = []
  let pending: string[] = []

  const flushText = () => {
    // Whitespace-only runs between blocks would render as empty paragraphs.
    if (pending.join('\n').trim()) {
      segments.push({ kind: 'text', text: pending.join('\n') })
    }
    pending = []
  }

  for (let i = 0; i < lines.length; i++) {
    if (!opensTable(lines, i)) {
      pending.push(lines[i])
      continue
    }

    const header = splitCells(lines[i])
    const rows: string[][] = []
    let j = i + 2
    // The table runs to the first blank or pipe-less line (GFM's own rule).
    for (; j < lines.length && lines[j].trim() && lines[j].includes('|'); j++) {
      const cells = splitCells(lines[j])
      // GFM pads short rows and drops overflowing cells against the header.
      rows.push(header.map((_, c) => cells[c] ?? ''))
    }

    flushText()
    segments.push({ kind: 'table', table: { header, rows } })
    i = j - 1
  }

  flushText()
  return segments
}
