## 0. Local Langfuse stack (infrastructure, no repo code)

- [x] 0.1 Remap the Langfuse compose Postgres host port off `5432` (a native host Postgres already owns it, which is why `langfuse-postgres-1` sat in `created` and `web`/`worker` never started). Done via an untracked `docker-compose.override.yml` at `~/learning/langfuse/`, leaving the upstream file pristine. **`ports: !override` is required** — Compose appends to list fields, so a plain override adds a second mapping and still tries to bind 5432. Now `127.0.0.1:5544:5432`; `DATABASE_URL` targets `postgres:5432` over the compose network, so nothing inside the stack changed.
- [x] 0.2 Replace the `# CHANGEME` secrets with generated values. 12 of the 14 markers are `${VAR:-default}` parameterized (the other 2 are comment lines), so this was done with an untracked, `chmod 600` `.env` in the compose directory rather than by editing the tracked file. `.env` is gitignored there. Interdependencies handled: `DATABASE_URL` embeds `POSTGRES_PASSWORD`, and all three `LANGFUSE_S3_*_SECRET_ACCESS_KEY` match `MINIO_ROOT_PASSWORD`. `ENCRYPTION_KEY` verified 64 hex chars.
- [x] 0.3 `docker compose down -v` (required: ClickHouse fixes its user password on first volume init, and the volumes had been created with the public defaults — safe here because `langfuse-web` had never started, so there was no project, user, or trace data). Then `docker compose up -d`: all six containers healthy, `/api/public/health` returns 200 on `:3000`. Native host Postgres on 5432 untouched.
- [x] 0.4 Org + project created in the UI (`customer-support-chatbot`, id `cms71pokd0006n306qwrpzu2s`); `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL` written to the untracked, gitignored **root** `.env`. Verified two ways: the repo's own `config._root_env_value` parses all three (it strips surrounding quotes, so the quoted form is fine), and the credentials authenticate against `GET /api/public/projects` → HTTP 200.

## 1. Config

- [x] 1.1 `backend/app/config.py`: `langfuse_tracing_enabled()` (env `LANGFUSE_TRACING`, **default off**), `langfuse_public_key()`, `langfuse_secret_key()` (via the existing `_secret` path), `langfuse_base_url()`. Follow the file's existing accessor conventions.
- [x] 1.2 Add the four keys to `.env.example` as commented entries, with the two credentials clearly marked as secrets that live only in `.env`.
- [x] 1.3 `backend/pyproject.toml`: add the `langfuse` dependency; note it pulls the OpenTelemetry SDK, and confirm no version conflict with existing deps.

## 2. Exporter lifecycle

- [x] 2.1 A small module owning the client: constructed once, only when the flag is on AND both credentials and base URL are present; otherwise every entry point is a no-op and no client exists.
- [x] 2.2 Mount `redact()` as the SDK's `mask_otel_spans` hook so one mask definition governs both sinks (spec: "A second sink inherits the same mask").
- [x] 2.3 Wire construction and a shutdown `flush()` into the app lifespan in `backend/app/main.py`.
- [x] 2.4 Guard every entry point so a raised exception is logged by type and swallowed — never span contents, never propagated to the request.

## 3. Mirror the span tree

- [x] 3.1 `observe_turn`: open the Langfuse root, set `session_id` = conversation `Thread.id` and `user_id` = `_stable_id(client_code)`. Note the thread id is not known at turn start — it arrives via `bind_conversation_thread`, so the trace attributes must be set or updated once it is bound.
- [x] 3.2 `observe_model_round`: emit as a Langfuse `generation` carrying model and token usage; decide per design open-question whether `cost_inr` rides native fields or metadata (ours stays authoritative either way).
- [x] 3.3 `observe_tool`, `observe_embedding`, `observe_retrieval`: emit as observations parented exactly as the internal `_Span.parent_id` records — `retriever` spans under their `tool`, matching CHO-285's `kb_embed`/`kb_search` siblings.
- [x] 3.4 Confirm no new instrumentation appears in `loop.py`, `kb/router.py`, or the tool layer — the five helpers are the only touch points.

## 4. Tests

- [x] 4.1 Identity mapping: Langfuse `session_id` equals the `agent_traces` `thread_id`, `user_id` equals the stored HMAC, for the same turn.
- [x] 4.2 Main Menu reset mints a new session id rather than rolling up (the CHO-275 regression, restated for the mirror).
- [x] 4.3 Credential guard: with an SSO session id and raw client code in flight, neither appears anywhere in the exported payload — session field, inputs, outputs, or metadata.
- [x] 4.4 Never-degrade: with every export call raising, the turn streams normally AND the `agent_traces` row is still written complete.
- [x] 4.5 Inert without config: flag off (and flag on with credentials missing) constructs no client and attempts no network call; trace behaviour is byte-identical to pre-change.
- [x] 4.6 Mask parity: a value that `redact()` scrubs from the Postgres row is equally absent from the exported span.
- [x] 4.7 `cd backend && uv run pytest` green.

## 5. Verify locally

- [x] 5.1 Drove the **real** `observe_*` helpers with the **real** SDK against the **real** local instance (fake model stream + fake pool; everything on the Langfuse side genuine). Read back over `GET /api/public/traces/{id}`: one trace, `chat_turn` → `model_round` (typed GENERATION, `model=claude-sonnet-4-6`, `usage={input: 7077, output: 42}`) + `search_knowledge_base` → `kb_embed`, `kb_search`. `sessionId` = thread UUID, `userId` = the HMAC. Verified via the API rather than the UI (no browser available here).
- [x] 5.2 Mask verified **on the real export path**, which is the stronger form of this check: a raw JWT, the SSO session id, and the raw client code were all injected into the turn; none appear anywhere in the fetched trace (4 `[REDACTED]` markers present, hashed user id present). Separately, a unit test asserts the runtime `lf` handle never reaches the persisted span JSON.
- [x] 5.3 Covered by unit test `test_main_menu_reset_starts_a_new_session` (two threads ⇒ two distinct `session.id`, one shared `user.id`). **Not** exercised live against the UI.
- [x] 5.4 Stopped `langfuse-web` and `langfuse-worker` and re-ran the turn against a genuinely dead endpoint (stronger than the raising mock in 4.4): **turn = 3.7 ms**, `agent_traces` INSERT still written, reply streamed intact. The shutdown flush blocked ~3.35 s on retry backoff — off the request path, recorded in `design.md`.

- [x] 5.5 **Live end-to-end through `POST /api/chat`** with the real backend, real Anthropic calls, the real KB (1,102 `qa_chunks` over the `:5433` tunnel), and real `agent_traces` persistence. Four turns run:
  - **KB turn** ("when does intraday square off happen"): reconciled Postgres ↔ Langfuse — **6 spans both, names match, nesting matches, `thread_id`==`sessionId`, `user_id`==`userId`**. Two `model_round` GENERATIONs with correct models and usage. Incidentally confirmed CHO-284 live: the `tool` SSE event fired *before* any `text` event.
  - **Main Menu reset** then a second turn: a new thread was minted and landed in its **own** Langfuse session — no roll-up (CHO-275 held).
  - **Failed FinX tool** (`get_holdings` with a dummy SSO → `is_error`, `NO_DATA`): **pg 4 spans / lf 4 spans, MATCH** — the error path mirrors completely, which is exactly the defect found and fixed during this section.
  - **Real account data** (`get_holdings` succeeding on a real session id and client code): scanned both stores for PAN / JWT / email / phone / raw client code / raw session id — **zero matches in either**. A `[A-Za-z0-9_-]{32,}` scan flagged 5 strings in Langfuse only; all were accounted for (the SDK's own `pk-lf-…` public key stamped into span metadata, our thread UUID which is the intended join key, and internal scope ids). No leak.
- [x] 5.6 **Why the PII result is stronger than "the mask worked":** inspecting a real tool span showed `input={}`, `output=null`, `metadata={is_error,error_code,duration_ms}` — the upstream response body **never enters a span at all**. So there is no customer PII on that path to mask. The real exposure surface is the user's own message (`model_round.input`), which the mask does cover.

### Still not verified

- [ ] 5.7 Visual confirmation in the Langfuse **UI** (all of the above was verified over the public API — no browser available in this environment).
- [ ] 5.8 A turn with a genuinely valid **SSO JWT**. The report tools authenticate with the SessionId, which is why `get_holdings` returned live data, but the SSO-authenticated paths (Get Profile, CML) were never exercised.
- [ ] 5.9 Sustained-load behaviour: the SDK batches exports, and `flush_at`/`flush_interval` are still at defaults nobody has justified. Also a p95 latency delta with the flag on vs off — the 3.7 ms figure is one synthetic turn.
- [ ] 5.10 Automate the reconciliation (span-count/shape parity per `thread_id`) as a recurring check rather than a one-off script, so a future divergence is caught without inspiration.

## 6. Deploy (user-gated)

- [ ] 6.1 **Answer first:** can the prod host pull from Docker Hub / ghcr? If not, all six Langfuse images join the hand-carried tarball path and that ongoing cost should be weighed before proceeding (design open question).
- [ ] 6.2 Stand up the stack on the prod host with its own generated secrets — never the local ones, never the upstream defaults.
- [ ] 6.3 Ship the backend image with the flag **off**, confirm no behaviour change, then enable and confirm traces arrive.
- [ ] 6.4 Rollback rehearsed: `LANGFUSE_TRACING=0` + container recreate leaves Postgres tracing untouched.

## 7. Ship

- [ ] 7.1 `git-sync` with issue key CHO-286, branched off `main` (not stacked on any other change).
- [ ] 7.2 `linear-connector` — In Progress at implementation, summary + In Review at PR, Done at merge. Note Linear MCP was unauthenticated as of 2026-07-30 and may need reconnecting first.
