# CHO-272: prompt-engineering-playground

## Why

Operators need a safe place to experiment with AskFinX system + primed prompt
text without changing production `/api/chat` behavior.

## What

- Isolated playground package (`backend/app/playground/`) + frontend entry
  (`playground.html`), gated by `PLAYGROUND_TOKEN` (404 when unset — same
  posture as the trace viewer).
- `GET /api/playground/defaults` — production prompt constants as the starting
  draft.
- `POST /api/playground/chat` (+ reset) — same agent tools/SSE contract, but
  accepts editable `systemPrompt` / `primedInstructions` in the body.
- Playground sessions namespaced (`pg:…`) so they never collide with production
  conversation threads.
- Drafts persist in the browser (`localStorage`) only — no prompt DB.

## Out of scope

- Changing production `SYSTEM_PROMPT` / `PRIMED_INSTRUCTIONS` as the live
  source of truth for `/api/chat`.
- Prompt versioning, shared team drafts, or shipping the playground UI in the
  production docker image by default.
