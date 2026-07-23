# CHO-244 — design

Grounded in two spikes against the installed **deepeval 4.1.3** (`uv run --with deepeval`).

## Spike findings (why the shape is what it is)

- `trace_manager.configure(mask, environment, sampling_rate, confident_api_key, anthropic_client, openai_client, tracing_enabled)` — takes a `mask` callable, a `tracing_enabled` gate, and `confident_api_key`. No key → deepeval logs "Skipping trace posting" and no-ops gracefully.
- `@observe` **works on async generators** — so the streaming model round can be an observed span that still yields SSE deltas.
- The synchronous `trace()` context manager **warns when used inside an async method** ("may lead to unexpected behavior") — so the root turn uses `@observe(type="agent")` on the async generator, NOT `with trace()`.
- `update_llm_span(model, input_token_count, output_token_count, ...)` is the manual hook for the streamed round (auto-patch only intercepts `messages.create`, and we use `messages.stream`).
- `update_current_trace(thread_id, user_id, input, output, tags, metadata, ...)` sets trace-level fields; `update_current_span(input, output, retrieval_context, name, metadata, ...)` sets span-level fields and **overrides** auto-captured input/output.

## Decision 1 — closures, not decorated cores (PII containment)

`@observe` captures the wrapped function's arguments as the span input. Our cores (`dispatch_outcome(name, input, ctx)`, `run_kb_search(params, ctx)`, the loop) take `ctx: ToolCtx`, which holds the **SSO JWT, session id, client code** — plus non-serializable `http_client`/`pg_pool`. Decorating them directly would serialize secrets into the trace.

So every observed function is a **thin wrapper taking only safe args**; the unsafe dependencies (`ctx`, `client`, `pool`, raw `kwargs.messages`) are captured in a **closure** and never appear in the signature:

```
observe_turn(*, message, thread_id, user_id, run)          # run = lambda: _chat_events(...)
observe_model_round(*, model, open_stream, holder)         # open_stream = lambda: client.messages.stream(**kwargs)
observe_tool(*, name, tool_input, run)                     # run = lambda: dispatch_outcome(name, input, ctx)
observe_retrieval(*, query, run)                           # run = lambda: hybrid_search(pool, query, emb, k)
```

Each wrapper immediately calls `update_current_span/trace(input=<safe, masked>)` so even the safe args are shaped deliberately. A global `mask` is the second layer.

## Decision 2 — mask (defense-in-depth)

`configure(mask=redact)` runs on all span inputs/outputs before export. `redact` walks dicts/lists/strings and redacts: JWT-shaped (`ey…`) and long opaque tokens, PAN (`[A-Z]{5}[0-9]{4}[A-Z]`), emails, 10-digit phones, and any dict key in a denylist (`authorization`, `sso_jwt`, `session_id`, `sessionId`, `client_code`, `accessToken`, `token`, `pan`, `dob`, `email`, `phone`, `bank`). Unit-tested directly.

## Decision 3 — streaming llm span via a holder

A generator can't `return` the final message the loop needs. `observe_model_round` yields text deltas (streamed to SSE) and stashes the final message in a caller-passed `holder` dict, then records `update_llm_span(model, input_token_count, output_token_count)` from `final.usage`. The loop reads `holder["final"]` to continue exactly as before.

## Decision 4 — config gating & safety

- `tracing_enabled = CONFIDENT_API_KEY present OR DEEPEVAL_TRACING=1`. When disabled, the wrappers are pass-throughs (no span objects created) — zero latency.
- `configure()` is wrapped in try/except at startup: a tracing init failure logs a warning and leaves chat fully working.
- Export is deepeval's background thread; the SSE path never blocks on it.
- `environment` = `DEEPEVAL_ENV` (default `development`); `sampling_rate` = `DEEPEVAL_SAMPLING_RATE` (default `1.0`).

## Non-goals (this change)

- No eval metrics / `metric_collection` attached yet (tracing first; evals are a follow-up).
- No auto-patch of the Anthropic client (we manually instrument the stream).
