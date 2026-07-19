# conversation-store (delta)

## ADDED Requirements

### Requirement: Feedback rows ride the writer queue
The store SHALL persist answer ratings in a `feedback` table (`thread_id` referencing the thread, `anchor_seq`, `rating` `up`|`down`, `source`, created/updated timestamps) with at most one row per `(thread_id, anchor_seq)` — upserted so the latest rating wins. Feedback writes SHALL go through the existing bounded single-writer queue with the same degradation posture as turn persistence: a full queue or unreachable database drops the write with a counter and length-only log, never blocking or failing the submitting request. The DDL SHALL be part of the idempotent store schema. Ratings contain no message text and no personal data beyond the thread linkage.

#### Scenario: Last tap wins
- **WHEN** two ratings for the same thread and anchor seq are applied in order `up` then `down`
- **THEN** the table holds one row for that exchange with rating `down`

#### Scenario: Degraded persistence never surfaces
- **WHEN** the database is unreachable while a rating is submitted
- **THEN** the endpoint still returns `{"ok": true}`, the dropped write is counted, and chat is unaffected
