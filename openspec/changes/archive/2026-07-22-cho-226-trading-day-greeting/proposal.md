# CHO-226: trading-day-greeting

## Why

The home screen greets every customer with one static line — `Hey {firstName} — what do you need?` (`EmptyState.tsx:30-33`) — regardless of hour, weekday, or whether the market is open. QA asked for a trading-day-aware greeting pool: warmer in the morning, market-aware during the session, and explicitly "markets are closed — I'm not" after hours.

Delivering that needs two things this codebase does not have: an **IST clock** and an **NSE equity holiday calendar**. Building them for a greeting alone would be a waste. The agent — the half of the product that actually answers questions about settlements, charges, and cutoffs — currently knows only the date (and after CHO-224, the correct date). It cannot answer "are markets open right now", "have I missed today's payout cutoff", or "will this settle today", because nothing in its prompt describes market state.

So this change builds **one market clock on the backend** and gives it two consumers: the greeting endpoint asks it which window we are in, and the agent prompt asks it for a live status line. One calendar, one set of session rules, one place to fix a wrong holiday.

## What Changes

**Market clock (new capability).** Extend `app/clock.py` from CHO-224 into a session-aware market clock over a config-driven calendar:

- `market_state(now)` → one of `PRE_OPEN`, `OPEN`, `CLOSED`, `HOLIDAY`, plus the session's close time when open.
- `is_trading_day(date)` → **not** a weekday-minus-holidays predicate. See below.

**The calendar models trading sessions, not closures.** The tester's rule was `weekday in Mon..Fri AND date not in holidayList` — subtraction only. That rule cannot express **Sunday, 8 November 2026**, which is a *trading day*: Diwali Laxmi Pujan Muhurat trading. No holiday-list tuning makes a subtraction rule return true for a Sunday. The calendar therefore carries session entries with their own windows, and the predicate becomes `date in specialSessions OR (weekday AND NOT holiday)`. Muhurat also runs in the evening with timings published only days beforehand, so a date's windows must be data, not code — otherwise the 8 November greeting says "markets are closed" during the most symbolically loaded session of the Indian trading year.

**Coverage-year guard.** The seeded calendar is 2026 only (16 weekday closures; verified every date against its stated weekday — all 20 published entries, including the four falling on weekends, check out). An expired calendar's failure mode is worse than a missing one: "no holidays found" reads as "every weekday is a trading day", so on Republic Day 2027 a stale list would cheerfully report an open market. The calendar declares its coverage window and any date outside it routes to **degraded weekday-only mode** explicitly, rather than silently returning "not a holiday".

**Greeting selection returns a key and a template, not a rendered string.** `GET /api/greeting` gains `greetingKey` and `template` alongside the existing `firstName`. The frontend interpolates, so the accent-coloured name span in `EmptyState.tsx` survives and copy stays editable server-side. Windows are half-open and walked in order: 06:00–09:00 `MORNING` (any day), 09:15–15:30 `MARKET` and 15:30–23:00 `POST_MARKET` (trading days only), everything else `DEFAULT`. A fifth `MUHURAT` key covers special evening sessions.

**`{clientRef}` is the first name.** The tester's spec says Client ID in Phase 1 and first name in Phase 2, but `greeting.py:25-36` already derives first names and ships them. Implementing the spec literally would regress "Hey Pritam" to "Hey X008593". First name throughout; the existing "there" fallback is retained.

**Agent prompt gains a live status line — at the very bottom.** The primed user turn splits into two content blocks: the frozen instructions and few-shot examples first, carrying the cache breakpoint, and the live line last:

```
Right now it is 2:47 pm IST on Monday, 20 July 2026. Markets are open; the equity session closes at 3:30 pm.
```

Everything above the breakpoint caches; the live line sits after it and costs nothing to change per request. This replaces the current `Today's date is …` line.

## Capabilities

### New Capabilities

- `market-clock`: the IST clock and NSE equity trading-session calendar — session-based (not closure-based) so special sessions like Muhurat are expressible, coverage-guarded so an expired calendar degrades loudly, and shared by every consumer that needs to know the date, the time, or whether the market is open.

### Modified Capabilities

- `profile-greeting`: the endpoint returns a greeting key and template selected from the market clock, in addition to the first name; failure degrades to the current static greeting rather than blocking the screen.
- `agent-loop`: the date line becomes a live IST status line carrying time and market state, pinned to the last content block of the primed turn so the frozen prefix stays cacheable.

## Impact

- Backend: `app/clock.py` (extended), new `content/market_calendar.json`, `app/greeting.py`, `app/agent/prompt.py`, tests.
- Frontend: `src/useGreeting.ts` (parse two more fields), `src/chat/EmptyState.tsx` (render the template with the accent span preserved).
- Depends on CHO-224 for the IST clock module; do not start until that merges.
- The calendar is server-side config, which matters because Muhurat timings are published late — but note the same redeploy limitation flagged in CHO-225 applies until `content/` is externalised.
- Prompt-cache note: the split introduces a second `cache_control` breakpoint (the API allows four; we currently use one). Worth measuring whether the existing tools+system prefix even clears the minimum cacheable prefix — the agent defaults to `claude-haiku-4-5`, whose minimum is 4096 tokens, double Sonnet 4.6's.
- Linear: CHO-226 · branch `cho-226-trading-day-greeting`.
