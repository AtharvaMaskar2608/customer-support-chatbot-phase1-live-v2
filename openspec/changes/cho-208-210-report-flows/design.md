# Design — CHO-208/209/210 Wave 1 Report Flows

## Context

Retroactive record of the Wave-1 flows, all additive on the CHO-207 foundation (engine, chat shell, delivery/PII layer, error model — reused unchanged). Built in parallel by three agents on disjoint files, integrated, and live-verified against real FinX on 2026-07-18.

## Decisions

1. **Per-flow backend routers, auto-composed.** Each flow ships its own `APIRouter` under `backend/app/reports/` (`ledger.py`, `tax.py`, `contract_notes.py`), mirroring the P&L route in `report.py`. `main.py` wires them via `include_router`. This kept the three parallel agents on disjoint files (near-zero merge surface) and keeps each flow independently testable.

2. **`RequestFor` / `FileFormat` stay per-descriptor constants** (never shared): P&L/Ledger download = 0, Tax download = 2, email = 1 everywhere; `FileFormat` 1/2 only on Tax. Encoded in each flow's mapping.

3. **Contract Notes is the selection step.** It doesn't fit pure slot-filling: date range → fetch a list → user taps → per-note download. The engine's `selection` slot (shape reserved in CHO-207) is realized here with `chat/NotesList.tsx` + `chat/notes.ts`; the two-step upstream and the `file_id`→opaque-token mapping live in `contract_notes.py`. Download-only (FinX has no CN email); PDFs unprotected.

4. **One combined branch/PR/change** rather than three, because the flows share the `main.py` wiring and were verified together — a single clean merge. The three Linear issues (CHO-208/209/210) track them individually.

## Risks / Trade-offs

- [MTF `Margin:1`] code-complete but the discriminator is CONFIRM-pending (no MTF test account) — same as noted in the API reference.
- [CN segment/badge] upstream reliably gives only `group` (`Grp1`=Equity confirmed); commodity labelling is a heuristic — the one unverifiable mapping.
- [Email delivery] not exercised live (would email the real account); unit-tested + masked.

## Migration Plan

Additive — no existing behavior changes; P&L, the engine, and the delivery layer are untouched. Ships on top of merged Wave 0.
