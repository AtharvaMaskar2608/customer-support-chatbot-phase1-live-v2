# CHO-226: trading-day-greeting — tasks

> Depends on **CHO-224** for `app/clock.py`. Do not start until that merges.

## 1. Calendar data

- [x] 1.1 Add `backend/content/market_calendar.json`: `coverageFrom`/`coverageTo` (2026-01-01 → 2026-12-31), `holidays[]` (all 20 published 2026 entries, each with `date`, `description`, `fallsOnWeekend` flag), `specialSessions[]` (8 Nov Muhurat, windows TBA)
- [x] 1.2 Default session windows in config, not code: `market` 09:15–15:30, `postMarket` 15:30–23:00, `morning` 06:00–09:00
- [x] 1.3 Cross-check every stored date against its published weekday before committing (all 20 verified at proposal time — re-verify after any edit)

## 2. Market clock

- [x] 2.1 Extend `app/clock.py`: `load_calendar()` with a cached read, `is_trading_day(d)` implementing `special OR (weekday AND NOT holiday)`, `market_state(now)` returning state + session close time
- [x] 2.2 Half-open window matching `[start, end)` walked in order, so 15:30:00 is unambiguously `POST_MARKET` and 09:15:00 is unambiguously `MARKET`
- [x] 2.3 Coverage guard: a date outside `coverageFrom`/`coverageTo` returns weekday-only degraded mode **and** logs a warning; never silently "no holidays"
- [x] 2.4 Calendar unreadable or malformed → same degraded mode, warning logged, never an exception to the caller

## 3. Greeting endpoint

- [x] 3.1 `GET /api/greeting` returns `{firstName, greetingKey, template}`; keep `firstName` semantics and the PII rules in `greeting.py` untouched
- [x] 3.2 Templates in config keyed by `DEFAULT` / `MORNING` / `MARKET` / `POST_MARKET` / `MUHURAT`, each containing the `{clientRef}` placeholder, plus a `fallbackTemplates` set with no placeholder
- [x] 3.3 `firstName` null/empty → serve the fallback template; verify no double space and no stray punctuation
- [x] 3.4 Any clock or calendar failure → `DEFAULT`; the endpoint must never 5xx on greeting selection alone
- [x] 3.5 Log `{greeting_key, ts}` on the session record — key only, never the name

## 4. Frontend

- [x] 4.1 `useGreeting.ts`: parse `greetingKey` and `template`; any missing field degrades to today's static greeting
- [x] 4.2 `EmptyState.tsx`: split the template on `{clientRef}` and render the name inside the existing accent span — the headline's visual output must be unchanged for the `DEFAULT` key
- [x] 4.3 Greeting is presentation-only: never a chat message, never in history, never routed as intent
- [x] 4.4 Static once painted — no live swap when a window boundary passes mid-view
- [x] 4.5 Restart recomputes (design D6)

## 5. Agent prompt

- [x] 5.1 Split `primed_messages()` into two content blocks: frozen instructions (carrying `cache_control`) then the live status line last
- [x] 5.2 Live line renders IST time, weekday, date, market state, and session close when open
- [x] 5.3 `snapshot_text()` keeps recording placeholders so the prompt hash stays stable across time
- [x] 5.4 Measure with `count_tokens` whether tools + system clears Haiku 4.5's 4096-token minimum cacheable prefix; record the number in the PR — **it does not**: tools 2,716 + system 229 = **2,946 tokens**, below the 4,096 minimum, so the pre-existing single breakpoint was caching nothing on Haiku. Adding block 0 behind the second breakpoint reaches **4,711 tokens**, which clears it. Numbers recorded in `app/agent/prompt.py`'s module docstring.
- [ ] 5.5 Verify `usage.cache_read_input_tokens` is non-zero across repeated requests on a multi-round tool conversation (watch the 20-block lookback)

## 6. Tests

- [x] 6.1 Every window boundary: 05:59, 06:00, 08:59, 09:00, 09:14, 09:15, 15:29, 15:30, 22:59, 23:00
- [x] 6.2 Trading day vs holiday vs weekend for a sampled set of the 16 closures
- [x] 6.3 Sunday 8 Nov 2026 during the Muhurat window → `MUHURAT`, not `DEFAULT` and not `POST_MARKET`
- [x] 6.4 1 Jan 2026 is a normal equity trading day (guards against importing the commodity table)
- [x] 6.5 A date in 2027 → degraded weekday-only mode with a logged warning, not "no holidays"
- [x] 6.6 Corrupt/missing calendar → `DEFAULT`, endpoint still 200
- [x] 6.7 Frontend: `DEFAULT` key renders a headline byte-identical to the current static greeting — asserted in `tests/test_market_clock.py` against a Python mirror of EmptyState's `{clientRef}` split, because the frontend has no test runner (no vitest in `package.json`); `npx tsc --noEmit` is the only frontend gate

## 7. Ship & sync

- [ ] 7.1 `git-sync` with issue key CHO-226
- [ ] 7.2 `linear-connector` — summary comment + state to Done on merge
