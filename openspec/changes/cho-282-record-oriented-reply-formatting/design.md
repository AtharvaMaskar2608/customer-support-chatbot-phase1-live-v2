## Context

Two independent facts converged on this design:

1. **Backend**: `backend/app/agent/prompt.py` has zero formatting constraints today; the model free-forms whatever markdown it likes, streamed raw (`backend/app/agent/loop.py:409`, no post-processing).
2. **Frontend**: `frontend/src/chat/RichText.tsx` is a 15-line renderer handling only `**bold**`. There is no markdown library anywhere in `frontend/package.json` (no `react-markdown`, `remark`, `marked`). The widget's usable content width is narrow everywhere it renders — the docked corner widget is 380px desktop (`frontend/src/widget/widget.ts:90`, minus padding ≈ 348px usable) and goes full-screen under 480px viewport (`widget.ts:115-124`); the standalone chat page is capped at `max-w-[480px]` even on desktop (`frontend/src/App.tsx:191`). So there is no "wide desktop" context to design a rich table layout for — every context is a narrow column.

A generic "render any incoming table well" component was considered and rejected (see proposal's Why). The existing datacard system (`frontend/src/chat/datacards/primitives.tsx`) is not a generic table renderer — `DetailGrid`/`DetailCell`/`ExpandableRow` are layout primitives that `HoldingsCard.tsx` fills in by hand, per known field (`DetailCell k="Invested"`, `k="Current"`, ... each with bespoke currency/percent/color formatting). There's no code path that takes arbitrary N-column text and infers formatting or a "headline" column. Building one would require guessing semantics (which column is the row's identity? is this cell a currency amount?) that fail the first time the model produces an unanticipated shape.

## Goals / Non-Goals

**Goals:**
- Give the model a formatting convention for multi-fact content that it can follow reliably (bold + short lines is something Claude is already very good at, unlike precise pipe/column alignment).
- Make that convention generalize over field count for free — a 2-field record and a 6-field record are just a different number of lines under one headline, not a different column layout.
- Ensure that even a compliance miss (a stray pipe table) never regresses below "usable" — degrade to a plain, honestly-styled scrollable table, never literal pipe/dash text.
- Keep this entirely scoped to free-text agent replies; do not touch the datacard system or any tool schema.

**Non-Goals:**
- Not building a generic "any table looks great" card in this change — that's CHO-283, explicitly deferred until real output under this convention exists.
- Not adopting a full markdown library (`react-markdown`/`remark-gfm`) — the only gap being closed is pipe-table handling; everything else the model might emit (headers, links, nested lists) is out of scope because there's no reported problem with them today, and adding a full markdown parser is a much bigger dependency/behavior surface than this bug needs.
- Not guaranteeing 100% prompt compliance — the frontend fallback exists precisely because compliance is probabilistic.

## Decisions

**1. The convention is "bold headline + plain field lines per record," not a new syntax.**
Something like:
```
**Net Qty**
Net position after buys and sells this period

**Realized P&L**
Booked gain or loss on fully closed positions
```
This already renders acceptably through the EXISTING `RichText` component with zero frontend changes — bold splits on `**`, and `whitespace-pre-wrap` preserves the line breaks. That's deliberate: the immediate bug-fix value comes from the prompt change alone; the frontend fallback is a safety net for non-compliance, not the primary mechanism. Alternative considered — a custom delimiter syntax (e.g. `[[field: value]]`): rejected, since it asks the model to produce something it has no training-data precedent for, less reliable than bold + newlines which it already does constantly and well.

**2. Frontend fallback: detect a GFM-shaped pipe table via line-pattern matching, not a markdown library.**
Scan the message text for a header line matching a `| ... | ... |` shape immediately followed by a separator line matching `|---|---|` (with optional `:` alignment markers) — the two-line signature that makes something unambiguously a GFM table rather than incidental pipe characters in prose. Split the text into segments (table block vs. surrounding text), render surrounding text through the existing `RichText`, and render the table block through a new minimal table component. Alternative considered — pull in `remark-gfm`/`react-markdown`: rejected for this change; it's a much larger dependency and behavior surface (headers, links, nested lists, HTML-in-markdown) than "don't show raw pipes," and the project has deliberately stayed library-free for text rendering so far. If a broader markdown need emerges later, that's a separate decision, not bundled into this bug fix.

**3. The fallback table borrows the app's visual tokens, not the datacard system's logic.**
Style the plain table with the same rounded-corner / border / dark-mode tokens `DataCardFrame` uses (`frontend/src/chat/datacards/primitives.tsx:22-28`: `rounded-2xl border ... dark:bg-zinc-900/60`) for visual consistency, wrapped in a horizontally-scrollable container for any table wider than the ~310–420px usable width. This is styling reuse only — no field-name guessing, no per-cell formatting inference, no dependency on `DetailGrid`/`DetailCell`.

## Risks / Trade-offs

- **[Risk]** Prompt compliance for the new convention isn't guaranteed — the model could still emit a pipe table sometimes. → **Mitigation**: that's exactly what the frontend fallback covers; a miss degrades to a readable scrollable table, never to raw pipe text.
- **[Risk]** Line-pattern table detection could misfire on prose that incidentally contains pipe characters (rare, but possible). → **Mitigation**: require BOTH a pipe-delimited line AND an immediately-following separator line matching the `|---|---|`-with-alignment-colons shape — that two-line signature is specific enough that incidental pipes in prose won't match it; this is the same signature GFM parsers themselves use to recognize a table.
- **[Risk]** A wide fallback table (many columns) on a ~340px-wide phone screen is still a cramped, scroll-required experience even when styled well. → **Mitigation**: accepted for this change — it's a safety net for a compliance miss, not the primary experience; CHO-283's card treatment is the better answer for the common case, this just ensures the miss case is "usable," not "broken."

## Migration Plan

No data migration. Backend: a prompt text change (one cache-miss on first request post-deploy, same as any prompt edit). Frontend: an additive rendering path in the `RichText`/message-rendering layer — existing bold-only rendering for non-table text is unchanged, so no regression risk to current behavior for the common case (no tables).

## Open Questions

- Exact prompt wording for the convention — to be finalized during implementation, following the "bold headline + plain lines" shape described above.
- Whether the fallback table component needs a row cap / "show more" for a very long stray table — likely yes for consistency with `ShowMoreRow`'s existing pattern elsewhere, but can be scoped during implementation based on how large a stray table realistically gets.
