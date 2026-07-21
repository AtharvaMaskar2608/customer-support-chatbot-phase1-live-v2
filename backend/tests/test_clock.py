"""IST clock correctness (CHO-224).

The bug this file exists to prevent: `datetime.date.today()` reads the
PROCESS timezone. On a dev machine set to Asia/Kolkata it is right; in the
deployed container (no TZ, no /etc/localtime → UTC) it is a day behind
between 00:00 and 05:30 IST, because the UTC date rolls over at 05:30 IST.
Both the prompt's date line and the report-form validator were affected, and
they were wrong *together*, so nothing ever errored — it quietly answered
for the previous day.

Time is pinned by monkeypatching `app.clock._utc_now`, the module's single
wall-clock seam. Instants are written UTC-side and asserted IST-side so the
5:30 offset is visible in the test itself.
"""

import datetime
import os
import time
from zoneinfo import ZoneInfo

import pytest

from app import clock
from app.agent.forms import OpenReportFormParams, run_open_report_form, validate_seed
from app.agent.prompt import PRIMED_INSTRUCTIONS, primed_messages, snapshot_text

UTC = datetime.timezone.utc

# The two sides of one UTC rollover, expressed in UTC.
#   2026-07-20 23:59 UTC == 2026-07-21 05:29 IST  (UTC still says the 20th)
#   2026-07-21 00:01 UTC == 2026-07-21 05:31 IST  (UTC has caught up)
JUST_BEFORE_UTC_ROLLOVER = datetime.datetime(2026, 7, 20, 23, 59, tzinfo=UTC)
JUST_AFTER_UTC_ROLLOVER = datetime.datetime(2026, 7, 21, 0, 1, tzinfo=UTC)
# 01:00 IST on 2026-07-21 — deep inside the broken window.
ONE_AM_IST = datetime.datetime(2026, 7, 20, 19, 30, tzinfo=UTC)


@pytest.fixture
def at_utc(monkeypatch):
    """Pin the clock to a given UTC instant."""

    def _pin(instant: datetime.datetime):
        monkeypatch.setattr(clock, "_utc_now", lambda: instant)
        return instant

    return _pin


@pytest.fixture
def process_tz(monkeypatch):
    """Run the process under a named TZ, restoring the real one afterwards."""
    original = os.environ.get("TZ")

    def _set(name: str):
        monkeypatch.setenv("TZ", name)
        time.tzset()

    yield _set

    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


# --- the zone itself ---------------------------------------------------------


def test_zone_database_is_available():
    """Guards the tzdata dependency: without it this raises
    ZoneInfoNotFoundError, which is exactly the container failure mode."""
    assert clock.IST is ZoneInfo("Asia/Kolkata")
    assert clock.IST.utcoffset(datetime.datetime(2026, 7, 21)) == datetime.timedelta(
        hours=5, minutes=30
    )


def test_ist_now_is_tz_aware_and_offset_by_five_thirty(at_utc):
    instant = at_utc(ONE_AM_IST)
    now = clock.ist_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == datetime.timedelta(hours=5, minutes=30)
    assert now == instant  # same moment, different wall clock
    assert (now.hour, now.minute) == (1, 0)


# --- the regression: independence from the process timezone ------------------


def test_ist_today_ignores_process_tz_utc(process_tz):
    """The regression this change exists to prevent: under TZ=UTC (the
    deployed container) the IST date is still the IST date."""
    process_tz("UTC")
    # Confirm the process really is on UTC, or the assertion below is vacuous.
    assert datetime.datetime.now().astimezone().utcoffset() == datetime.timedelta(0)
    assert clock.ist_today() == datetime.datetime.now(clock.IST).date()


def test_ist_today_same_under_utc_and_kolkata(process_tz):
    process_tz("UTC")
    under_utc = clock.ist_today()
    process_tz("Asia/Kolkata")
    under_ist = clock.ist_today()
    assert under_utc == under_ist


def test_ist_today_diverges_from_host_today_inside_the_window(at_utc, process_tz):
    """The concrete failure: at 01:00 IST a UTC host says 'the 20th' while
    India says 'the 21st'."""
    at_utc(ONE_AM_IST)
    process_tz("UTC")
    host_view = ONE_AM_IST.astimezone(datetime.datetime.now().astimezone().tzinfo)
    assert host_view.date() == datetime.date(2026, 7, 20)
    assert clock.ist_today() == datetime.date(2026, 7, 21)


# --- the 05:30 boundary ------------------------------------------------------


def test_boundary_0529_ist_is_already_the_new_day(at_utc):
    """23:59 UTC on the 20th is 05:29 IST on the 21st — the pre-fix code
    reported the 20th here."""
    at_utc(JUST_BEFORE_UTC_ROLLOVER)
    assert (clock.ist_now().hour, clock.ist_now().minute) == (5, 29)
    assert clock.ist_today() == datetime.date(2026, 7, 21)


def test_boundary_0531_ist_agrees(at_utc):
    """Once UTC catches up both zones name the same date — naming the zone
    makes the two sides of the rollover agree."""
    at_utc(JUST_AFTER_UTC_ROLLOVER)
    assert (clock.ist_now().hour, clock.ist_now().minute) == (5, 31)
    assert clock.ist_today() == datetime.date(2026, 7, 21)


# --- call site: the prompt ---------------------------------------------------


def test_prompt_status_line_uses_ist(at_utc, process_tz):
    """01:00 IST on the 21st, under a UTC host that still says the 20th."""
    at_utc(ONE_AM_IST)
    process_tz("UTC")
    blocks = primed_messages()[0]["content"]
    assert blocks[1]["text"].startswith(
        "Right now it is 1:00 am IST on Tuesday, 21 July 2026."
    )
    assert "20 July" not in blocks[1]["text"]


def test_prompt_injected_now_still_wins(at_utc):
    """The injectable parameter is untouched — tests keep pinning the clock."""
    at_utc(ONE_AM_IST)
    pinned = datetime.datetime(2026, 1, 2, 11, 0, tzinfo=clock.IST)
    blocks = primed_messages(now=pinned)[0]["content"]
    assert blocks[1]["text"].startswith(
        "Right now it is 11:00 am IST on Friday, 2 January 2026."
    )


# --- call site: the form validator ------------------------------------------


def test_zero_future_cap_accepts_todays_ist_date_at_1am(at_utc, process_tz):
    """Contract notes cap the future at 0 days. At 01:00 IST a UTC-dated
    validator called 2026-07-21 'the future' and silently dropped the pair,
    so a 1 am request for today's contract note came back with an empty
    date slot."""
    at_utc(ONE_AM_IST)
    process_tz("UTC")
    seed, dropped = validate_seed(
        OpenReportFormParams(
            flow="contract-notes", fromDate="2026-07-21", toDate="2026-07-21"
        )
    )
    assert seed == {"fromDate": "2026-07-21", "toDate": "2026-07-21"}
    assert dropped == []


def test_zero_future_cap_still_rejects_tomorrow(at_utc):
    at_utc(ONE_AM_IST)
    seed, dropped = validate_seed(
        OpenReportFormParams(
            flow="contract-notes", fromDate="2026-07-22", toDate="2026-07-22"
        )
    )
    assert seed == {}
    assert dropped == ["fromDate", "toDate"]


def test_pre_fix_behaviour_is_what_the_old_clock_produced(at_utc):
    """Pinning today to the UTC date reproduces the bug — proof the test
    above is actually exercising the fix and not a tautology."""
    seed, _ = validate_seed(
        OpenReportFormParams(
            flow="contract-notes", fromDate="2026-07-21", toDate="2026-07-21"
        ),
        today=datetime.date(2026, 7, 20),
    )
    assert seed == {}


def test_tool_entry_point_uses_the_ist_clock(at_utc, process_tz):
    """`run_open_report_form` takes the default `today`, so the live path
    (not just the helper) is on the IST clock."""
    import asyncio

    at_utc(ONE_AM_IST)
    process_tz("UTC")
    result = asyncio.run(
        run_open_report_form(
            {
                "flow": "contract-notes",
                "fromDate": "2026-07-21",
                "toDate": "2026-07-21",
            },
            None,
        )
    )
    assert result["seed"] == {"fromDate": "2026-07-21", "toDate": "2026-07-21"}
    assert result["dropped"] == []


def test_fy_window_follows_the_ist_clock(at_utc, process_tz):
    """The tax flow's selectable FYs also key off `today`; on 1 April at
    01:00 IST the new FY must already be offered."""
    at_utc(datetime.datetime(2026, 3, 31, 19, 30, tzinfo=UTC))  # 2026-04-01 01:00 IST
    process_tz("UTC")
    seed, _ = validate_seed(OpenReportFormParams(flow="tax", fy="2026-2027"))
    assert seed == {"fy": "2026-2027"}
