# CHO-226: trading-day-greeting — design

## D1. Where greeting selection lives

Three options were considered. The constraint that decides it is `EmptyState.tsx:30-33`, which renders the customer's name in accent colour inside the headline — a rendered string would flatten that, violating "keep the UI as-is".

| Option | Response | Keeps accent name | Copy editable without a frontend release |
|---|---|---|---|
| Backend renders the full string | `{greeting}` | No | Yes |
| Backend picks the key, frontend holds templates | `{firstName, greetingKey}` | Yes | No |
| **Backend picks the key and sends the template** | `{firstName, greetingKey, template}` | **Yes** | **Yes** |

**Decision: option 3.** The frontend splits the template on `{clientRef}` and wraps the name in its existing span. The backend owns the clock, the calendar, and the copy; the frontend owns presentation only. Same philosophy as `whats-new`, where copy already lives server-side.

## D2. The calendar is a session calendar, not a holiday list

The supplied rule was subtraction-only:

```
isTradingDay(d) = d.weekday in Mon..Fri AND d not in holidays
```

That cannot express **Sunday 8 November 2026**, a trading day (Diwali Laxmi Pujan Muhurat). Additions need their own channel:

```
isTradingDay(d) =  d in specialSessions
                OR (d.weekday in Mon..Fri AND d not in holidays)
```

And a second layer: Muhurat runs in the *evening*, so even with `isTradingDay` true, a 6:45 pm timestamp misses the 09:15–15:30 `MARKET` window and lands in `POST_MARKET` — whose copy is "Markets are closed — I'm not". Wrong, on the single most symbolically loaded trading day of the Indian year.

**Decision: dates carry their own windows.**

```
DATE
 ├─ special session?  ── yes ─▶ use its declared windows  → MUHURAT
 ├─ weekday + holiday? ─ yes ─▶ no session                → DEFAULT all day
 └─ ordinary weekday   ──────▶ 09:15–15:30 → MARKET
                                15:30–23:00 → POST_MARKET
```

Muhurat timings are published only days in advance, so the window must be editable config, not a code constant. Cost of building it this way now is one extra field; cost of retrofitting is the schema plus every consumer.

## D3. Coverage-year guard

The seeded calendar covers 2026 only. The dangerous failure is not absence but **expiry**: a 2026 calendar asked about 26 January 2027 returns "not a holiday", and the system confidently reports an open market on Republic Day.

**Decision:** the calendar declares `coverageFrom` / `coverageTo`. A date outside that window routes to degraded weekday-only mode and logs a warning. An absent calendar fails loudly; an expired one must too.

## D4. Data source

The published NSE list bundles equity and commodity tables on one page, and they differ. **1 January 2026 is absent from the equity list** — it appears only under Commodity Derivatives (morning open, evening closed). Equity trades normally on New Year's Day. A naive scrape of "every date on that page" would import Jan 1 as an equity closure and inherit commodity's split-session semantics, which the spec explicitly excludes.

**Decision: curated, human-reviewed JSON — not a scraper.** Sixteen entries a year is not worth automating badly. All twenty published entries are stored (including the four falling on weekends, which are no-ops for a weekday rule) with a flag, so a reviewer diffing our config against the NSE page sees the same twenty rows.

Verified 2026 equity data — all twenty entries checked against their real weekday, zero mismatches:

| Weekday closures (16) | |
|---|---|
| 15 Jan (Thu) Municipal Corp. Election · 26 Jan (Mon) Republic Day · 03 Mar (Tue) Holi · 26 Mar (Thu) Ram Navami · 31 Mar (Tue) Mahavir Jayanti · 03 Apr (Fri) Good Friday · 14 Apr (Tue) Ambedkar Jayanti · 01 May (Fri) Maharashtra Day · 28 May (Thu) Bakri Id · 26 Jun (Fri) Muharram · 14 Sep (Mon) Ganesh Chaturthi · 02 Oct (Fri) Gandhi Jayanti · 20 Oct (Tue) Dussehra · 10 Nov (Tue) Diwali-Balipratipada · 24 Nov (Tue) Guru Nanak Jayanti · 25 Dec (Fri) Christmas | |
| Weekend-falling (4, no-ops) | 15 Feb (Sun) · 21 Mar (Sat) · 15 Aug (Sat) · 08 Nov (Sun) |
| Special session | 08 Nov (Sun) Muhurat — evening window, timings TBA |

2026 has 261 weekdays; 16 closures leave 245 trading days. The calendar changes the answer on ~6% of weekdays — acceptable as a temporary fallback, not as a steady state.

## D5. `{clientRef}` is the first name

The supplied spec says Client ID for Phase 1, first name for Phase 2. But `greeting.py:25-36` already derives `"PRITAM NITIN WAVHAL" → "Pritam"` and the frontend already renders it. Implementing the spec literally regresses to "Hey X008593".

**Decision:** first name throughout, `there` as the existing fallback. Treat the spec's Phase 1 as already superseded.

## D6. Restart recomputes

The spec fires the greeting on "first open or reopen after session expiry". The Restart button is neither, but it remounts the shell and clears the conversation, so from the customer's side it *is* a fresh entry screen.

**Decision:** recompute on restart. Cheap, and a stale greeting on a visibly-reset screen would look like a bug.

## D7. Window gaps stay DEFAULT

09:00–09:15 (NSE pre-open) and 23:00–06:00 (overnight) match no window and fall to `DEFAULT`. Both are intentional. Pre-open is a natural fifth key later; overnight is a plausible sixth. Not in this change.

## D8. Live status line goes last in the prompt

The primed user turn becomes two content blocks:

```
content[0]  frozen instructions + few-shot examples   ← cache_control breakpoint
content[1]  "Right now it is 2:47 pm IST on Monday, 20 July 2026.
             Markets are open; the equity session closes at 3:30 pm."
```

`cache_control` attaches to a content block, and a user message may hold several, so the volatile line sits strictly after the breakpoint. Prefix caching is a prefix match — everything up to the breakpoint is reusable, and a value after it can change every request at no cost.

**Decision: minute-level time is fine, provided it is the last block.** Time-of-day earns its place: cutoff questions ("can I still withdraw today?", "am I too late to pledge for tomorrow's margin?") are wall-clock questions that an open/closed boolean cannot answer. Market state alone would be cheaper but strictly less useful, and the split makes the cheapness moot.

Two implementation notes. The agent defaults to `claude-haiku-4-5`, whose minimum cacheable prefix is **4096 tokens** (Sonnet 4.6's is 2048) — measure with `count_tokens` whether tools + system clears it today, because if not, the existing single breakpoint is caching nothing and folding the instructions in would switch caching on for the first time. Separately, a cache breakpoint searches back at most **20 content blocks** for a prior entry; a tool-heavy turn can exceed that, so verify hit rates on a multi-round conversation rather than a single exchange.
