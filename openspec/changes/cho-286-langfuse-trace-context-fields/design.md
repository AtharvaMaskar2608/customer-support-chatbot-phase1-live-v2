## Context

CHO-286 mirrors every `observe_*` span to Langfuse. Identity is already set (`session_id` = Thread.id, `user_id` = HMAC). The root `chat_turn` currently closes with no metadata. Platform / screenName exist only in frontend `SessionContext`. Feedback lives in a separate `feedback` table keyed by `(thread_id, anchor_seq)` with no Langfuse join key. `/api/ticket` does not run under `observe_turn`.

## Goals / Non-Goals

**Goals:**
- Every chat turn root carries platform, entry point, bot versions, turn_seq, latency_ms, and ticket_id when known — in both sinks.
- Thumbs feedback becomes a Langfuse BOOLEAN score on the matching trace when joinable; session-level score as fallback.
- Best-effort only: missing headers, missing versions, Langfuse down → chat and Postgres unchanged.

**Non-Goals:**
- Raw client code (CHO-287).
- Replacing the `feedback` table.
- Requiring frontend version at build time (optional header).

## Decisions

**1. Headers, not body fields.** `X-Platform`, `X-Screen-Name`, `X-Frontend-Version` ride next to the auth triple so `/api/chat`, `/api/feedback`, and `/api/ticket` share one path. Bodies keep `extra="ignore"` IDOR posture.

**2. Root metadata + `version=` on the Langfuse observation.** Context keys live in span `metadata` (both sinks). Langfuse native `version` gets `backend_version` when present.

**3. `turn_seq` + `lf_trace_id` on the root for feedback join.** Just before `done`, bind `thread.turns[-1].seq`. Extract Langfuse trace id from the OTel span context when ending the root. Feedback looks up recent `agent_traces` rows for the thread, matches `metadata.turn_seq`, scores that `lf_trace_id`; if none, scores by `session_id`.

**4. Ticket stamp.** Agent path: `bind_ticket_id` while the root is open. Help-card `/api/ticket`: a short-lived Langfuse root named `raise_ticket` with the same session identity and `ticket_id` metadata (no Postgres agent_traces row — that path has no observe_turn today; documenting the asymmetry).

**5. `BOT_VERSION` env.** Compose / `docker run` injects the image tag (e.g. `backendv1.0.11`). Absent → omit the field.

## Risks

- Feedback before the async persist finishes → session-level score fallback.
- Help-card tickets have no Postgres mirror row (pre-existing instrumentation gap).
