# CHO-246: user-name-context

## Why

The agent knows nothing about who it's talking to — it never receives the user's name — and it doesn't guard against requests for someone else's data. In the CHO-246 report, the user typed "Provide me harsh's pnl report" and the bot replied "Sure — let's set it up" as if it would fetch another person's P&L. (The tool layer is already safe — reports always use the header-derived client code — but the bot's *response* is misleading.) Product wants: (1) fetch the user's name from the Profile API into the prompt context, and (2) a guardrail so the bot only ever works with the logged-in client's own data.

## What Changes

- **Name in context**: the agent prompt SHALL carry the logged-in user's first name so the bot can address them and recognise self-reference. Because the prompt prefix is frozen for cache stability, the name rides in the **volatile tail block** (with the IST status line, after the cache breakpoint) — never in the cached prefix. The name is fetched server-side from the Profile API (the same `derive_first_name` the greeting uses), cached per thread so it costs one fetch per conversation.
- **Self-only data guardrail**: the prompt SHALL instruct that only the logged-in client's own data exists for the assistant; a request for anyone else's account/reports/details gets a brief "I can fetch reports only for your account" and no tool call — the bot never pretends to fetch a third party's data. (The tool layer already enforces the client code from headers; this fixes the conversational behaviour.)
- Backend-only: `prompt.py` (volatile block + rule) and a per-thread profile-name fetch in the agent path.

## Open decisions

- **Name source**: fetch server-side from the Profile API in the agent path (recommended — trustworthy, not client-spoofable), cached per thread. Alternative: the frontend passes `firstName` in the `/api/chat` body (it already has it from the greeting), cheaper but client-controlled. Recommend server-side.

## Capabilities

### Modified Capabilities

- `agent-loop`: the prompt SHALL carry the logged-in user's first name (in the volatile, post-cache-breakpoint block) and instruct the assistant that only the logged-in client's own data exists — a request for another person's data is declined briefly, never fetched or pretended.

## Impact

- Backend: `backend/app/agent/prompt.py` — add the first name to the live tail block (never the cached prefix; the snapshot template keeps a placeholder so the hash stays stable); add the self-only-data rule. A per-thread name fetch (reuse `greeting._fetch_profile` / `derive_first_name`) in the agent path (`loop.py` / `router.py`), cached on the thread — shares the profile call opportunity with CHO-245.
- PII: the first name is already permitted context (same as the greeting); it must never reach logs (existing posture). No new upstream field beyond what the greeting derives.
- `uv run pytest` gate (name-injection + third-party-decline tests; snapshot hash stable via placeholder).
- Linear: CHO-246 · branch `cho-246-user-name-context`. Relates to CHO-241 (data-isolation), CHO-245 (shared profile fetch).
