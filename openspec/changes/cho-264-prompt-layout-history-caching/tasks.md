# CHO-264: prompt-layout-history-caching — tasks

## 1. Phase 0 — relocate the live context (unconditional)

- [x] 1.1 `prompt.py`: `primed_messages()` → frozen two-message preamble — ONE instructions block carrying the cache breakpoint, then `"Understood."`. Drop the `now` / `first_name` parameters from the primed path.
- [x] 1.2 `prompt.py`: new `trailing_context_message(now=None, first_name=None, *, reminders=())` → the single last user message: one `<system-reminder>`-wrapped live-context block (status line + first name) followed by any reminder blocks.
- [x] 1.3 `prompt.py:223`: reword the one clause in `PRIMED_INSTRUCTIONS` that says the IST date and time is "given at the end of this message" so it refers to the live-context note at the end of the conversation. Check the adjacent sentence about market open / session close still reads correctly.
- [x] 1.4 `prompt.py:340-348`: reword the name-usage clause to a self-check against the visible conversation ("if you have already used their name earlier in this conversation, do not use it again"), keeping "do not start routine replies with their name" and "never open consecutive messages with their name".
- [x] 1.5 `prompt.py:393-405`: reorder/relabel `snapshot_text()` to match the new layout (`--- trailing live-context note ---`), keeping `clock.STATUS_LINE_TEMPLATE` placeholders so the hash stays time-stable.
- [x] 1.6 `loop.py:296-308`: assemble `primed_messages(...) + thread.messages() + [trailing_context_message(...)]`; delete `_reminder_message` (`loop.py:95-99`) — reminders now ride the trailing message.
- [x] 1.7 `prompt.py:22-40`: correct the stale docstring figures — system **268** (not 229), tools **2,926** (not 2,716), cacheable prefix **6,559** (not 5,344), Sonnet 4.6 minimum cacheable prefix **1,024** (not 2,048); record *why* the tail moved past the history.

## 2. Phase 1 — rolling history breakpoint

- [x] 2.1 `store.py`: `CACHE_CONTROL_EPHEMERAL` + `with_history_breakpoint(messages)` — **copy-on-mark** the last content block of the last message (`content[-1] = {**block, "cache_control": …}`); no-op on empty history, non-list content, or a block that already carries `cache_control`. Docstring states why in-place mutation is forbidden (`store.py:182,188,190` share block dicts with `thread.turns`).
- [x] 2.2 `store.py`: conditional insurance marker — when the tip is more than 19 content blocks past the **last valid entry**, also mark the deepest message within 19 blocks **of that entry** (anchored to the entry, never to the tip). Last valid entry = the previous round's tip (round ≥2) or the previous turn's round-1 tip (round 1); derive it from the message index of the last turn that existed before `loop.py:274` appended the new user turn — no new persistent state.
- [x] 2.3 `loop.py`: apply the marker to `thread.messages()` **before** the primed prefix and trailing message are concatenated, so it structurally cannot touch either.
- [x] 2.4 `loop.py`: skip the marker when `force_wrapup` (the `tool_choice: {"type":"none"}` round), when either playground override is set, and when the flag is off.
- [x] 2.5 TTL: plain `{"type": "ephemeral"}` (5 minutes) on all breakpoints — no `"ttl"` key anywhere in this change.

## 3. Config and folded-in fixes

- [x] 3.1 `config.py`: `agent_history_cache()` — `AGENT_HISTORY_CACHE`, default on, falsy set `{0,false,no,off}`; docstring states it gates only the marker, never the Phase 0 layout.
- [x] 3.2 `.env.example`: document `AGENT_HISTORY_CACHE` (default 1, set 0 for a no-rebuild rollback).
- [x] 3.3 `loop.py:310,317`: hoist `config.agent_model()` and the thinking params out of the `while` loop into per-turn locals, so an env flip mid-turn cannot split one turn across two models (cache-destroying) or corrupt `turns.meta.model`.

## 4. New tests

- [x] 4.1 `test_history_breakpoint_marks_last_stored_block` — `calls[i]["messages"][-2]["content"][-1]["cache_control"] == {"type": "ephemeral"}` (`[-1]` is the trailing volatile message).
- [x] 4.2 `test_history_breakpoint_does_not_mutate_stored_turns` — after the request, `"cache_control" not in json.dumps([t.content for t in thread.turns])`, and a `thread.messages()` snapshot taken before the request is byte-identical to the same prefix afterwards.
- [x] 4.3 `test_trailing_message_carries_no_breakpoint` — no `cache_control` anywhere in `messages[-1]`.
- [x] 4.4 `test_only_the_trailing_message_is_volatile` — pin `clock._utc_now` at two instants 5 minutes apart with identical stored turns; `json.dumps(messages[:-1])` byte-identical, `messages[-1]` differs. (This is the cache-stability invariant as a unit test.)
- [x] 4.5 `test_at_most_four_cache_breakpoints` — count `cache_control` across `system` + `tools` + `messages`; normal round = 3, deep-gap round = 4, never more; `tools` carry none.
- [x] 4.6 `test_wrapup_round_drops_history_breakpoint` — extend `test_tool_round_guard_forces_wrapup_call` (`tests/test_agent_loop.py:475`): the wrap-up call has zero `cache_control` in `messages`, the round before it has one.
- [x] 4.7 `test_marker_rolls_once_per_round` — multi-round turn: every call has exactly one marker and it is always on the last stored message.
- [x] 4.8 `test_insurance_marker_bridges_a_deep_gap` — a 5-round × 3-parallel turn followed by a new user turn: two markers, the second anchored within 19 blocks of the previous turn's entry; and a 1-round turn produces only one marker.
- [x] 4.9 `test_history_cache_flag_off_matches_legacy_layout` — `AGENT_HISTORY_CACHE=0` ⇒ exactly 2 markers, and the array is otherwise identical to the flag-on array.
- [x] 4.10 `test_playground_overrides_drop_history_breakpoint` — in `tests/test_playground_router.py`, beside the existing override assertions.
- [x] 4.11 `test_trailing_context_is_framed_as_app_generated` — the trailing block is `<system-reminder>`-wrapped and `"<system-reminder>" not in json.dumps(thread.messages())` still holds.
- [x] 4.12 `test_model_and_thinking_resolved_once_per_turn` — flip `AGENT_MODEL` between rounds via monkeypatch; every call of the turn carries the same model, and `turns.meta.model` matches it.
- [x] 4.13 `test_flow_event_memo_between_tool_results_keeps_results_first` — a `flow_event` appended between two `tool_result` appends of one round still yields results-first ordering and leaves the marked block's prefix unchanged (pins the `store.py:186-188` reorder that the marker rule depends on).

## 5. Existing tests to update

- [x] 5.1 `tests/test_agent_loop.py:189-207` — primed turn is now ONE block; the status line moves to `messages[-1]`; `messages[1]` / `messages[2]` indices shift.
- [x] 5.2 `tests/test_agent_loop.py:405-408` — `messages[-1]["content"]` now holds `[live-context, reminder]`, so the reminder is `content[1]`.
- [x] 5.3 `tests/test_agent_loop.py:303-306` — parallel `tool_result` assertion indexes `messages[-1]`; retarget at `messages[-2]`.
- [x] 5.4 `tests/test_agent_loop.py:340-344` — error-bounce assertion indexes `messages[-1]`; retarget.
- [x] 5.5 `tests/test_agent_loop.py:878-881` — `test_short_circuited_turn_continues_cleanly` indexes `messages[-1]`; retarget.
- [x] 5.6 `tests/test_agent_loop.py:963-967` — ticket-bounce assertion indexes `messages[-1]`; retarget.
- [x] 5.7 `tests/test_agent_loop.py:998-1002` — `len(messages) == 3` after reset becomes 4 (the trailing message); the `messages[2]` identity assertion shifts.
- [x] 5.8 `tests/test_market_clock.py:396-446` — six assertions on the two-block primed turn; retarget at `trailing_context_message`. Keep the intent of `test_no_volatile_value_appears_before_the_breakpoint` (strengthened by 4.4) and of `test_first_name_rides_the_volatile_block_not_the_cached_prefix`.
- [x] 5.9 `tests/test_clock.py:144-155` — same retarget (IST-under-UTC and injected-`now` assertions read `primed_messages()[0]["content"][1]`).
- [x] 5.10 `tests/test_playground_router.py:82-95` — primed-override shape is now a single block.

## 6. Verification gates

- [x] 6.1 Full `uv run pytest` green (existing suite + section 4, including all five breaks in section 5).
- [ ] 6.2 Prompt evals with the reworded copy: relative-date resolution ("last month" → correct `YYYY-MM-DD` from the trailing note), market-cutoff answering ("can I still act today?"), and the model must **not** answer the clock line as if it were the user's latest message.
- [ ] 6.3 Name-overuse eval: 10-turn transcript with a first name available ⇒ the first name appears in at most ONE assistant reply (CHO-274 regression guard).
- [ ] 6.4 Confirm exactly **one** new `prompt_snapshots` row after deploy (one reworded prompt ⇒ one new `prompt_hash`); old threads keep the old hash.

## 7. Deploy and prod canary

- [ ] 7.1 Backend-only image: build + bump `backendvX.Y.Z` in `docker-compose.yml`; frontend tag untouched (per `docs/deployment.md`).
- [ ] 7.2 Canary (user-gated — needs a fresh SSO JWT): two chat turns ~10 s apart on prod, then read the two `llm` spans and assert turn-2 `cache_read ≈ 6,559 + H₁`.
- [ ] 7.3 Prod gates on threads with ≥5 user turns: median `cache_read/total_prompt` on 2nd+ `llm` spans ≥ 0.70; median per-turn `cost_inr` at turn ≥8 down ≥50%; `cache_creation ≤ 1.3×` the round's own delta on ≥90% of spans; **zero** spans with `cache_creation > 10,000` while `total_prompt > 15,000`; `cache_read ≥ 6,000` on the first span of every fresh thread. Do not measure across a flag flip.
- [ ] 7.4 Rollback path rehearsed and documented: `AGENT_HISTORY_CACHE=0` + `docker rm -f jini-backend` / `docker run … -e …` (user-gated SSH); Phase 0 stays live and independently verifiable.

## 8. Ship & sync

- [ ] 8.1 `git-sync` with issue key CHO-264
- [ ] 8.2 `linear-connector` — In Progress at implementation, summary + In Review at PR, Done at merge
