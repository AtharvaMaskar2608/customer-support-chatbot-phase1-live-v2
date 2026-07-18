import { Fragment } from 'react'

/**
 * Minimal inline-emphasis renderer: text wrapped in `**` renders bold. Keeps
 * descriptor copy as plain strings (no JSX / innerHTML) while still bolding
 * the segment, range, etc. in bot lines and result summaries.
 */
export function RichText({ text }: Readonly<{ text: string }>) {
  const parts = text.split('**')
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="font-semibold text-zinc-900 dark:text-zinc-50">
            {part}
          </strong>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  )
}
