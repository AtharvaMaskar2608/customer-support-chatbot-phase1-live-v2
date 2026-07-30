## Context

`tracing.py` assembles one `_Trace` per `/api/chat` turn: a flat list of `_Span` records (`agent` | `llm` | `tool` | `retriever`) linked by `parent_id`, opened and closed exclusively by five helpers — `observe_turn`, `observe_model_round`, `observe_tool`, `observe_embedding`, `observe_retrieval`. At turn end `_schedule_persist` fires a background write to `agent_traces`. Identity is deliberate and already litigated: `user_id` is `_stable_id(client_code)` (salted HMAC), and `thread_id` is the conversation-store `Thread.id`, bound by `bind_conversation_thread` after CHO-275 found that grouping by hashed `session_id` "kept rolling up after reset" when Main Menu mints a new thread.

Two properties of the existing implementation constrain the design more than they first appear:

1. **Span timestamps are monotonic, not wall-clock.** `_now_ms()` is `time.perf_counter() * 1000` — an arbitrary origin. `_Trace` carries no absolute time at all; only the DB row's `created_at` anchors a turn in real time.
2. **The Langfuse v4 SDK is built for live instrumentation.** It is OpenTelemetry-based; observations are created through context managers, decorators, or `start_observation`, with parenting via OTel context or an explicit `trace_context`. Explicit `start_time`/`end_time` for backfilling a finished tree is not documented (it may be reachable through the underlying OTel span API, but that is unverified).

Together these rule out the otherwise-obvious design of replaying the completed tree at persist time.

## Goals / Non-Goals

**Goals:**
- Every span that reaches Postgres also reaches Langfuse, with identical shape and identical redaction.
- The two stores stay **joinable** — a Langfuse trace can be pivoted to its `agent_traces` row and back.
- Langfuse being slow, down, misconfigured, or absent changes nothing about the chat response or the Postgres write.
- The PII guarantees of `observability-tracing` bind the new sink as strongly as the old one.

**Non-Goals:**
- Not replacing `agent_traces`, the CHO-262 trace viewer, or the CHO-276 eval harness. Postgres stays the system of record.
- Not adopting Langfuse prompt management, datasets, or LLM-as-judge evals in this change — those are the eventual prize, but each is its own change once traces are flowing.
- Not instrumenting anything that is not already instrumented. If a code path has no span today, it gets none here.
- Not making Langfuse a hard dependency of the backend. Absent config, the import is unused and the sink is inert.

## Decisions

**1. One instrumentation, two sinks — inside the existing `observe_*` helpers.**
Those five functions are the only places a span is opened or closed, so adding a Langfuse span beside the internal `_Span` gives exact parity with no drift and no new call sites. Langfuse times its own spans in real time, which sidesteps the `perf_counter` problem entirely.
*Alternative considered — replay the finished `_Trace` at persist time:* rejected. It needs explicit start/end timestamps the SDK does not document, and it needs a wall-clock anchor the span model does not carry. It is the more attractive design on paper (all mirror work strictly after the response) and should be revisited if Langfuse documents timestamped ingestion.
*Alternative considered — a second, independent instrumentation pass:* rejected outright. Two sets of span boundaries would drift the moment either is edited.

**2. Langfuse `session_id` is the conversation `Thread.id`; the FinX SSO session id is never sent, in any form that could authenticate.**
Langfuse's "session" groups traces into one conversation, which is exactly our thread. FinX's `session_id` is a *different* concept wearing the same word — and it is a **live credential**: per `docs/finx_android_api_reference.html` and `CLAUDE.md`, the P&L / Ledger / Tax endpoints authenticate with the SessionId as the `authorization` header. It is already in `_DENY_KEYS`, and `observability-tracing` states plainly that "the raw session token and the raw client code SHALL never be stored."
Putting it in Langfuse's `session_id` would therefore be wrong twice over: it would re-open the CHO-275 roll-up-after-reset bug, and it would place a working auth token in the observability system. When correlation to an SSO session is genuinely needed, `_stable_id(session_id)` goes into metadata as `finx_session_hash` — same salt, so it correlates, but it cannot authenticate anything.
*Consequence to accept:* because a thread is minted on every Main Menu reset, one user pressing Main Menu three times appears as three Langfuse sessions. That is correct — it matches the Postgres cost buckets — but "everything this user did today" becomes a `user_id` filter, not a session view.

**3. Send the same `_stable_id()` HMAC to Langfuse, not raw identifiers.**
Self-hosting makes raw identifiers *defensible* (nothing leaves our infrastructure), but sending the same hash Postgres stores is strictly better: the two stores remain joinable on `user_id` and `thread_id`, which is most of the point of a mirror. Raw ids would also contradict a requirement that is currently in force. If resolving a hash to a real customer is ever needed, that is a separate, access-controlled lookup — not a property of the trace store.

**4. `redact()` is mounted as the Langfuse export mask, not re-implemented.**
The SDK's `mask_otel_spans` hook runs on the batch-span-processor worker thread before export. Reusing the existing function means the mirror cannot fall behind the Postgres path as the denylist grows; one definition governs both sinks. This is what makes the modified `observability-tracing` requirement enforceable rather than aspirational.

**5. Flag off by default, and every failure is a no-op.**
`LANGFUSE_TRACING=0` by default, matching how `AGENT_CONTEXT_CURATION` shipped. The SDK is async and batched, so steady-state cost is near zero, but the guarantee must not rest on that: client construction, span emission, and flush are each individually guarded, and a raised exception is logged by type and swallowed. `observability-tracing`'s "Tracing never degrades the chat path" already binds this; the mirror inherits it.

## Risks / Trade-offs

- **[Risk]** The SDK opens real OTel spans during the turn, so a pathological exporter could add latency to the hot path. → **Mitigation**: batched async export is the SDK's documented default; the flag gives an instant kill switch; the never-degrade test asserts a turn completes normally with the exporter raising on every call. **Measured against a genuinely stopped Langfuse (not a mock): the turn took 3.7 ms and the `agent_traces` row was still written.** The hot path is unaffected because export is queued, not awaited.
- **[Known]** That same measurement showed the *shutdown* flush blocking **~3.35 s** against a dead endpoint — SDK retry backoff, not a single timeout. It is off the request path (app shutdown only) and well inside Docker's default 10 s SIGTERM grace, so it is recorded rather than engineered around: adding a client timeout would not shorten a connection-refused retry loop, and a config knob for it would be scope this change does not need. Worth revisiting only if container stop time becomes a deploy problem.
- **[Risk]** Self-hosted Langfuse via Docker Compose has, by Langfuse's own documentation, no HA, no scaling, and no backups. → **Mitigation**: accepted deliberately. This is a mirror; losing it loses a UI, not data. If Langfuse ever becomes the place people actually look, that promotion is the moment to revisit the deployment, and it should be an explicit decision rather than a drift.
- **[Risk]** Five more containers (web, worker, Postgres, ClickHouse, Redis, MinIO) on a prod box that today runs two, where ECR is IAM-blocked and images are hand-carried as tarballs. → **Mitigation**: verify outbound registry pulls from the prod host **before** committing to the deployment; if they are blocked, every Langfuse image joins the tarball path and that ongoing cost should be weighed against the benefit.
- **[Trade-off]** Dual-write means two systems to keep in sync as the span model evolves. Accepted because both writes originate from one assembled tree; the coupling is at the helper, not at the call sites.

## Migration Plan

No data migration; no backfill of historical traces (Langfuse starts from first write). Ship with the flag off, verify locally against a real turn, enable in prod only after the stack is stood up and reachable. Rollback is `LANGFUSE_TRACING=0` and a container recreate — Postgres tracing is untouched throughout, so there is no state to unwind.

## Open Questions

- Can the prod host pull from Docker Hub / ghcr at all? This is the single question most likely to change the deployment plan, and it should be answered before the infrastructure work starts.
- Does `finx_session_hash` earn its place in metadata, or is thread + user enough? Leaving it out is the smaller surface; it can be added once a real correlation need appears.
- Should the `llm` span map to a Langfuse `generation` with native usage/cost fields, or carry our own `cost_inr` in metadata? Native typing gives better dashboards; our own figure is what CHO-278 tuned and what the existing viewer shows. Likely both, with ours authoritative.
- Does the eval harness eventually move to Langfuse datasets? Out of scope here, but it is the reason this change is worth making, and the answer shapes whether the mirror stays a mirror.
