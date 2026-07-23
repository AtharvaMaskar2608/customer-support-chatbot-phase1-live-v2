# CHO-254: subtitle-text — design

## Context

`EmptyState.tsx` renders two static subtitle `<p>` lines under the trading-day greeting. Linear CHO-254 jam screenshots (current prod) still show:

- Line 1: `Reports, charges, processes, ticket status.`
- Line 2: `Files land right here —` + green `no email verification needed.`

Ticket status is Phase 2. Product's approved replacement copy (issue body, not yet in the jam) is:

> Fetch your reports instantly, explain charges and processes. Files land right here in chat — no email verification needed.

Archived CHO-238 asked to change that highlight from green to blue. The phrase survives the copy edit, and `EmptyState` still uses `text-online` / `text-online-soft` today — so CHO-238 remains in scope and folds into this change.

## Goals / Non-Goals

**Goals:**

- Update both subtitle strings to the approved CHO-254 copy.
- Switch the highlight span to accent tokens (`text-accent dark:text-accent-soft`), same pattern as the hero name span.

**Non-Goals:**

- Landing pagination, chip layout, divider, or any other `EmptyState` structure (CHO-260).
- Backend, greeting template, composer placeholder, or chip registry changes.

## Decisions

1. **Keep two `<p>` lines** — split the Linear copy at the sentence boundary so existing `mt-3` / leading spacing stays unchanged; only strings and the highlight class change.
2. **Accent tokens for highlight (CHO-238 included)** — `text-accent dark:text-accent-soft` + keep `font-medium`. Reuses FinX blue theme tokens; no new CSS. Green stays reserved for true "online" / market-up semantics elsewhere.
3. **CHO-238 folded in** — same file, same span; no separate follow-up PR for colour alone. Still relevant after the copy change.

## Risks / Trade-offs

- **[Merge conflict with CHO-260]** → Land CHO-254 first; CHO-260 rebases onto it. Do not parallel-apply.
- **[Composer placeholder still says "tickets…"]** → Out of scope; product only changed the subtitle block in CHO-254.

## Open Questions

- None blocking.
