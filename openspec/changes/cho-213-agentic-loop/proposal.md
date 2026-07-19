# CHO-213 · Agentic Loop

## Why

Every capability the widget has today — six report/data flows plus KB retrieval (CHO-212) — is reachable only through deterministic button flows or a stateless search endpoint; free text still has nowhere intelligent to go. This change adds the **agentic chat layer**: a Claude tool-use loop that receives free text, orchestrates the existing flows and the KB as tools, asks for missing parameters, and answers — turning Choice Jini from a menu into an agent. The conversation store it introduces doubles as the training corpus for a future fine-tuned support model, so its format is designed for that from day one.

## What Changes

- **Agent loop** (`POST /api/chat`): a manual `while stop_reason == "tool_use"` loop over the Anthropic Messages API (Python SDK). Inner guard ≈5 tool rounds per user message; assistant/tool messages fed back wire-faithfully (`tool_use` blocks echoed, `tool_result` blocks in user turns, parallel tool calls answered in one message, errors returned as `is_error` tool_results so the model recovers by re-asking). **Every round streams** (SDK `messages.stream()`), and `/api/chat` responds as an SSE stream — text deltas reach the widget as they generate; tool activity and artifacts arrive as typed events.
- **Tool registry — functions, not HTTP self-calls**: each existing flow's core logic (P&L, Ledger, Tax, Contract Notes, Holdings, Pay-in/Pay-out, Brokerage, KB search) is extracted from its FastAPI route into a shared async function; the route and the tool registry both call the same core, so route contracts are byte-identical after the refactor. Tool schemas expose **only user-intent parameters**; credentials (SessionId, SSO JWT, client code) are injected server-side via a per-request `ctx` built from authenticated headers — the model has no field to put a client code in (IDOR defense carries over).
- **Slot filling via prompting + validation**: required params in schemas; system prompt forbids inventing values and mandates bundling all missing fields into one question; Pydantic validation in handlers bounces bad/missing values back as `is_error` tool_results. Today's date in the system prompt for relative-date resolution.
- **Caps — enforced in code, all env-configurable**: max **2** clarifying questions per task, max **10** user turns per task window, **20**-user-message session backstop. A *task window* is the conversation since the last resolution event (an assistant turn that ended with ≥1 successful tool call); resolution resets both per-task counters. Any cap trip → the reply suggests escalation (the Freshdesk raise-ticket *tool* is a later change).
- **Conversation store**: Postgres `threads` / `turns` / `prompt_snapshots`. Each turn stores the exact Anthropic content-block array (JSONB) plus meta (model, stop_reason, usage, latency / tool name, is_error); prompt snapshots (system prompt + tool schemas by hash) make every thread a self-contained training example. Writes happen at every step boundary through a **bounded asyncio queue with a single background writer task** — the chat path never awaits the DB; if the DB is down, persistence degrades to best-effort and chat keeps working. Counters are derived from turns, never stored. Retention: keep everything; redact at training-export time.
- **Minimal frontend wiring**: the chat shell's free-text input posts to `/api/chat`, consumes the SSE stream (text rendered incrementally as it arrives), and renders structured artifacts (file-download card via existing `fileToken` mechanics, data cards from tool-result envelopes).

Out of scope (deliberate follow-ups): the escalation tool itself (Freshdesk raise-ticket API), mid-flow free-text breakout with flow-snapshot handover and slot-picker quick-replies on the frontend (the store's `flow_event` turn kind and the seedable-slot design already accommodate it), the training-export/redaction script, and any model fine-tuning.

## Capabilities

### New Capabilities

- `agent-loop`: the `/api/chat` orchestration — tool-use loop, slot-filling behavior, caps and task-window/resolution semantics, escalation suggestion, credential-isolation contract.
- `agent-tool-registry`: the tool catalog — schema + handler pairs wrapping the extracted flow cores and KB search, ctx injection, error mapping to `is_error` tool_results, invariant that existing route contracts are unchanged.
- `conversation-store`: threads/turns/prompt_snapshots persistence — wire-faithful turn format, per-step write points, async single-writer queue, degraded mode, retention.

### Modified Capabilities

- `report-chat-shell`: the chat input, currently limited to the guided-flow entry points, gains free-text send → agent reply rendering (text + artifacts).

## Impact

- New backend: `app/agent/` (loop, registry, ctx, store writer); refactor of `app/report.py`, `app/reports/*`, `app/data/*`, `app/kb/` to extract core functions (routes preserved verbatim); new tables in the KB Postgres (`threads`, `turns` exist empty already; `prompt_snapshots` is new); new dependency: `anthropic` SDK; `ANTHROPIC_API_KEY` already in untracked `.env`.
- Frontend: chat shell wiring for free-text send/render.
- Config: `CLARIFY_CAP` (2), `TASK_TURN_CAP` (10), `SESSION_TURN_CAP` (20), inner-round guard, `AGENT_MODEL` (`claude-haiku-4-5` default | `claude-sonnet-4-6`), `AGENT_THINKING` (`off` default | `minimal` — mapped per model: Haiku `budget_tokens: 1024`, the API minimum; Sonnet 4.6 adaptive + `effort: "low"`) — env-overridable with code defaults.
- Security/PII: tool results entering the transcript are the already-whitelisted normalized envelopes (never raw upstream bodies); credentials never enter `messages` or the store; user free text is never logged verbatim (length/status only), matching the KB precedent. Store runs on the dev Postgres tunnel today — production needs a managed connection or the documented degraded mode.
- Compliance: factual answers only; system prompt forbids investment advice; footer untouched.
