/**
 * Color-discipline tokens (data-card-system) — success is quiet, exceptions
 * carry the color and the word. One place for the signed/status/direction
 * presentation rules so all three data cards (Holdings now; Money and
 * Brokerage in Wave B) stay on one visual system.
 */

/** Signed-value text colors (theme-aware): green up, red down. */
export const UP_TEXT = 'text-online dark:text-online-soft'
export const DOWN_TEXT = 'text-alert dark:text-red-400'

/** Typographic minus (the prototype's glyph — never the hyphen). */
export const MINUS = '−'

/** Canonical status enum (the backend normalizes upstream casing to this). */
export type CanonicalStatus = 'SUCCESS' | 'PENDING' | 'FAILURE' | 'CANCELLED'

/**
 * Status → presentation. Success renders minimally (✓ only, no word);
 * exceptions get the dot-word and the color; rows for things that did not
 * happen (failed/cancelled) are dimmed. `dotClass` styles the count-chip dot.
 */
export const STATUS_PRESENTATION: Record<
  CanonicalStatus,
  { label: string; textClass: string; dotClass: string; dim: boolean }
> = {
  SUCCESS: { label: '✓', textClass: UP_TEXT, dotClass: 'bg-online', dim: false },
  PENDING: {
    label: '● Pending',
    textClass: 'text-amber-600 dark:text-amber-400',
    dotClass: 'bg-amber-600 dark:bg-amber-500',
    dim: false,
  },
  FAILURE: { label: '● Failed', textClass: DOWN_TEXT, dotClass: 'bg-alert', dim: true },
  CANCELLED: {
    label: '● Cancelled',
    textClass: 'text-zinc-400 dark:text-zinc-500',
    dotClass: 'bg-zinc-400 dark:bg-zinc-500',
    dim: true,
  },
}

/** Direction glyphs (passbook model): only incoming money earns green;
 *  outgoing stays neutral. */
export const DIRECTION: Record<'in' | 'out', { glyph: string; textClass: string }> = {
  in: { glyph: '↓', textClass: UP_TEXT },
  out: { glyph: '↑', textClass: 'text-zinc-600 dark:text-zinc-400' },
}
