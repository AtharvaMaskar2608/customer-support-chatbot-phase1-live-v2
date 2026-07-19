# CHO-217 · Answer Feedback — Design

## D1 · Which messages carry the chip, and how they learn their anchor

Chip-bearing message kinds: `download` (file card), `email` (confirmation), `datacard`, and the **exchange-final** `agent`/`bot` answer bubble. Mechanics:

- **Agent path**: when the terminal `done` event arrives (now carrying `lastSeq`), the shell stamps `{anchorSeq}` onto the answer messages rendered during that exchange (the artifact cards and/or final text bubble). One exchange → one anchor → the chip on any of its messages rates the same row.
- **Sticker path**: deterministic flow results append their cards without seq knowledge — their chips send no `anchorSeq` and the server anchors to the thread's latest turn at rating time. Post-CHO-214 that is the flow-event memo of exactly that completion. (A user rating a sticker answer *after* sending a new chat message would anchor late — accepted v1 imprecision, noted for the export tooling.)
- Clarify questions, typing/progress pills, sticker rows, and mid-stream text never carry chips — only completed answers.

## D2 · Rating semantics: set and switch, never clear

Tapping 👍 sets `up`; tapping 👎 switches to `down`; tapping the already-selected thumb does nothing (no un-rating, no DELETE path — out of scope with reasons/comments). The chip reflects local state immediately (optimistic); the POST is fire-and-forget with silent failure — a lost rating never surfaces an error to the user.

## D3 · Storage: one row per exchange through the writer queue

```sql
CREATE TABLE IF NOT EXISTS feedback (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    thread_id  UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    anchor_seq INTEGER NOT NULL,
    rating     TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    source     TEXT NOT NULL,          -- 'agent' | 'flow' | 'data'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (thread_id, anchor_seq)
);
```

Upsert `ON CONFLICT (thread_id, anchor_seq) DO UPDATE SET rating, updated_at` — the last tap wins. The endpoint enqueues a new `("feedback", row)` job on the store's existing bounded queue; the single writer applies it. DB down / queue full ⇒ counted + dropped, chat untouched — identical posture to turn persistence. Export joins `feedback` to `turns` on `(thread_id, seq ≤ anchor_seq)` per exchange.

## D4 · `done` event

`done` grows one field: `{"thread": {"taskTurns": n, "sessionTurns": n, "lastSeq": n}}` — the thread's last turn seq at terminal time. Additive; the CHO-213 SSE contract's consumers ignore unknown fields.

## D5 · Chip visual

Zinc outline icons in a small pill under the message, accent-filled when selected, ~24px tall, present from render (no hover-gating — touch devices). No layout shift: space reserved with the message. Same component across all four message kinds.
