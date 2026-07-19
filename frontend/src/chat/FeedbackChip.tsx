import { ThumbDownIcon, ThumbUpIcon } from '../icons'

export type FeedbackRating = 'up' | 'down'

/**
 * Quiet inline 👍/👎 pill under an answer message (CHO-217 · design D5):
 * zinc outline thumbs, accent-filled when selected, ~24px tall, present from
 * render (no hover-gating — touch devices). Tapping sets the rating, tapping
 * the other thumb switches it, tapping the selected thumb does nothing —
 * un-rating is out of scope, so `onRate` only ever fires with a change.
 */
export function FeedbackChip({
  rating,
  onRate,
}: Readonly<{ rating?: FeedbackRating; onRate: (rating: FeedbackRating) => void }>) {
  return (
    <div className="inline-flex h-6 w-fit items-center gap-0.5 rounded-full border border-zinc-200 bg-white px-1 dark:border-zinc-700 dark:bg-zinc-900/60">
      <Thumb kind="up" selected={rating === 'up'} onRate={onRate} />
      <Thumb kind="down" selected={rating === 'down'} onRate={onRate} />
    </div>
  )
}

function Thumb({
  kind,
  selected,
  onRate,
}: Readonly<{ kind: FeedbackRating; selected: boolean; onRate: (rating: FeedbackRating) => void }>) {
  const Icon = kind === 'up' ? ThumbUpIcon : ThumbDownIcon
  return (
    <button
      type="button"
      aria-label={kind === 'up' ? 'Good answer' : 'Bad answer'}
      aria-pressed={selected}
      onClick={() => {
        if (!selected) onRate(kind)
      }}
      className={[
        'grid size-5 place-items-center rounded-full transition-colors',
        selected
          ? 'text-accent dark:text-accent-soft'
          : 'text-zinc-400 hover:text-zinc-600 dark:text-zinc-500 dark:hover:text-zinc-300',
      ].join(' ')}
    >
      <Icon className="size-3.5" strokeWidth={1.75} fill={selected ? 'currentColor' : 'none'} />
    </button>
  )
}
