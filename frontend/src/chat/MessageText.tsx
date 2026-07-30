import { PlainTable } from './PlainTable'
import { RichText } from './RichText'
import { splitPipeTables } from './pipeTable'

/**
 * Reply-body renderer for `bot` / `agent` messages (CHO-282).
 *
 * Almost every reply is plain text and takes the fast path below — one
 * paragraph through the existing bold-only `RichText`, exactly as before.
 * Only when a stray markdown pipe table is detected does the body split into
 * paragraph and table blocks; the table has to live outside the `<p>` (a
 * `<table>` inside a paragraph is invalid markup), which is why the wrapper
 * element belongs here rather than at the call site.
 */
export function MessageText({
  text,
  className,
}: Readonly<{ text: string; className: string }>) {
  const segments = splitPipeTables(text)

  if (segments.length === 1 && segments[0].kind === 'text') {
    return <p className={className}><RichText text={text} /></p>
  }

  return (
    <div className="flex flex-col gap-2">
      {segments.map((segment, i) =>
        segment.kind === 'text' ? (
          <p key={i} className={className}>
            <RichText text={segment.text} />
          </p>
        ) : (
          <PlainTable key={i} table={segment.table} />
        ),
      )}
    </div>
  )
}
