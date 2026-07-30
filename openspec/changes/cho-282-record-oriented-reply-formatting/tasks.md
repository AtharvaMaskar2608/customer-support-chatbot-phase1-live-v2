## 1. Prompt convention

- [x] 1.1 Add the record-oriented formatting instruction to `backend/app/agent/prompt.py`: bold headline + plain field lines per record, explicitly prohibiting markdown pipe-table syntax, for any multi-fact reply (report column glossaries, transaction-like breakdowns, etc.). (Added as the `MULTI-FACT REPLIES USE RECORD SHAPE, NEVER A TABLE` bullet, immediately after the "Keep how-to answers SHORT" rule, with the worked `**Net Qty**` / `**Realized P&L**` example inline. Scoped so a single-fact answer stays a plain sentence.)
- [x] 1.2 Check `backend/evals/cases/e6_report_columns.py` (existing report-columns eval case) and align/extend it to assert the new convention rather than just prose. (E6's own probe gained a cheap `pipe_table` guard; the real check is the new **E6t** case in the same module — "explain what every column in my ledger report means" — since a one-column question never tempts a table. New shared matcher `assertions.pipe_table`, registered in `evals/cases/__init__.py`.)

## 2. Frontend: pipe-table detection

- [x] 2.1 Add a line-pattern detector (header row `| ... | ... |` immediately followed by a separator row `|---|---|`, with optional alignment colons) to identify a GFM-shaped table block within message text. (`frontend/src/chat/pipeTable.ts`. The delimiter row's cell count must equal the header's — GFM's own rule, and the thing that keeps prose pipes and bare `---` rules from matching.)
- [x] 2.2 Split message text into segments: non-table text (unchanged path through the existing `RichText` bold-only renderer) and detected table blocks. (`splitPipeTables`. When no table signature is present it returns the input as one text segment, byte-identical — the common path is a genuine no-op.)

## 3. Frontend: plain table fallback component

- [x] 3.1 Build a minimal table component that parses a detected table block's header/rows and renders a real `<table>`, styled with the same rounded-corner/border/dark-mode tokens as `DataCardFrame` (`frontend/src/chat/datacards/primitives.tsx:22-28`) for visual consistency — no dependency on `DetailGrid`/`DetailCell`/per-field formatting logic. (`frontend/src/chat/PlainTable.tsx`. Cells render through `RichText`, so `**bold**` is honoured; no field-name or currency inference anywhere.)
- [x] 3.2 Wrap the table in a horizontally-scrollable container for widths exceeding the available message area. (`overflow-x-auto overscroll-x-contain`, table at `w-max min-w-full` so it grows past the column instead of crushing, `max-w-[220px]` per cell to bound runaway width.)
- [x] 3.3 Wire the new component into the `agent`/`bot` message rendering path (`frontend/src/chat/ChatShell.tsx`, the `case 'agent'`/`case 'bot'` branches) alongside the existing `RichText` call. (Via a new `MessageText.tsx` wrapper — the `<table>` must sit outside the `<p>`, which is invalid markup otherwise, so the wrapper element moved into the component. Both branches keep their existing classNames, `whitespace-pre-wrap` included.)

## 4. Tests

- [x] 4.1 Add frontend tests (or Storybook/manual cases) for: non-table text unchanged; a valid pipe table renders as a real table; a line with incidental pipe characters but no valid separator row renders as plain text (no false-positive table detection). (`frontend/src/chat/pipeTable.test.ts`, 15 assertions, run with `npx --yes tsx src/chat/pipeTable.test.ts` per the `brokerageCluster.test.ts` convention. Also covers ragged rows, alignment colons, delimiter/header cell-count mismatch, and two tables in one reply. Passing.)
- [x] 4.2 Add/extend a backend eval case asserting the model's reply for a report-column question uses the bold-headline+fields convention, not pipe-table syntax. (E6t, above — asserts no pipe-table signature AND that bold headlines are actually present, so "no table" cannot be satisfied by a run-on paragraph. The Python and TypeScript detectors were cross-checked on the same five inputs and agree.)

## 5. Verify

- [x] 5.3 Static verification: `cd backend && uv run pytest` → 660 passed, 3 skipped. Frontend `tsc -b`, `npm run lint` (oxlint), and `npm run build` (app + widget entries) all clean. Cacheable prompt prefix re-measured with `count_tokens` on `claude-sonnet-4-6`: 6,875 → **7,077** (+202 for this change; 6,731 → 6,875 was CHO-284's +144). Recorded in `prompt.py`'s module docstring.

### Needs the user (live app + fresh SSO JWT — cannot be done from here)

- [ ] 5.1 Manually test a report-column question (e.g. "what do the P&L columns mean") end-to-end and confirm no raw pipe/dash text appears.
- [ ] 5.2 Manually force a stray pipe table (e.g. temporarily prompt-inject one) to confirm the fallback table renders correctly and scrolls on a narrow viewport. (Quickest route: the prompt playground at `/playground.html`, or temporarily returning a table string from the agent branch in `ChatShell.tsx`.)

## 6. Open items carried forward

- Row cap / "show more" on a very long stray table (design's open question) was deliberately **not** built: a stray table is a compliance miss on a bounded reply, and importing `ShowMoreRow` would pull in exactly the datacard coupling decision 3 rules out. Revisit only if a real transcript shows a long one.
- CHO-283 (`RecordListCard`) remains parked and un-started, per its own hard dependency on real post-deploy transcripts under this convention.
