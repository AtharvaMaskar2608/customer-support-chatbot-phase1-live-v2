# CHO-244: add-deepeval-tracing-observability

## Why

The agent loop is a black box in production: when an answer is wrong we cannot see which step failed — was the KB retrieval empty, did a tool error, did the model burn tokens or drift from persona across a long conversation? We want DeepEval tracing so every `/api/chat` turn's execution graph (and the multi-turn thread) shows up in the Confident AI dashboard, giving us per-span inputs/outputs/latency/tokens and a foundation for async evals later (`docs/tracing/1_rag_tracing.md`, `docs/tracing/2_multi_turn_chat_tracing.md`).

## What Changes

- Add `deepeval` and initialize `trace_manager.configure(...)` once at app startup with: the PII/secret **mask**, `environment`, `sampling_rate`, and `confident_api_key` (new `CONFIDENT_API_KEY` secret). **Config-gated**: with no key (and no explicit enable) tracing is a no-op — zero added latency, no behavior change.
- Instrument the agent loop as a trace tree (new module `app/agent/tracing.py`):
  - **agent** root span per turn, stitched into a multi-turn thread via `thread_id = X-Session-Id`, `user_id = X-User-Id`.
  - **llm** span per streamed model round — manual (`update_llm_span`) since `client.messages.stream` is not auto-patched; records model + input/output token counts.
  - **tool** span per `dispatch_outcome` call (parallel tool rounds included).
  - **retriever** span for KB hybrid search, carrying `retrieval_context` (the fused chunks) for RAG metrics.
- **PII/secret safety is a hard requirement.** DeepEval auto-captures a function's *arguments* as span input, and our cores take `ctx: ToolCtx` (SSO JWT, session id, client code). We therefore decorate only thin wrappers that receive **safe args**, passing `ctx`/client/pool via **closure** so they are never captured, and install a global `mask` (redacts JWT/PAN/DOB/email/phone/session/token-shaped values) as defense-in-depth.
- No change to the SSE contract, the loop's behavior, or any response latency (DeepEval exports in a background thread; a tracing failure never becomes a chat failure).

## Capabilities

### Added Capabilities

- `observability-tracing`: config-gated DeepEval tracing of the agent loop — a per-turn agent trace with multi-turn thread stitching and llm/tool/retriever child spans, exported to Confident AI, with mandatory PII/secret masking and zero impact on the chat path.

## Impact

- New: `backend/app/agent/tracing.py` (configure + mask + `@observe` wrappers), `backend/tests/test_agent_tracing.py`.
- Edited: `backend/app/main.py` (configure at startup), `backend/app/agent/loop.py` (agent/llm/tool spans), `backend/app/kb/router.py` (retriever span), `backend/app/config.py` (`confident_api_key()` + tracing knobs), `backend/pyproject.toml` + `uv.lock` (`deepeval`), `.env.example` (`CONFIDENT_API_KEY`).
- Dependency weight: `deepeval` pulls ~60 transitive packages (incl. `openai`, `aiohttp`) → a notably larger backend image. Called out for the deploy.
- Backend-only. Linear: CHO-244 · branch `cho-244-add-deepeval-tracing-observability`.
