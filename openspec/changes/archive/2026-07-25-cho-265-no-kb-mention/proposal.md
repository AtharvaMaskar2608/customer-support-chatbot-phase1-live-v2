## Why

Users must never see the bot's intermediary steps — retrieval, search retries, or internal reasoning. Jam capture on CHO-265 shows a multi-paragraph assistant reply that leaks mechanism ("I'll search our knowledge base"), search outcomes ("The search results are…"), retries ("Let me search more specifically"), guessing hedges ("This is likely…", "may involve…"), and announce-then-act ticket narration ("Let me raise a support ticket"). That breaks the illusion of a direct support assistant. Prompt guidance already has a one-liner ("Never narrate retrieval…") and CHO-241 covers ticket announce, but tool descriptions still prime "knowledge base" / "Summarize the results", and the banned list is incomplete.

## What Changes

- Expand **USER-FACING VOICE** in `backend/app/agent/prompt.py`: categorized banned patterns from CHO-265 (mechanism, process narration, retry disclosure, process-tied uncertainty, self-narration) plus allowed miss-phrasing for empty lookups — answer directly, call tools silently, offer tickets without announcing.
- Soften Anthropic-facing tool descriptions in `backend/app/agent/tools.py` so they do not teach the model to say "knowledge base", "search results", or "summarize the results". Internal tool **name** `search_knowledge_base` stays.
- **Prompt-first only** — no post-generation regex filter on streamed text (follow-up only if prompt-only proves insufficient).
- Backend / agent-loop spec only. No frontend, API shape, or loop orchestration change.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `agent-loop`: user-visible assistant text SHALL conceal retrieval and internal process — banned mechanism, narration, retry-disclosure, process-tied uncertainty, and self-narration; grounded answers SHALL be direct; empty/miss replies SHALL be factual without forbidden wording.

## Impact

- **OWN:** `backend/app/agent/prompt.py`, `backend/app/agent/tools.py` (descriptions only), `openspec/specs/agent-loop` delta, backend tests (prompt snapshot / agent tests).
- **NOT:** `EmptyState`, `ChatShell` narration / `toolCaption`, `BrokerageCard`. Jam screenshots are assistant bubbles, not UI status pills — frontend "Looking that up…" is out of this change.
- **Wave:** Wave 1 — parallel-safe with `cho-251-waiting-buffer` and `cho-259-brokerage-ui` (disjoint ownership).
- Prompt-snapshot hash will change (expected). Overlaps CHO-241 ticket announce — keep those rules; CHO-265 owns retrieval/KB/process voice broadly.
- Linear: CHO-265 · branch `cho-265-no-kb-mention`.

## Parallel apply

Wave 1 — safe with `cho-251-waiting-buffer` / `cho-259-brokerage-ui`.
