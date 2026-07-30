import { RichText } from './RichText'
import type { PipeTable } from './pipeTable'

/**
 * Plain table fallback for a stray markdown pipe table (CHO-282).
 *
 * This is a safety net, not the intended experience — the model is asked to
 * present multi-fact content as records instead (see `pipeTable.ts`). It
 * borrows `DataCardFrame`'s visual tokens (rounded corners, border, dark
 * variants) so a miss still looks like it belongs to the app, but it shares
 * none of the datacard *logic*: no field-name inference, no per-cell currency
 * or percent formatting, no `DetailGrid`/`DetailCell` dependency. Every cell
 * is rendered as text, with `**bold**` honoured for consistency with the rest
 * of the reply.
 *
 * The message column is narrow in every context the chat renders in (~310–420px),
 * so the frame scrolls horizontally rather than crushing columns.
 */
export function PlainTable({ table }: Readonly<{ table: PipeTable }>) {
  return (
    <div className="overflow-x-auto overscroll-x-contain rounded-2xl border border-zinc-200 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900/60 dark:text-zinc-100">
      <table className="w-max min-w-full border-collapse text-[13px] leading-normal">
        <thead>
          <tr>
            {table.header.map((cell, i) => (
              <th
                key={i}
                className="border-b border-zinc-200 px-3 py-2 text-left font-semibold whitespace-nowrap dark:border-zinc-700"
              >
                <RichText text={cell} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => (
            <tr key={r} className="border-b border-zinc-100 last:border-b-0 dark:border-zinc-800">
              {row.map((cell, c) => (
                <td key={c} className="max-w-[220px] px-3 py-2 align-top">
                  <RichText text={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
