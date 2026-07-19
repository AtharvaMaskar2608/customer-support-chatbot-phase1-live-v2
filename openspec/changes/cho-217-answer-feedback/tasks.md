# CHO-217 · Answer Feedback — Tasks

## 1. Backend — storage + endpoint

- [ ] 1.1 `feedback` DDL in `schema.sql` (idempotent) + applied to the dev DB; store: `record_feedback(thread, anchor_seq, rating, source)` enqueue + `("feedback", row)` writer job with upsert; tests (last-tap-wins upsert, queue-full/degraded drop, memory-only no-op)
- [ ] 1.2 `POST /api/feedback` in the agent router: header validation → 400; body validation (rating up|down, optional int anchorSeq, source) → 400; anchor to given seq else thread's latest turn; `{"ok": true}`; tests incl. sticker-path server-side anchoring

## 2. Backend — done-event anchor

- [ ] 2.1 `done` event carries `thread.lastSeq`; loop tests updated (both terminal paths: narrated end_turn and CHO-215 short-circuit)

## 3. Frontend — chip

- [ ] 3.1 `FeedbackChip` component (👍/👎 pill, accent-selected, optimistic, set/switch semantics, fire-and-forget POST via authHeaders)
- [ ] 3.2 Message stamping: `done.lastSeq` stamped onto the exchange's answer messages; chips render under `download`, `email`, `datacard`, and exchange-final agent/bot bubbles — never on clarifies/progress/stickers; sticker-path cards submit without anchorSeq
- [ ] 3.3 Frontend build green (`tsc -b` + both vite entries)

## 4. Verification

- [ ] 4.1 Backend suite green; live: rate a KB answer 👍 then switch 👎 → one row in Postgres with rating down and matching anchor_seq; rate a sticker-flow report → row anchored to its flow-event turn; chips absent on clarify/progress messages
