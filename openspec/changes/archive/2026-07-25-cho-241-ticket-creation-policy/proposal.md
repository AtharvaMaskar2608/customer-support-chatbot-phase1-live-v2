# CHO-241: ticket-creation-policy

## Why

The bot must **never create a support ticket on its own judgement**. A Freshdesk create should fire only when the user explicitly asks (or taps "Raise a ticket"). The LLM may *detect* that a ticket would help — but detection should produce an **offer**, never an action. The current tool guidance says "never preemptively", but a prompt alone was trusted once and produced an unwanted ticket (per the CHO-241 report), so product wants the rule hardened with a code-level guarantee.

## What Changes

- **Prompt policy** (`prompt.py` / tool guidance):
  - You may *offer* to raise a ticket, but never *decide* to. Never call `raise_support_ticket` unless the user's latest message is an explicit request to raise/escalate/complain or "connect me to a human", or they accept your escalation offer.
  - Never announce ticket creation as your plan ("let me raise a ticket"). When a ticket would help, ask "Want me to raise a ticket so the team can take this up?" and stop.
  - Offer at most once per issue; if declined or ignored, don't offer again for that issue.
  - Never offer a ticket while refusing a request (security, another client's data, policy) — refuse briefly and stop.
  - Never narrate retrieval / internal steps ("the search results show…", "let me search").
- **Server-side hardening** (orchestrator): reject a model-emitted `raise_support_ticket` whose triggering user turn is neither an explicit escalation request (allowlist match) nor an affirmative acceptance of the assistant's own preceding escalation offer; a rejected call returns an error `tool_result` so the model offers instead of acting. The help-card chip path (`POST /api/ticket`) is inherently user-initiated and unaffected.
- Backend-only. No change to the ticket payload/contract.

## Open decisions

- **Server guard**: include it (recommended — "prompts steer; this one *guarantees*") or ship prompt-only. Default: include.
- Exact allowlist / "accepted the offer" detection is an implementation detail — keep it conservative (err toward letting an explicit request through; let the prompt handle nuance).

## Capabilities

### Modified Capabilities

- `agent-loop`: ticket creation SHALL be user-initiated only — the model offers, never decides; and the orchestrator SHALL reject a model-emitted ticket-create call not triggered by an explicit user escalation request (or acceptance of an offer), returning an error tool_result rather than raising a ticket.

## Impact

- Backend: `backend/app/agent/prompt.py` (policy + example) and `backend/app/agent/tools.py` (raise_support_ticket description) — prompt-hash change expected.
- Backend guard: `backend/app/agent/tools.py` dispatch (or `loop.py`) — precondition check on `raise_support_ticket` against the triggering user turn; error tool_result on rejection. Reuses the thread's latest user turn.
- Overlap: the self-only-data guardrail is owned by CHO-246 ("only your data / decline others"); CHO-241 owns "don't offer a ticket while refusing".
- `uv run pytest` gate — tests: a preemptive ticket call is rejected; an explicit request goes through; the help-card path is unaffected.
- Linear: CHO-241 · branch `cho-241-ticket-creation-policy`. Relates to CHO-246, CHO-252.
