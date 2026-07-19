# CHO-217 · Answer Feedback

## Why

The conversation store records every exchange wire-faithfully — but nothing tells us whether an answer was any good. A quiet 👍/👎 on each completed answer closes that gap with the cheapest possible signal, and because every rating anchors to the exact turn it judges, the stored transcripts become a **labeled** training corpus — ground truth for the future fine-tune and the deferred DeepEval judge slice, not just raw conversations.

## What Changes

- **Inline feedback chip (frontend)**: a small 👍/👎 affordance renders under every answer-carrying message — report file cards, email confirmations, data cards, and the final agent text bubble of an exchange (KB answers included). ChatGPT-style quiet inline chips, not a popup: always available (older answers stay ratable on scroll), never interrupting, no layout shift. Tapping sets the rating; tapping the other thumb switches it; the selected state persists in the conversation UI. Deliberately out of scope: down-vote reasons, free-text comments, un-rating.
- **`POST /api/feedback` (backend)**: same auth-header validation as `/api/chat`, body `{rating: "up"|"down", anchorSeq?, source}`. Resolves the session's thread, anchors to `anchorSeq` when the frontend knows it, else to the thread's latest turn (which for a just-completed sticker flow is the CHO-214 flow-event memo — exactly the rated exchange). No model involvement.
- **`feedback` table (store)**: `thread_id`, `anchor_seq`, `rating`, `source`, `created_at`/`updated_at` — one row per rated exchange, upserted so the last tap wins. Writes ride the conversation store's existing bounded single-writer queue: rating can never add latency to chat or reports, and degrades exactly like turn persistence when the DB is down. DDL added idempotently to `schema.sql`.
- **Anchor plumbing**: the agent stream's terminal `done` event additionally carries the exchange's last turn `seq`; the shell stamps it onto the answer messages it just rendered so agent-path ratings anchor precisely.

## Capabilities

### New Capabilities

- `answer-feedback`: the chip affordance, rating semantics, and the feedback endpoint.

### Modified Capabilities

- `conversation-store`: feedback persistence through the writer queue; the feedback table joins the store schema.
- `agent-loop`: the SSE `done` event gains the exchange's last turn seq.

## Impact

- Backend: `app/agent/schema.sql` (+`feedback` DDL, idempotent), `app/agent/store.py` (feedback enqueue + writer job), `app/agent/router.py` (+`/api/feedback`), `app/agent/loop.py` (done event seq). No model calls, no new dependencies.
- Frontend: feedback chip component + message stamping in the chat shell (`messages.ts`, `ChatShell.tsx`, result-card surrounds).
- PII/compliance: a rating stores only thread id, seq, and up/down — no text, no new personal data. Training-export implications are strictly positive (labels).
