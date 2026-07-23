"""Market clock, greeting selection, and the live prompt status line (CHO-226).

Three classes of bug this file exists to prevent:

1. **Subtraction-only trading days.** `weekday AND NOT holiday` cannot express
   Sunday 8 November 2026 — Diwali Laxmi Pujan Muhurat trading, a trading day
   that is both a Sunday and an entry in `holidays[]`. Additions must win.
2. **Ambiguous boundaries.** Half-closed or reordered windows put 15:30:00 in
   two windows (or none). Every boundary in tasks.md §6.1 is asserted here.
3. **Silent expiry.** A 2026 calendar asked about 2027 must NOT answer "not a
   holiday" — that asserts an open market on Republic Day. It degrades to
   weekday-only mode and says so in the log.

Time is pinned by constructing tz-aware IST instants and passing them in, or
by monkeypatching `app.clock._utc_now` — the module's single wall-clock seam.
"""

import datetime
import json
import logging

import pytest

from app import clock, greeting
from app.agent.prompt import PRIMED_INSTRUCTIONS, primed_messages, snapshot_text

IST = clock.IST


def at(year, month, day, hour=0, minute=0) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, minute, tzinfo=IST)


@pytest.fixture(autouse=True)
def _fresh_calendar():
    """The calendar cache is process-wide; never let it leak between tests."""
    clock.reset_calendar_cache()
    yield
    clock.reset_calendar_cache()


@pytest.fixture
def calendar_file(monkeypatch, tmp_path):
    """Point the clock at a bespoke calendar file (or a missing one)."""

    def _point_at(payload: object | None, *, raw: str | None = None):
        target = tmp_path / "market_calendar.json"
        if raw is not None:
            target.write_text(raw, encoding="utf-8")
        elif payload is not None:
            target.write_text(json.dumps(payload), encoding="utf-8")
        # payload None and raw None -> file deliberately absent
        monkeypatch.setattr(clock, "CALENDAR_PATH", target)
        clock.reset_calendar_cache()
        return target

    return _point_at


# --- the shipped calendar itself ---------------------------------------------


def test_calendar_parses_and_declares_its_coverage():
    calendar = clock.load_calendar()
    assert not calendar.unavailable
    assert calendar.coverage_from == datetime.date(2026, 1, 1)
    assert calendar.coverage_to == datetime.date(2026, 12, 31)
    # All 20 published 2026 entries, weekend-falling ones included.
    assert len(calendar.holidays) == 20
    assert datetime.date(2026, 11, 8) in calendar.special_sessions


def test_every_stored_holiday_matches_its_stated_weekday():
    """Task 1.3: a date typo would otherwise close the market on a random day."""
    with clock.CALENDAR_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    for entry in payload["holidays"]:
        day = datetime.date.fromisoformat(entry["date"])
        assert day.strftime("%A") == entry["weekday"], entry["date"]
        assert entry["fallsOnWeekend"] == (day.weekday() >= 5), entry["date"]


def test_session_windows_come_from_config_not_code():
    calendar = clock.load_calendar()
    windows = {s.key: (s.start, s.end, s.trading_day_required) for s in calendar.sessions}
    assert windows["MORNING"] == (datetime.time(6, 0), datetime.time(9, 0), False)
    assert windows["MARKET"] == (datetime.time(9, 15), datetime.time(15, 30), True)
    assert windows["POST_MARKET"] == (
        datetime.time(15, 30),
        datetime.time(23, 0),
        True,
    )


# --- 6.1 every window boundary ------------------------------------------------

# 2026-07-20 is a Monday and an ordinary trading day.
BOUNDARIES = [
    ((5, 59), clock.KEY_DEFAULT),
    ((6, 0), clock.KEY_MORNING),
    ((8, 59), clock.KEY_MORNING),
    ((9, 0), clock.KEY_DEFAULT),  # NSE pre-open gap (design D7)
    ((9, 14), clock.KEY_DEFAULT),
    ((9, 15), clock.KEY_MARKET),
    ((15, 29), clock.KEY_MARKET),
    ((15, 30), clock.KEY_POST_MARKET),
    ((22, 59), clock.KEY_POST_MARKET),
    ((23, 0), clock.KEY_DEFAULT),  # overnight gap
]


@pytest.mark.parametrize(("hhmm", "expected"), BOUNDARIES)
def test_window_boundaries_on_a_trading_day(hhmm, expected):
    snapshot = clock.market_state(at(2026, 7, 20, *hhmm))
    assert snapshot.greeting_key == expected


def test_market_close_boundary_is_post_market_not_open():
    """15:30:00 exactly: half-open [start, end) puts it in POST_MARKET."""
    assert clock.market_state(at(2026, 7, 20, 15, 30)).state != clock.STATE_OPEN
    assert clock.market_state(at(2026, 7, 20, 15, 29)).state == clock.STATE_OPEN


def test_market_open_boundary_is_open_not_pre_open():
    """09:15:00 exactly: the first instant of the session, not pre-open."""
    assert clock.market_state(at(2026, 7, 20, 9, 15)).state == clock.STATE_OPEN
    assert clock.market_state(at(2026, 7, 20, 9, 14)).state == clock.STATE_PRE_OPEN


def test_open_state_carries_the_session_close_time():
    snapshot = clock.market_state(at(2026, 7, 20, 11, 0))
    assert snapshot.session_close == datetime.time(15, 30)


# --- 6.2 trading day vs holiday vs weekend -----------------------------------


@pytest.mark.parametrize(
    ("day", "description"),
    [
        (datetime.date(2026, 1, 15), "Municipal Corporation Election"),
        (datetime.date(2026, 1, 26), "Republic Day"),
        (datetime.date(2026, 3, 3), "Holi"),
        (datetime.date(2026, 4, 3), "Good Friday"),
        (datetime.date(2026, 5, 1), "Maharashtra Day"),
        (datetime.date(2026, 9, 14), "Ganesh Chaturthi"),
        (datetime.date(2026, 10, 2), "Gandhi Jayanti"),
        (datetime.date(2026, 12, 25), "Christmas"),
    ],
)
def test_sampled_weekday_closures_are_not_trading_days(day, description):
    assert not clock.is_trading_day(day), description
    snapshot = clock.market_state(
        datetime.datetime.combine(day, datetime.time(11, 0), tzinfo=IST)
    )
    assert snapshot.state == clock.STATE_HOLIDAY
    assert snapshot.greeting_key == clock.KEY_DEFAULT


def test_weekend_is_not_a_trading_day_but_is_not_a_holiday_state():
    saturday = at(2026, 7, 18, 11, 0)
    assert not clock.is_trading_day(saturday.date())
    snapshot = clock.market_state(saturday)
    assert snapshot.state == clock.STATE_CLOSED
    assert snapshot.greeting_key == clock.KEY_DEFAULT


def test_weekend_falling_holiday_is_a_no_op():
    """15 Feb 2026 is a Sunday closure — already closed, nothing changes."""
    assert not clock.is_trading_day(datetime.date(2026, 2, 15))


def test_ordinary_weekday_is_a_trading_day():
    assert clock.is_trading_day(datetime.date(2026, 7, 20))


def test_morning_window_applies_on_a_non_trading_day():
    """MORNING asserts nothing about the market, so it holds on a Sunday."""
    snapshot = clock.market_state(at(2026, 7, 19, 7, 0))
    assert snapshot.greeting_key == clock.KEY_MORNING
    assert snapshot.trading_day is False


def test_market_windows_require_a_trading_day():
    """11:00 on Republic Day is DEFAULT — never MARKET."""
    assert clock.market_state(at(2026, 1, 26, 11, 0)).greeting_key == clock.KEY_DEFAULT
    assert clock.market_state(at(2026, 1, 26, 16, 0)).greeting_key == clock.KEY_DEFAULT


# --- 6.3 Muhurat: additions win ----------------------------------------------


def test_muhurat_sunday_is_a_trading_day():
    """The whole reason the calendar models sessions rather than closures."""
    day = datetime.date(2026, 11, 8)
    assert day.weekday() == 6  # Sunday
    assert day in clock.load_calendar().holidays  # AND listed as a holiday
    assert clock.is_trading_day(day)  # ...and still a trading day


def test_muhurat_window_is_muhurat_not_default_and_not_post_market():
    snapshot = clock.market_state(at(2026, 11, 8, 18, 30))
    assert snapshot.greeting_key == "MUHURAT"
    assert snapshot.greeting_key != clock.KEY_DEFAULT
    assert snapshot.greeting_key != clock.KEY_POST_MARKET
    assert snapshot.state == clock.STATE_OPEN
    assert snapshot.session_close == datetime.time(19, 0)


def test_muhurat_date_does_not_inherit_the_ordinary_post_market_window():
    """16:00 on Muhurat Sunday: the special windows replace the default pair,
    so we never claim 'markets are closed' before the session has run."""
    snapshot = clock.market_state(at(2026, 11, 8, 16, 0))
    assert snapshot.greeting_key == clock.KEY_DEFAULT
    assert snapshot.state == clock.STATE_PRE_OPEN
    assert snapshot.next_open == datetime.time(18, 0)


def test_muhurat_morning_still_greets_normally():
    assert clock.market_state(at(2026, 11, 8, 7, 0)).greeting_key == clock.KEY_MORNING


def test_the_day_after_muhurat_diwali_balipratipada_is_closed():
    assert not clock.is_trading_day(datetime.date(2026, 11, 10))


# --- 6.4 equity segment only --------------------------------------------------


def test_new_years_day_is_an_ordinary_equity_trading_day():
    """1 Jan 2026 appears only in the COMMODITY table. Importing it would
    close the equity market on a day it trades normally."""
    day = datetime.date(2026, 1, 1)
    assert day not in clock.load_calendar().holidays
    assert clock.is_trading_day(day)
    assert clock.market_state(at(2026, 1, 1, 11, 0)).state == clock.STATE_OPEN


# --- 6.5 coverage guard -------------------------------------------------------


def test_out_of_coverage_date_degrades_loudly(caplog):
    with caplog.at_level(logging.WARNING, logger="app.clock"):
        snapshot = clock.market_state(at(2027, 1, 26, 11, 0))
    assert snapshot.degraded is True
    assert "does not cover" in caplog.text
    assert "degraded weekday-only" in caplog.text


def test_out_of_coverage_is_never_reported_as_authoritative():
    """The dangerous failure: 26 Jan 2027 answered as a normal trading day
    with no signal. Weekday-only is the answer, but `degraded` marks it."""
    snapshot = clock.market_state(at(2027, 1, 26, 11, 0))
    assert snapshot.trading_day is True  # weekday-only fallback
    assert snapshot.degraded is True  # ...and the caller is told
    assert "approximate" in clock.status_line(at(2027, 1, 26, 11, 0))


def test_out_of_coverage_weekend_still_reads_as_closed():
    snapshot = clock.market_state(at(2027, 1, 24, 11, 0))  # a Sunday
    assert snapshot.trading_day is False
    assert snapshot.degraded is True


def test_out_of_coverage_ignores_stale_special_sessions():
    """A 2027 date must not pick up 2026's Muhurat entry by accident."""
    assert clock.market_state(at(2027, 11, 8, 18, 30)).special_session is None


# --- 2.4 unreadable / malformed calendar --------------------------------------


def test_missing_calendar_answers_from_weekday_logic(calendar_file, caplog):
    calendar_file(None)
    with caplog.at_level(logging.WARNING, logger="app.clock"):
        snapshot = clock.market_state(at(2026, 1, 26, 11, 0))
    assert snapshot.degraded is True
    assert "unreadable" in caplog.text
    # Callers get an answer, never an exception.
    assert snapshot.state in {clock.STATE_OPEN, clock.STATE_PRE_OPEN, clock.STATE_CLOSED}


def test_malformed_calendar_degrades_with_a_warning(calendar_file, caplog):
    calendar_file(None, raw="{ this is not json")
    with caplog.at_level(logging.WARNING, logger="app.clock"):
        assert clock.market_state(at(2026, 7, 20, 11, 0)).degraded is True
    assert "malformed" in caplog.text


def test_calendar_with_a_bad_date_degrades_rather_than_raising(calendar_file):
    calendar_file(
        {
            "coverageFrom": "2026-01-01",
            "coverageTo": "2026-12-31",
            "sessions": {"market": {"key": "MARKET", "start": "09:15", "end": "15:30"}},
            "holidays": [{"date": "2026-13-45", "description": "nonsense"}],
        }
    )
    assert clock.load_calendar().unavailable is True


def test_calendar_without_sessions_degrades(calendar_file):
    calendar_file({"coverageFrom": "2026-01-01", "coverageTo": "2026-12-31"})
    assert clock.load_calendar().unavailable is True


def test_calendar_edits_go_live_without_a_restart(calendar_file):
    """The cache is keyed on mtime, so a corrected holiday takes effect."""
    payload = {
        "coverageFrom": "2026-01-01",
        "coverageTo": "2026-12-31",
        "sessions": {
            "market": {
                "key": "MARKET",
                "start": "09:15",
                "end": "15:30",
                "tradingDayRequired": True,
            }
        },
        "holidays": [],
        "specialSessions": [],
    }
    target = calendar_file(payload)
    assert clock.is_trading_day(datetime.date(2026, 7, 20))

    payload["holidays"] = [{"date": "2026-07-20", "description": "Newly declared"}]
    target.write_text(json.dumps(payload), encoding="utf-8")
    import os

    stat = target.stat()
    os.utime(target, (stat.st_atime + 10, stat.st_mtime + 10))
    assert not clock.is_trading_day(datetime.date(2026, 7, 20))


# --- status line --------------------------------------------------------------


def test_status_line_open_market_states_time_weekday_date_and_close():
    assert clock.status_line(at(2026, 7, 20, 14, 47)) == (
        "Right now it is 2:47 pm IST on Monday, 20 July 2026. "
        "Markets are open; the equity session closes at 3:30 pm."
    )


def test_status_line_holiday_is_explicit_about_the_holiday():
    line = clock.status_line(at(2026, 1, 26, 11, 0))
    assert "Markets are closed today for Republic Day (exchange holiday)." in line


def test_status_line_after_close_names_the_close_time():
    """The 15:20 cutoff question is answerable because the close time is here."""
    line = clock.status_line(at(2026, 7, 20, 16, 0))
    assert "closed at 3:30 pm" in line


def test_status_line_before_open_names_the_open_time():
    assert "opens at 9:15 am" in clock.status_line(at(2026, 7, 20, 8, 0))


def test_status_line_weekend():
    assert "closed for the weekend" in clock.status_line(at(2026, 7, 19, 11, 0))


def test_status_line_muhurat_is_open_not_closed():
    line = clock.status_line(at(2026, 11, 8, 18, 30))
    assert "Markets are open for a special session" in line
    assert "closed" not in line


def test_status_line_uses_ist_regardless_of_the_host_zone(monkeypatch):
    """01:00 IST on the 21st while the container's UTC clock says the 20th."""
    monkeypatch.setattr(
        clock,
        "_utc_now",
        lambda: datetime.datetime(2026, 7, 20, 19, 30, tzinfo=datetime.timezone.utc),
    )
    assert clock.status_line().startswith(
        "Right now it is 1:00 am IST on Tuesday, 21 July 2026."
    )


def test_naive_datetimes_are_read_as_ist():
    naive = datetime.datetime(2026, 7, 20, 11, 0)
    assert clock.market_state(naive).greeting_key == clock.KEY_MARKET


def test_utc_datetimes_are_converted_before_matching():
    """09:00 UTC is 14:30 IST — inside the session, not before it."""
    utc = datetime.datetime(2026, 7, 20, 9, 0, tzinfo=datetime.timezone.utc)
    assert clock.market_state(utc).greeting_key == clock.KEY_MARKET


# --- prompt: two blocks, live line last (5.1–5.3) -----------------------------


def test_primed_turn_is_two_blocks_with_the_live_line_last():
    blocks = primed_messages(at(2026, 7, 20, 14, 47))[0]["content"]
    assert [b["type"] for b in blocks] == ["text", "text"]
    assert blocks[0]["text"] == PRIMED_INSTRUCTIONS
    assert blocks[1]["text"].startswith("Right now it is ")


def test_cache_breakpoint_sits_on_the_frozen_block_only():
    blocks = primed_messages(at(2026, 7, 20, 14, 47))[0]["content"]
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocks[1]


def test_no_volatile_value_appears_before_the_breakpoint():
    """Two requests minutes apart: every block up to and including the
    breakpoint is byte-identical; only the final block differs."""
    first = primed_messages(at(2026, 7, 20, 14, 47))[0]["content"]
    second = primed_messages(at(2026, 7, 20, 14, 52))[0]["content"]
    assert first[0] == second[0]
    assert first[1] != second[1]


def test_frozen_block_carries_no_rendered_clock():
    """The few-shot examples do contain literal dates; what must never appear
    is the *current* clock, which is what would churn the cache."""
    text = primed_messages(at(2026, 7, 20, 14, 47))[0]["content"][0]["text"]
    for volatile in ("Right now", "Today's date", "20 July", "2:47 pm", "Monday"):
        assert volatile not in text


def test_snapshot_keeps_placeholders_so_the_hash_is_time_stable():
    text = snapshot_text()
    assert clock.STATUS_LINE_TEMPLATE in text
    assert "{time}" in text and "{date}" in text and "{market}" in text
    # Two snapshots minutes apart are identical by construction.
    assert snapshot_text() == text


def test_first_name_rides_the_volatile_block_not_the_cached_prefix():
    """CHO-246: the client's first name appears only in the post-breakpoint
    tail block, never in the cached instructions — so per-client names never
    churn the shared cached prefix."""
    blocks = primed_messages(at(2026, 7, 20, 14, 47), first_name="Harsha")[0]["content"]
    assert "Harsha" not in blocks[0]["text"]
    assert "Harsha" in blocks[1]["text"]
    # No name → the tail is just the status line (no dangling name text).
    plain = primed_messages(at(2026, 7, 20, 14, 47))[0]["content"][1]["text"]
    assert "speaking with" not in plain


def test_first_name_never_enters_the_prompt_snapshot():
    """The name is volatile, so the recorded snapshot (the hash source) must
    not carry it — the prompt hash stays stable across clients."""
    assert "Harsha" not in snapshot_text()


def test_self_only_data_guardrail_is_in_the_frozen_instructions():
    """CHO-246: the 'only your own account' rule ships in the cached prompt."""
    assert "I can fetch reports only for your account." in PRIMED_INSTRUCTIONS


def test_followup_reopens_the_seeded_form_rule_is_in_the_instructions():
    """CHO-252: follow-ups (params from a prior flow event) re-open the seeded
    form rather than executing the report tool directly."""
    assert "FOLLOW-UPS re-open the form" in PRIMED_INSTRUCTIONS


def test_snapshot_records_no_rendered_clock():
    assert "Right now it is 2:47 pm" not in snapshot_text()


def test_user_facing_voice_block_is_in_the_frozen_instructions():
    """CHO-265: USER-FACING VOICE + banned categories ship in the cached prompt."""
    assert "USER-FACING VOICE" in PRIMED_INSTRUCTIONS
    for phrase in (
        "knowledge base",
        "search results",
        "let me search",
        "let me search more specifically",
        "this is likely",
        "based on what I found",
        "That isn't covered in our support guides",
        "NOT a global hedge",
    ):
        assert phrase in PRIMED_INSTRUCTIONS
    assert "USER-FACING VOICE" in snapshot_text()
    # scattered one-liner consolidated into the voice block
    assert "Never narrate retrieval or internal steps" not in PRIMED_INSTRUCTIONS


def test_cost_price_miss_few_shot_is_in_the_instructions():
    """CHO-265: Jam-shaped miss → allowed phrasing + ticket ask, silent tool call."""
    assert "update cost price for shares I bought outside FinX" in PRIMED_INSTRUCTIONS
    assert "That isn't covered in our support guides" in PRIMED_INSTRUCTIONS


# --- greeting selection (3.x) -------------------------------------------------


def test_greeting_selects_the_market_template_during_market_hours():
    key, template = greeting.select_greeting("Pritam", at(2026, 7, 20, 11, 0))
    assert key == clock.KEY_MARKET
    assert "{clientRef}" in template


def test_greeting_falls_back_to_default_on_a_holiday():
    key, template = greeting.select_greeting("Pritam", at(2026, 1, 26, 11, 0))
    assert key == clock.KEY_DEFAULT
    assert template == "Hey {clientRef} — what do you need?"


def test_greeting_uses_the_placeholder_free_fallback_without_a_name():
    for first_name in (None, ""):
        key, template = greeting.select_greeting(first_name, at(2026, 7, 20, 11, 0))
        assert key == clock.KEY_MARKET
        assert "{clientRef}" not in template
        assert "  " not in template
        assert not template.startswith(("—", ",", " "))


def test_greeting_degrades_to_default_when_the_calendar_is_gone(calendar_file):
    """26 Jan at 11:00 is inside the MARKET window on a weekday — with no
    calendar we must NOT greet with 'markets are live', because we cannot
    know it is not a holiday. DEFAULT asserts nothing."""
    calendar_file(None)
    key, template = greeting.select_greeting("Pritam", at(2026, 1, 26, 11, 0))
    assert key == clock.KEY_DEFAULT
    assert template == "Hey {clientRef} — what do you need?"


def test_greeting_degrades_to_default_outside_the_coverage_window():
    key, _ = greeting.select_greeting("Pritam", at(2027, 1, 26, 11, 0))
    assert key == clock.KEY_DEFAULT


def test_greeting_degrades_to_default_when_the_clock_raises(monkeypatch):
    def boom(_now=None):
        raise RuntimeError("clock exploded")

    monkeypatch.setattr(clock, "market_state", boom)
    key, template = greeting.select_greeting("Pritam")
    assert key == clock.KEY_DEFAULT
    assert template == "Hey {clientRef} — what do you need?"


def test_greeting_content_is_recoverable_when_the_copy_file_is_gone(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(greeting, "GREETINGS_PATH", tmp_path / "missing.json")
    key, template = greeting.select_greeting("Pritam", at(2026, 7, 20, 11, 0))
    assert key == clock.KEY_DEFAULT
    assert template == "Hey {clientRef} — what do you need?"


def test_every_key_the_clock_can_emit_has_copy():
    content = greeting.load_greetings()
    keys = {clock.KEY_DEFAULT, clock.KEY_MORNING, clock.KEY_MARKET, clock.KEY_POST_MARKET}
    keys |= {s.key for s in clock.load_calendar().special_sessions.values()}
    for key in keys:
        assert key in content["templates"], key
        assert key in content["fallbackTemplates"], key
        assert "{clientRef}" in content["templates"][key], key
        assert "{clientRef}" not in content["fallbackTemplates"][key], key


# --- 6.7 the DEFAULT key renders byte-identically to today's headline ---------

# The pre-CHO-226 headline, as JSX renders it: "Hey " + <span>{name}</span> +
# " — what do you need?" (JSX collapses the newline + indentation into one
# space). EmptyState now splits the template on {clientRef} and drops the name
# into that same span — this mirrors that split so a copy change that would
# alter the painted headline fails here, on the backend, where the copy lives.
STATIC_HEADLINE = "Hey Pritam — what do you need?"
STATIC_HEADLINE_NO_NAME = "Hey there — what do you need?"


def render_headline(template: str, first_name: str | None) -> str:
    """Mirror of EmptyState's `Headline` split (frontend has no test runner)."""
    if "{clientRef}" not in template:
        return template
    head, _, tail = template.partition("{clientRef}")
    return f"{head}{first_name or 'there'}{tail}"


def test_default_key_renders_byte_identically_to_the_current_greeting():
    _, template = greeting.select_greeting("Pritam", at(2026, 1, 26, 11, 0))
    assert render_headline(template, "Pritam") == STATIC_HEADLINE


def test_default_fallback_renders_byte_identically_without_a_name():
    _, template = greeting.select_greeting(None, at(2026, 1, 26, 11, 0))
    assert render_headline(template, None) == STATIC_HEADLINE_NO_NAME


@pytest.mark.parametrize(
    "hhmm_and_day",
    [
        ((2026, 7, 20), (7, 0)),  # MORNING
        ((2026, 7, 20), (11, 0)),  # MARKET
        ((2026, 7, 20), (16, 0)),  # POST_MARKET
        ((2026, 11, 8), (18, 30)),  # MUHURAT
        ((2026, 1, 26), (11, 0)),  # DEFAULT
    ],
)
def test_no_window_ever_renders_a_broken_headline(hhmm_and_day):
    (year, month, day), (hour, minute) = hhmm_and_day
    when = at(year, month, day, hour, minute)
    for first_name in ("Pritam", None):
        _, template = greeting.select_greeting(first_name, when)
        line = render_headline(template, first_name)
        assert "{clientRef}" not in line
        assert "  " not in line
        assert line.strip() == line
