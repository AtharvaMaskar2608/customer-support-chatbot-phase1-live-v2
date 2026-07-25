# CHO-264: prompt-layout-history-caching

## Why

Only the frozen prefix is cached today (`system` + primed instructions — measured **6,559 tokens**). The conversation history re-bills as fresh input on **every** model call, so cost grows quadratically: a measured 15-turn conversation costs **₹42.35** in input alone, marginal turn **₹3.86**, 91% of it tool-result envelopes.

A rolling breakpoint on the conversation tip is the fix — but on today's array it would make things *worse*. The live IST status line renders into `messages[0].content[1]` (`prompt.py:333-349` → `clock.py:467`, **minute granularity**), i.e. before all history, and caching is a strict byte-prefix match: a history breakpoint hits within a turn and essentially never across turns, and a miss bills the whole history at 1.25× instead of 1.0×. Measured: breakpoint alone **₹37.74 (−11%)**; breakpoint plus relocating the live tail past the history **₹14.31 (−66%)**. The layout move is a prerequisite, so both halves ship on one branch and one backend tag.

## What Changes

- **Phase 0 — relocate the live context (unconditional, no flag).** The IST status line and the client's first name move out of `messages[0].content[1]` into a single **trailing user message placed after all stored history**, wrapped in the repo's existing `<system-reminder>` app-generated frame (the same convention `loop.py:95-99` already uses for cap reminders, so the frame is already proven on the wire and already pinned as never-stored). `primed_messages()` becomes fully frozen: one instructions block carrying the cache breakpoint, then `"Understood."`. Cap/wrap-up reminders ride in that same trailing message. `_reminder_message` is superseded.
- **One frozen-copy edit.** `PRIMED_INSTRUCTIONS` (`prompt.py:223`) says the IST date and time is "given at the end of this message"; after the move that points at nothing, so exactly one clause is reworded to refer to the note at the end of the conversation. The **name-usage clause** is reworded in the same pass to reference the visible conversation ("if you have already used their name earlier in this conversation, do not use it again") — moving it adjacent to the generation point otherwise risks re-triggering the CHO-274 name-overuse bug. `snapshot_text()` is reordered/relabelled to match ⇒ **exactly one** new `prompt_snapshots` row.
- **Phase 1 — rolling history breakpoint (`AGENT_HISTORY_CACHE`, default on).** An ephemeral `cache_control` marker is placed on the last content block of the last **stored** message, re-placed on every model call, via **copy-on-mark** (`content[-1] = {**block, "cache_control": …}`). Copy-on-mark is mandatory, not stylistic: `Thread.messages()` (`store.py:182,188,190`) builds fresh message dicts and fresh content *lists* but **shares the inner block dicts with `thread.turns`**, so a naive in-place mark leaks into the store, the ticket transcript, and the persisted rows. A `store.with_history_breakpoint()` helper does the copy; no stored turn is mutated.
- **Conditional insurance marker, shipped at launch.** The server looks back only **20 content blocks** for a readable entry. Measured cross-turn gaps for multi-round turns are **22 / 27 / 32 / 37** blocks (5 rounds × 2–3 parallel tools, ± a leading text block), and a wrap-up turn is a 5-round turn *by definition* — so the miss is systematic, not exotic. When the tip is more than 19 blocks past the **last still-valid entry**, a second marker is placed on the deepest message still within 19 blocks **of that entry** (anchored to the entry, never to the tip).
- **Breakpoint map 4/4:** `system` · primed instructions block · rolling tip · conditional insurance. Tools carry none.
- **Skips.** No marker on the wrap-up round (`tool_choice: {"type":"none"}` changes the messages-tier cache key, so the write could not be read back) and none under playground overrides (drafts already run uncached).
- **Folded-in fix:** `config.agent_model()` / `config.agent_thinking()` are read **per round** (`loop.py:310,317`). An env flip mid-turn therefore splits one turn across two models — caches are model-scoped, so every tier drops — and mis-records `turns.meta.model`. Both are hoisted to per-turn locals.
- **TTL:** 5-minute ephemeral on all breakpoints at launch. The 1h question is CHO-278 (rate table + measured gap distribution first).

## Open decisions

- **1h TTL for the rolling tip** — deferred to CHO-278 by design. `trace_cost.py:17-22` hardcodes the 5-minute write rate and `_usage_dict` (`loop.py:126-141`) reads only the four flat usage keys, so adopting 1h today would under-report cost by ~60% *including in this change's own prod gate*.
- **Server-side compaction and top-level automatic caching are rejected**, with reasoning recorded in `design.md` — both are strictly worse here, not merely unnecessary.

## Capabilities

### Modified Capabilities

- `agent-loop`: the live status line and first name move into a single trailing volatile message after all stored history (out of the primed turn), and every model call carries a rolling prompt-cache breakpoint on the conversation history with a conditional deep-gap insurance marker; model/thinking resolve once per turn.
- `conversation-store`: replay reconstructs the **lossless** array byte-identically to the stored turns; the model-facing array may differ only by additive, non-semantic request metadata, and the store is never mutated to produce it.

## Impact

- Backend — prompt assembly: `backend/app/agent/prompt.py` (`primed_messages()` frozen to one block; new `trailing_context_message()`; one reworded clause in `PRIMED_INSTRUCTIONS`; reworded name clause; `snapshot_text()` reordered/relabelled; stale docstring figures corrected to system 268 / tools 2,926 / prefix 6,559 / Sonnet minimum 1,024).
- Backend — store: `backend/app/agent/store.py` (`with_history_breakpoint()`, copy-on-mark; no change to `Thread`, `append_turn`, or persistence).
- Backend — loop: `backend/app/agent/loop.py` (round assembly; `_reminder_message` removed; `model`/thinking hoisted out of the round loop).
- Backend — config: `backend/app/config.py` (`agent_history_cache()`), `.env.example`.
- Tests: `backend/tests/test_agent_loop.py` (new marker/mutation/stability tests **plus five existing breaks** at :304, :341, :878, :965, :1000 — everything indexing `messages[-1]`, plus a `len(messages) == 3` assertion that becomes 4), `backend/tests/test_market_clock.py:396-446`, `backend/tests/test_clock.py:144-155`, `backend/tests/test_playground_router.py:82-95`.
- Specs: `openspec/specs/agent-loop/spec.md`, `openspec/specs/conversation-store/spec.md` (deltas in this change).
- Gates: full `uv run pytest` green; byte-stability unit test across two pinned clock instants; stored-turns-unmutated test; ≤4 breakpoints test; prompt evals (relative-date resolution, market-cutoff answering, name-overuse ≤1 per 10-turn conversation, model must not answer the clock line as the user's message); exactly one new `prompt_snapshots` row; prod canary asserting turn-2 `cache_read ≈ 6,559 + H₁`.
- Deploy: backend-only ⇒ one new `backendvX.Y.Z`; frontend tag untouched. Rollback = `AGENT_HISTORY_CACHE=0` + container recreate (Phase 0 stays live).
- Linear: CHO-264 · branch `cho-264-prompt-layout-history-caching`
