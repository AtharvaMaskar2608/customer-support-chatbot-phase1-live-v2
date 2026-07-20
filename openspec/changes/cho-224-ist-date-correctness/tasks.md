# CHO-224: ist-date-correctness — tasks

## 1. Shared clock module

- [x] 1.1 Add `backend/app/clock.py` with `IST = ZoneInfo("Asia/Kolkata")`, `ist_now() -> datetime` (tz-aware) and `ist_today() -> date`
- [x] 1.2 Add `tzdata` to `backend/pyproject.toml` dependencies and `uv lock` (tzdata 2026.3)
- [x] 1.3 Confirm `zoneinfo.ZoneInfo("Asia/Kolkata")` resolves **inside the built image**, not only on the host: `docker build` then `docker run --rm <img> python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Asia/Kolkata'))"`
  - Verified: container reports `tzname = ('UTC', 'UTC')`, zone resolves, and `ist_now()` read 18:34 IST against 13:04 UTC. Both the pip `tzdata` and `/usr/share/zoneinfo` are present in the current base image; the explicit dependency is what keeps it true if the base is slimmed.

## 2. Wire the two call sites

- [x] 2.1 `backend/app/agent/prompt.py:primed_messages()` — default `today` comes from `ist_today()`; keep the injectable parameter
- [x] 2.2 `backend/app/agent/forms.py:validate_seed()` — same change; keep the injectable parameter (the seed validator is the real name; `build_form_slots()` does not exist)
- [x] 2.3 Grep for any other `date.today()` / `datetime.now()` without a timezone in `backend/app/`
  - `app/agent/store.py:_now()` and `app/agent/tickets.py:120` already use `datetime.now(timezone.utc)`; storage/audit timestamps stay UTC deliberately — comment added in `store.py`.
  - [ ] **Outstanding:** `app/data/money.py:79` calls `_fy_window(datetime.date.today())` for the pay-in/pay-out FY window (April 1 → today+7). Same host-timezone bug, narrower blast radius: the `to_date` is a day early inside the 00:00–05:30 IST window, and on 1 April in that window `from_date` anchors to the previous FY. One-line fix (`ist_today()`), left out of this change because the file was outside the agreed edit scope.

## 3. Tests

All in `backend/tests/test_clock.py` (15 tests). Time is pinned by monkeypatching `app.clock._utc_now`, the module's single wall-clock seam — no freezegun dependency needed.

- [x] 3.1 `ist_today()` returns the IST date when the process runs under `TZ=UTC` — the regression this change exists to prevent (`test_ist_today_ignores_process_tz_utc`, plus `test_ist_today_same_under_utc_and_kolkata` and `test_ist_today_diverges_from_host_today_inside_the_window`)
- [x] 3.2 Boundary: freeze at 2026-07-21 05:29 IST (23:59 UTC on the 20th) → expect 2026-07-21, not 2026-07-20
- [x] 3.3 Boundary: freeze at 2026-07-21 05:31 IST → expect 2026-07-21 (both sides of the UTC rollover agree once the zone is named)
- [x] 3.4 Form validator: a `futureDaysCap: 0` flow accepts today's IST date at 01:00 IST (previously rejected as "future") — asserted through both `validate_seed()` and the live `run_open_report_form()` entry point, with a companion test pinning `today` to the UTC date to prove the old behaviour is what is being fixed
- [x] 3.5 Existing prompt/form tests still pass unchanged

## 4. Verification

- [x] 4.1 `cd backend && uv run pytest` — 359 passed, 2 skipped (both skips pre-existing)
- [x] 4.2 Confirm the rendered prompt line is byte-identical to today's output outside the 00:00–05:30 window (no cache churn) — `test_prompt_wording_and_position_unchanged` asserts the render equals `PRIMED_INSTRUCTIONS.format(...)` verbatim and that `snapshot_text()` still carries the placeholders, so the snapshot hash stays date-stable

## 5. Ship & sync

- [ ] 5.1 `git-sync` with issue key CHO-224
- [ ] 5.2 `linear-connector` — summary comment + state to Done on merge
