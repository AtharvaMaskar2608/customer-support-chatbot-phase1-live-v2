## ADDED Requirements

### Requirement: Turn roots carry client context and bot versions
When a `/api/chat` turn is traced, the agent root span's metadata SHALL include `platform` and `screen_name` when the client sent `X-Platform` / `X-Screen-Name`, `backend_version` when `BOT_VERSION` is set, and `frontend_version` when `X-Frontend-Version` is set. The same metadata SHALL be mirrored to Langfuse when the mirror is enabled. Missing optional headers SHALL NOT fail the turn.

#### Scenario: Widget web handoff stamps platform
- **WHEN** the client sends `X-Platform: web` on `/api/chat`
- **THEN** the turn's root span metadata includes `platform: "web"` in Postgres and in Langfuse

#### Scenario: Absent context headers omit the keys
- **WHEN** `/api/chat` is called without platform/screen/version headers and without `BOT_VERSION`
- **THEN** the turn still completes and the root metadata simply lacks those keys

### Requirement: Turn latency and turn seq are explicit on the root
At turn end the root metadata SHALL include `latency_ms` (root duration) and, when the conversation store produced turns, `turn_seq` equal to the exchange's last stored seq (the feedback anchor). When the Langfuse mirror is enabled the root metadata SHALL also include `lf_trace_id`.

#### Scenario: done.lastSeq matches root turn_seq
- **WHEN** a chat turn ends with SSE `done.thread.lastSeq = N`
- **THEN** the persisted root metadata has `turn_seq: N`

### Requirement: Ticket id is attached when a ticket is raised
When `raise_support_ticket` succeeds inside a chat turn, the open root's metadata SHALL include `ticket_id`. When `POST /api/ticket` succeeds with the mirror enabled, Langfuse SHALL receive a short `raise_ticket` observation for that thread session carrying `ticket_id`.

#### Scenario: Agent-raised ticket lands on the turn root
- **WHEN** the agent tool raises ticket 7551234 during a traced turn
- **THEN** the root metadata includes `ticket_id` of that id in both sinks

### Requirement: Feedback scores the matching Langfuse trace
When `POST /api/feedback` records a rating and the Langfuse mirror is enabled, the backend SHALL create a Langfuse BOOLEAN score named `user-feedback` (`1` for up, `0` for down) on the matching turn's `lf_trace_id` when found via `(thread_id, turn_seq)`; otherwise it SHALL score by Langfuse `session_id` = Thread.id. Failures SHALL NOT change the HTTP response or the `feedback` table write.

#### Scenario: Thumbs-up scores the turn
- **WHEN** feedback `up` is posted with `anchorSeq` matching a persisted root `turn_seq`
- **THEN** Langfuse receives a `user-feedback` BOOLEAN score of 1 on that trace
