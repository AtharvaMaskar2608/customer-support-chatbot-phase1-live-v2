## Why

`backend/app/agent/tracing.py` already captures every `/api/chat` turn as an execution graph and persists it to our own Postgres (`agent_traces`, CHO-261), with an admin-gated trace viewer over it (CHO-262). That machinery is sound and stays. What it does not give us is the surrounding workflow — dataset-backed evals, prompt versioning, a UI a non-engineer can be pointed at without an admin gate — and building those ourselves is a much larger programme than adopting a tool that has them.

Langfuse is that tool, and the fit is unusually close. Its data model (session → trace → nested observations, with `user_id` / `session_id` / `tags` / `metadata` propagating from the trace to every child) maps almost one-to-one onto the `_Trace` / `_Span` tree we already assemble, including the typed `generation` observation that carries token usage and cost the way our `llm` span already does. Its Python SDK (v4, OpenTelemetry-based) takes a client-side `mask_otel_spans` hook that runs on the exporter thread before anything leaves the process — the same shape as our existing `redact()`.

This change adds Langfuse as a **mirror**, not a replacement: Postgres remains the system of record, and Langfuse is a second, best-effort sink over the same assembled tree. Nothing that reads `agent_traces` today (the trace viewer, the eval harness) changes or regresses. The deployment is **self-hosted**, so no trace data leaves our infrastructure.

## What Changes

- Emit each turn's spans to a self-hosted Langfuse instance in addition to Postgres, from inside the five existing `observe_*` helpers — the only places a span is ever opened or closed. No new instrumentation in `loop.py`, `kb/router.py`, or the tool layer.
- Map identities so the two stores stay joinable: Langfuse `session_id` ← the conversation `Thread.id`, Langfuse `user_id` ← the same `_stable_id()` HMAC of the client code that Postgres already carries.
- Reuse the existing `redact()` as the Langfuse export mask, so the mirror inherits the PII posture rather than re-implementing it.
- Gate the whole sink behind `LANGFUSE_TRACING`, **off by default**, and make every Langfuse failure path a no-op for the chat response and for the Postgres write.
- No change to `agent_traces`, the trace viewer, the eval harness, tool schemas, prompts, or any frontend code.

## Capabilities

### New Capabilities
- `trace-mirror`: mirroring the assembled per-turn execution graph to a self-hosted Langfuse instance — the identity mapping, the masking guarantee, the flag, and the best-effort failure semantics that keep the mirror subordinate to the Postgres system of record.

### Modified Capabilities
- `observability-tracing`: the "No PII or secrets in stored traces" requirement is extended so its guarantees bind **every** sink the span tree is written to, not only the Postgres row — closing the gap that would otherwise let a second exporter carry what the table is forbidden to hold.

## Impact

- `backend/app/agent/tracing.py` — the five `observe_*` helpers gain a parallel Langfuse span; a small exporter module holds the client lifecycle.
- `backend/app/config.py` — `LANGFUSE_TRACING`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` accessors, plus `.env.example` entries. The two keys are **secrets** and live only in the untracked `.env`.
- `backend/pyproject.toml` — new `langfuse` dependency (pulls the OpenTelemetry SDK).
- `backend/app/main.py` — client construction and shutdown flush on the app lifespan.
- `backend/tests/` — new coverage for the identity mapping, the mask, the flag, and the never-degrade guarantee.
- **Infrastructure (outside this repo):** a self-hosted Langfuse stack — `langfuse-web`, `langfuse-worker`, Postgres, ClickHouse, Redis, S3/MinIO. Langfuse's own docs warn the Docker Compose path has no HA, scaling, or backups; acceptable for a mirror whose system of record is elsewhere, and recorded as an accepted trade-off in `design.md`.
- Independent of every other open change. Touches no file that CHO-263 (recitation) or CHO-278 (TTL) would touch.
