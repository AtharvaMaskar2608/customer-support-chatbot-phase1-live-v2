# CHO-224: ist-date-correctness

## Why

Two places in the backend ask for "today", and both take it from the **host's local timezone** rather than naming one:

- `app/agent/prompt.py:198` — `datetime.date.today()` fills the `Today's date is {today} ({weekday})` line at the end of the primed turn, the agent's only sense of time.
- `app/agent/forms.py:122` — the same call bounds `futureDaysCap` when the agent pre-fills a report form.

On a developer machine configured to `Asia/Kolkata` this is correct, which is why it has never been caught: `date.today()` returns the true IST date and everything behaves. **The deployed container is a different story.** `backend/Dockerfile` builds on `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, sets no `TZ`, and `docker-compose.yml` mounts no `/etc/localtime`. Running that image reports `tzname = ('UTC', 'UTC')` — verified 2026-07-20, where the host read 18:14 IST and the container read 12:44.

IST is UTC+5:30, so the UTC date rolls over at **05:30 IST**. In the container, between midnight and half past five in the morning India time, the agent and the form validator both believe it is still yesterday: relative expressions ("today", "yesterday", "this month") resolve one day early, and a 1 am request for today's contract note is bounded against the wrong date. Both are wrong together, so nothing errors — it quietly answers for the previous day.

The trap is that this is invisible in local development and only appears once containerized, in a five-and-a-half-hour window most testing never covers. Naming the zone explicitly removes the environment dependency entirely.

This is separable from the greeting work (CHO-226): correcting the date needs only a timezone, not a holiday calendar. Shipping it alone fixes a latent production bug and gives CHO-226 a clock module to extend.

## What Changes

- Add a shared `app/clock.py` exposing `ist_now()` and `ist_today()`, returning the current moment/date in **`Asia/Kolkata`** via `zoneinfo` — independent of host or container timezone, so dev and production agree by construction. CHO-226 extends this module with market-session logic rather than standing up a second clock.
- `prompt.py:primed_messages()` and `forms.py:build_form_slots()` take their default `today` from that helper.
- Both keep their existing injectable parameter so tests can pin a date — no test rewrites, and the 05:30 boundary becomes directly testable.
- Add `tzdata` to backend dependencies: the slim Debian image is not guaranteed to carry the zone database, and `zoneinfo` raises `ZoneInfoNotFoundError` without it. Verify inside the built image, not just on the host.
- The prompt line's wording and position are unchanged in this change. Restructuring the primed turn into two content blocks (frozen instructions + live time) belongs to CHO-226, which is what introduces a value that changes intra-day.

## Capabilities

### Modified Capabilities

- `agent-loop`: the "include today's date" requirement is tightened to name **IST (`Asia/Kolkata`)** as the reference zone, computed independently of the host timezone, and to require the report-form validator to resolve "today" on the same clock.

## Impact

- Backend only: new `backend/app/clock.py`, plus `backend/app/agent/prompt.py`, `backend/app/agent/forms.py`, `backend/pyproject.toml` (tzdata), and tests.
- Behaviour changes only inside the 00:00–05:30 IST window and only where the host is not already IST; the rest of the day is byte-identical, so the prompt cache is unaffected outside that boundary.
- No API contract, frontend, or database change.
- Existing tests that pass an explicit `today` are unaffected. Add boundary tests at 05:29 and 05:31 IST, and a test asserting the result does not depend on the process `TZ` (run it under `TZ=UTC` and `TZ=Asia/Kolkata`).
- Linear: CHO-224 · branch `cho-224-ist-date-correctness`.
