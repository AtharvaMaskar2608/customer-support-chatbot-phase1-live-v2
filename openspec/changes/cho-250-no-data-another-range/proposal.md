# CHO-250: no-data-another-range

## Why

When a report comes back with no data — e.g. "I couldn't find any P&L for that period." — the shell prints the line and stops. There is no actionable control to try a different range; the user has to restart the whole flow. Contract notes already handles this well: on an empty result it offers a **"Change dates"** pill (`notesAction` → `ChangeDatesButton`). The report flows (P&L, ledger, capital gains) should offer the same one-tap recovery (CHO-250: if no P&L is available, provide a "select another range" sticker, mirroring contract notes).

## What Changes

- On a **no-data** report result (the outcome that renders "couldn't find …"), the shell SHALL append a **"Try another range"** recovery pill beneath the line. Choosing it appends a FRESH guided flow card below, seeded with the prior run's values but with the **date range re-opened** (segment/book kept), so the user picks a new range and re-runs — the spawn-fresh-below model shared with CHO-249.
- Applies to the date-bearing report flows (P&L, ledger; capital gains uses a financial-year slot — the pill re-opens that). Mirrors the existing contract-notes recovery so the UX is consistent across flows.
- Frontend-only. No backend/API change. The agent-memory side of a no-data attempt is tracked separately in **CHO-253** (so the LLM's next reply is no-data-aware); this change is the immediate in-widget recovery.

## Capabilities

### Modified Capabilities

- `report-chat-shell`: a no-data report result SHALL carry an actionable "Try another range" recovery affordance (mirroring contract notes' "Change dates"), which re-opens the range on a fresh seeded flow card — not just a dead-end text line.

## Impact

- Frontend only: `frontend/src/chat/ChatShell.tsx` — in `renderResult` (the no-data outcome that maps to the "couldn't find …" line in `messages.ts:105`), append a recovery-action message that spawns a fresh flow seeded with the prior values minus the date/FY slot (so the engine prompts it first). Generalises the existing `notesAction` / `ChangeDatesButton` recovery from contract notes to the report flows.
- `frontend/src/chat/messages.ts` — the "couldn't find …" copy stays; it just gains an actionable pill beneath it.
- No test impact expected; `tsc` + lint + build are the gates. Visible UI change → screenshot before deploy.
- Linear: CHO-250 · branch `cho-250-no-data-another-range`. Relates to CHO-249, CHO-253.
