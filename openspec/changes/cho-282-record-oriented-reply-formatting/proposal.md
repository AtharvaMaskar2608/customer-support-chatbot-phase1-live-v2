## Why

The chat frontend has no markdown-table support: `frontend/src/chat/RichText.tsx` is a ~15-line hand-rolled renderer that only handles `**bold**` (split-on-`**`); everything else, including markdown pipe tables, passes through as literal text under `whitespace-pre-wrap`. The backend's agent loop streams raw model text with zero post-processing (`backend/app/agent/loop.py:409`), and `backend/app/agent/prompt.py` has no constraint on output formatting. When the model presents multi-fact content — report column glossaries, ledger-like breakdowns — it sometimes free-forms a markdown pipe table, which renders as literal `| Col | Col |` / `|---|---|` text: "very badly formatted," per the reported bug.

A generic table renderer was considered and explicitly rejected as the primary fix: the app's existing structured-data components (`frontend/src/chat/datacards/`) are hand-composed for known, fixed schemas (e.g. `HoldingsCard.tsx` hardcodes `DetailCell k="Invested"`, `k="Current"`, etc. with per-field currency/percent formatting) — there's no code path that generically maps arbitrary N-column markdown to a good-looking layout, and the widget's usable width is narrow (~310–420px across both the docked corner widget and the full-screen mobile/standalone chat page) in every context it appears, so an arbitrary-width table has no comfortable home. The tractable fix is to constrain what shape of thing the model is allowed to emit, not to guess arbitrary shapes at render time: a **record-oriented** convention (bold headline + plain field lines per record) instead of a **column-oriented** one (pipe tables) — record shape generalizes over field count for free, since fields stack vertically per record rather than laying out as grid columns.

## What Changes

- Add a formatting convention to `backend/app/agent/prompt.py`: when presenting more than one related fact (e.g. report column meanings, transaction-like breakdowns), the model SHALL use a bold-headline line per record followed by its plain-text fields — never markdown pipe-table syntax.
- Add a frontend safety net in the RichText rendering path: if a stray GFM pipe table still slips through (prompt compliance isn't 100%), detect it and render it as a plain, honestly-styled, horizontally-scrollable HTML table (matching the app's existing rounded-corner / light-dark tokens) instead of literal pipe/dash text — never worse than today, even on a compliance miss.
- No changes to tool schemas, the datacard component system, or `HoldingsCard`/`MoneyCard`/`BrokerageCard` — those are untouched; this only affects free-text agent replies (the `agent`/`bot` message kinds routed through `RichText`).

## Capabilities

### New Capabilities
- `reply-formatting`: how multi-fact/tabular content in streamed agent replies is formatted by the model and rendered by the frontend — the record-oriented convention plus the plain-table fallback for non-compliant output.

### Modified Capabilities
(none — this is new behavior, not a change to an existing spec'd requirement)

## Impact

- `backend/app/agent/prompt.py` — new formatting convention instruction.
- `frontend/src/chat/RichText.tsx` — extended to detect and fall back a stray pipe table to a plain scrollable table; the bold-only path is unchanged for everything else.
- Possibly a new small presentational component (e.g. a plain table wrapper) alongside `RichText.tsx`, styled to match `frontend/src/chat/datacards/primitives.tsx`'s `DataCardFrame` visual tokens (rounded corners, dark-mode variants) for consistency, without depending on any datacard-specific logic.
- This is Phase 1 of a two-phase effort. Phase 2 (CHO-283, a proper `RecordListCard` reusing the datacard visual primitives) is explicitly blocked on this change shipping and real model output being observed under the new convention — do not scope Phase 2's parser/card design here.
- Independent of CHO-284 (tool-call preamble) and CHO-285 (embedding latency).
