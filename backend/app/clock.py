"""The one clock the agent reasons on: India Standard Time (CHO-224) plus the
NSE equity market session calendar (CHO-226).

Everything the *user* experiences as "now" — the date in the prompt, the
bounds the report-form validator applies, the greeting on the entry screen,
"are markets open" — is Indian market time, so it is resolved here against an
explicitly named zone rather than inherited from whatever timezone the host or
container happens to carry.

Why this module exists at all: `datetime.date.today()` reads the process's
local zone. A developer machine set to `Asia/Kolkata` returns the right
answer, but the deployed image (`ghcr.io/astral-sh/uv:python3.12-bookworm-slim`,
no `TZ`, no `/etc/localtime` mount) reports UTC. IST is UTC+5:30, so the UTC
date rolls over at 05:30 IST — between midnight and half past five in the
morning India time the container believed it was still yesterday. Naming the
zone removes the environment dependency by construction.

`tzdata` is a hard dependency (see pyproject.toml): the slim Debian image is
not guaranteed to ship the IANA zone database, and `ZoneInfo` raises
`ZoneInfoNotFoundError` without it.

Scope: this module answers "what time/date is it in India" and "what is the
market doing right now". Storage timestamps deliberately stay UTC (see
`app/agent/store.py`) — UTC is the right zone for a database column, IST is
the right zone for a human-facing date.

The market half (CHO-226) rests on three rules, each of which exists because
the obvious alternative is wrong:

1. **Sessions, not closures.** `is_trading_day(d)` is
   `d in specialSessions OR (weekday AND NOT holiday)` — additions win over
   subtractions. Sunday 8 November 2026 is a trading day (Diwali Laxmi Pujan
   Muhurat) *and* appears in `holidays[]`; a weekday-minus-holidays predicate
   can never return true for it.
2. **Half-open windows `[start, end)` walked in declared order**, so 15:30:00
   is unambiguously POST_MARKET and 09:15:00 is unambiguously MARKET.
3. **A coverage guard that degrades loudly.** The seeded calendar covers 2026
   only. An expired calendar's failure mode is worse than a missing one:
   "not in the holiday list" reads as "ordinary trading day", so a stale 2026
   list would cheerfully assert an open market on Republic Day 2027. Any date
   outside `coverageFrom`/`coverageTo` — and any unreadable or malformed file
   — routes to weekday-only degraded mode *and logs a warning*, never to
   "no holidays found".

Callers never see an exception from this module: every failure path lands in
degraded mode with an answer.
"""

import datetime
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

logger = logging.getLogger("app.clock")

CALENDAR_PATH = (
    Path(__file__).resolve().parent.parent / "content" / "market_calendar.json"
)

# Greeting/window keys. MUHURAT is not listed here — special-session keys come
# from the calendar, because their timings are published days in advance and
# must be editable config rather than a code constant (design D2).
KEY_MORNING = "MORNING"
KEY_MARKET = "MARKET"
KEY_POST_MARKET = "POST_MARKET"
KEY_DEFAULT = "DEFAULT"

# Market states (proposal): the four the prompt's status line distinguishes.
STATE_OPEN = "OPEN"
STATE_PRE_OPEN = "PRE_OPEN"
STATE_CLOSED = "CLOSED"
STATE_HOLIDAY = "HOLIDAY"

# The status line the agent prompt appends as its LAST content block. Kept
# here (not in prompt.py) so `snapshot_text()` can record the *unformatted*
# template and the prompt hash stays time-stable (agent-loop spec).
STATUS_LINE_TEMPLATE = "Right now it is {time} IST on {weekday}, {date}. {market}"


def _utc_now() -> datetime.datetime:
    """The single seam where real wall-clock time enters this module.

    Isolated so tests can pin an instant (monkeypatch this) without patching
    `datetime` itself, and so any future time-dependent helper here is
    freezable by the same one-line patch.
    """
    return datetime.datetime.now(datetime.timezone.utc)


def ist_now() -> datetime.datetime:
    """Current moment as a tz-aware datetime in `Asia/Kolkata`."""
    return _utc_now().astimezone(IST)


def ist_today() -> datetime.date:
    """Today's calendar date in India, independent of the process timezone."""
    return ist_now().date()


# --- calendar model ----------------------------------------------------------


@dataclass(frozen=True)
class Session:
    """A default session window, declared in the calendar (task 1.2)."""

    key: str
    start: datetime.time
    end: datetime.time
    trading_day_required: bool


@dataclass(frozen=True)
class SpecialSession:
    """A dated session with its own windows — Muhurat and friends.

    Its presence makes the date a trading day even when the date is a weekend
    or also appears in `holidays[]`: additions win (design D2).
    """

    date: datetime.date
    key: str
    description: str
    windows: tuple[tuple[datetime.time, datetime.time], ...]


@dataclass(frozen=True)
class Window:
    """One resolved candidate window for a specific date."""

    key: str
    start: datetime.time
    end: datetime.time


# Code-side fallback used ONLY when the calendar file cannot be read or parsed.
# The live values live in content/market_calendar.json (task 1.2); these exist
# so an unreadable file still yields sane windows instead of an exception.
_FALLBACK_SESSIONS: tuple[Session, ...] = (
    Session(KEY_MORNING, datetime.time(6, 0), datetime.time(9, 0), False),
    Session(KEY_MARKET, datetime.time(9, 15), datetime.time(15, 30), True),
    Session(KEY_POST_MARKET, datetime.time(15, 30), datetime.time(23, 0), True),
)


@dataclass(frozen=True)
class Calendar:
    sessions: tuple[Session, ...]
    holidays: dict[datetime.date, str]
    special_sessions: dict[datetime.date, SpecialSession]
    coverage_from: datetime.date | None
    coverage_to: datetime.date | None
    #: True when this is the code fallback — the file was missing or malformed.
    unavailable: bool

    def covers(self, day: datetime.date) -> bool:
        if self.unavailable or self.coverage_from is None or self.coverage_to is None:
            return False
        return self.coverage_from <= day <= self.coverage_to


_UNAVAILABLE_CALENDAR = Calendar(
    sessions=_FALLBACK_SESSIONS,
    holidays={},
    special_sessions={},
    coverage_from=None,
    coverage_to=None,
    unavailable=True,
)

# (mtime, Calendar) — re-read when the file changes so a calendar edit goes
# live without a server restart (same philosophy as content/whats_new.json).
_cache: tuple[float, Calendar] | None = None


def reset_calendar_cache() -> None:
    """Drop the cached parse. Tests call this; production rarely needs it."""
    global _cache
    _cache = None


def _parse_time(raw: object) -> datetime.time:
    if not isinstance(raw, str):
        raise ValueError("time must be a string")
    hour, _, minute = raw.partition(":")
    return datetime.time(int(hour), int(minute))


def _parse_date(raw: object) -> datetime.date:
    if not isinstance(raw, str):
        raise ValueError("date must be a string")
    return datetime.date.fromisoformat(raw)


def _parse_calendar(payload: object) -> Calendar:
    """Strict parse: anything unexpected raises, and the caller degrades."""
    if not isinstance(payload, dict):
        raise ValueError("calendar root must be an object")

    raw_sessions = payload.get("sessions")
    if not isinstance(raw_sessions, dict) or not raw_sessions:
        raise ValueError("calendar has no sessions")
    sessions = tuple(
        Session(
            key=str(entry["key"]),
            start=_parse_time(entry["start"]),
            end=_parse_time(entry["end"]),
            trading_day_required=bool(entry.get("tradingDayRequired", False)),
        )
        # dicts preserve insertion order, so "declared order" is JSON order.
        for entry in raw_sessions.values()
        if isinstance(entry, dict)
    )
    if len(sessions) != len(raw_sessions):
        raise ValueError("malformed session entry")

    holidays: dict[datetime.date, str] = {}
    for entry in payload.get("holidays") or []:
        if not isinstance(entry, dict):
            raise ValueError("malformed holiday entry")
        holidays[_parse_date(entry["date"])] = str(entry.get("description", "holiday"))

    specials: dict[datetime.date, SpecialSession] = {}
    for entry in payload.get("specialSessions") or []:
        if not isinstance(entry, dict):
            raise ValueError("malformed special session entry")
        day = _parse_date(entry["date"])
        windows = tuple(
            (_parse_time(w["start"]), _parse_time(w["end"]))
            for w in entry.get("windows") or []
            if isinstance(w, dict)
        )
        if not windows:
            raise ValueError("special session without windows")
        specials[day] = SpecialSession(
            date=day,
            key=str(entry.get("key", "MUHURAT")),
            description=str(entry.get("description", "special session")),
            windows=windows,
        )

    return Calendar(
        sessions=sessions,
        holidays=holidays,
        special_sessions=specials,
        coverage_from=_parse_date(payload["coverageFrom"]),
        coverage_to=_parse_date(payload["coverageTo"]),
        unavailable=False,
    )


def load_calendar(path: Path | None = None) -> Calendar:
    """The market calendar, cached on the file's mtime.

    Never raises: an unreadable or malformed file logs a warning and returns
    the explicitly-unavailable calendar, which every consumer treats as
    degraded weekday-only mode (spec: "an out-of-coverage or unavailable
    calendar degrades loudly").
    """
    global _cache
    target = path or CALENDAR_PATH
    try:
        mtime = target.stat().st_mtime
    except OSError as exc:
        logger.warning(
            "market calendar unreadable error=%s — degraded weekday-only mode",
            type(exc).__name__,
        )
        return _UNAVAILABLE_CALENDAR

    if path is None and _cache is not None and _cache[0] == mtime:
        return _cache[1]

    try:
        with target.open(encoding="utf-8") as handle:
            calendar = _parse_calendar(json.load(handle))
    except Exception as exc:  # malformed JSON, bad dates, missing keys
        logger.warning(
            "market calendar malformed error=%s — degraded weekday-only mode",
            type(exc).__name__,
        )
        return _UNAVAILABLE_CALENDAR

    if path is None:
        _cache = (mtime, calendar)
    return calendar


# --- trading-day predicate ---------------------------------------------------


def _degraded_for(day: datetime.date, calendar: Calendar) -> bool:
    """True when this date has no holiday data — and say so, loudly."""
    if calendar.unavailable:
        # load_calendar() already logged the read/parse failure.
        return True
    if not calendar.covers(day):
        logger.warning(
            "market calendar does not cover date=%s (coverage %s..%s) — "
            "degraded weekday-only mode, NOT 'no holidays found'",
            day.isoformat(),
            calendar.coverage_from,
            calendar.coverage_to,
        )
        return True
    return False


def is_trading_day(day: datetime.date, calendar: Calendar | None = None) -> bool:
    """`day in specialSessions OR (weekday AND NOT holiday)`.

    Additions win: Sunday 8 Nov 2026 is a trading day (Muhurat) even though it
    is a Sunday and also carries a `holidays[]` entry. Out of coverage, this
    falls back to weekday-only — the caller learns that from
    `market_state().degraded`, and a warning is logged.
    """
    calendar = calendar if calendar is not None else load_calendar()
    if _degraded_for(day, calendar):
        return day.weekday() < 5
    if day in calendar.special_sessions:
        return True
    return day.weekday() < 5 and day not in calendar.holidays


# --- market state ------------------------------------------------------------


@dataclass(frozen=True)
class MarketSnapshot:
    """Everything both consumers need from one walk of the windows."""

    now: datetime.datetime
    state: str
    #: MORNING | MARKET | POST_MARKET | <special key> | DEFAULT
    greeting_key: str
    trading_day: bool
    #: End of the open session (OPEN), or the session that just ended (CLOSED).
    session_close: datetime.time | None
    #: Start of the session yet to open (PRE_OPEN).
    next_open: datetime.time | None
    #: Description of the special session in play, if any.
    special_session: str | None
    holiday: str | None
    #: True when no holiday data applies to this date (out of coverage, or
    #: the file could not be read) — the answer is weekday-only guesswork.
    degraded: bool


def _windows_for(
    day: datetime.date,
    calendar: Calendar,
    trading_day: bool,
    special: SpecialSession | None,
) -> tuple[list[Window], list[Window]]:
    """(candidate windows in walk order, the day's market-open windows).

    A special-session date uses ITS declared windows for the market — the
    ordinary 09:15–15:30 / 15:30–23:00 pair does not apply (design D2's
    branch structure), so 16:00 on Muhurat Sunday is DEFAULT rather than a
    "markets are closed" post-market claim. Sessions that do not require a
    trading day (MORNING) still apply on every date, special or not.
    """
    if special is not None:
        market = [Window(special.key, start, end) for start, end in special.windows]
        others = [
            Window(s.key, s.start, s.end)
            for s in calendar.sessions
            if not s.trading_day_required
        ]
        return market + others, market

    candidates = [
        Window(s.key, s.start, s.end)
        for s in calendar.sessions
        if trading_day or not s.trading_day_required
    ]
    market = [w for w in candidates if w.key == KEY_MARKET]
    return candidates, market


def _derive_state(
    *,
    matched: Window | None,
    market_windows: list[Window],
    clock_time: datetime.time,
    trading_day: bool,
    special: SpecialSession | None,
    weekday_holiday: bool,
) -> tuple[str, datetime.time | None, datetime.time | None]:
    """(state, session_close, next_open) from the matched window.

    OPEN is "inside the market window" — the ordinary equity session, or a
    declared special session's window. Before that window on a trading day is
    PRE_OPEN (so the model can say when trading starts); after it is CLOSED
    with the time the session ended.
    """
    open_keys = {KEY_MARKET} | ({special.key} if special is not None else set())
    if matched is not None and matched.key in open_keys:
        return STATE_OPEN, matched.end, None
    if trading_day and market_windows:
        if clock_time < market_windows[0].start:
            return STATE_PRE_OPEN, None, market_windows[0].start
        return STATE_CLOSED, market_windows[-1].end, None
    if weekday_holiday:
        return STATE_HOLIDAY, None, None
    return STATE_CLOSED, None, None


def market_state(now: datetime.datetime | None = None) -> MarketSnapshot:
    """The market's state at `now` (IST), plus the matching greeting window.

    Window matching is half-open `[start, end)` in declared order, so a
    boundary instant belongs to exactly one window: 09:15:00 is MARKET,
    15:30:00 is POST_MARKET.
    """
    now = now if now is not None else ist_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)

    day = now.date()
    clock_time = now.timetz().replace(tzinfo=None)
    calendar = load_calendar()
    degraded = _degraded_for(day, calendar)

    special = None if degraded else calendar.special_sessions.get(day)
    holiday = None if degraded else calendar.holidays.get(day)
    trading_day = is_trading_day(day, calendar)

    candidates, market_windows = _windows_for(day, calendar, trading_day, special)
    matched = next(
        (w for w in candidates if w.start <= clock_time < w.end),
        None,
    )

    greeting_key = matched.key if matched is not None else KEY_DEFAULT
    state, session_close, next_open = _derive_state(
        matched=matched,
        market_windows=market_windows,
        clock_time=clock_time,
        trading_day=trading_day,
        special=special,
        weekday_holiday=holiday is not None and day.weekday() < 5,
    )

    return MarketSnapshot(
        now=now,
        state=state,
        greeting_key=greeting_key,
        trading_day=trading_day,
        session_close=session_close,
        next_open=next_open,
        special_session=special.description if special is not None else None,
        holiday=holiday,
        degraded=degraded,
    )


# --- rendering ---------------------------------------------------------------


def format_time(value: datetime.time) -> str:
    """`2:47 pm` — built by hand because `%-I` is a glibc extension."""
    hour = value.hour % 12 or 12
    meridiem = "am" if value.hour < 12 else "pm"
    return f"{hour}:{value.minute:02d} {meridiem}"


def format_date(value: datetime.date) -> str:
    """`20 July 2026` — day number unpadded, again avoiding `%-d`."""
    return f"{value.day} {value:%B} {value.year}"


def _open_sentence(snapshot: MarketSnapshot) -> str:
    close = format_time(snapshot.session_close) if snapshot.session_close else None
    if snapshot.special_session is not None:
        opener = f"Markets are open for a special session — {snapshot.special_session}"
        return f"{opener}; it closes at {close}." if close else f"{opener}."
    if close is None:
        return "Markets are open."
    return f"Markets are open; the equity session closes at {close}."


def _pre_open_sentence(snapshot: MarketSnapshot) -> str:
    if snapshot.next_open is None:
        return "Markets are not open yet."
    label = "the Muhurat session" if snapshot.special_session else "the equity session"
    return f"Markets are not open yet; {label} opens at {format_time(snapshot.next_open)}."


def _closed_sentence(snapshot: MarketSnapshot) -> str:
    if snapshot.trading_day and snapshot.session_close is not None:
        closed = format_time(snapshot.session_close)
        return f"Markets are closed for the day; the equity session closed at {closed}."
    if snapshot.now.weekday() >= 5:
        return "Markets are closed for the weekend."
    return "Markets are closed."


def _market_sentence(snapshot: MarketSnapshot) -> str:
    if snapshot.state == STATE_OPEN:
        return _open_sentence(snapshot)
    if snapshot.state == STATE_PRE_OPEN:
        return _pre_open_sentence(snapshot)
    if snapshot.state == STATE_HOLIDAY:
        return f"Markets are closed today for {snapshot.holiday} (exchange holiday)."
    return _closed_sentence(snapshot)


def status_line(now: datetime.datetime | None = None) -> str:
    """The live IST status line the agent prompt ends with.

    e.g. `Right now it is 2:47 pm IST on Monday, 20 July 2026. Markets are
    open; the equity session closes at 3:30 pm.`

    In degraded mode the market claim is hedged rather than dropped: the model
    still needs the clock, but must not present a weekday-only guess as fact.
    """
    snapshot = market_state(now)
    market = _market_sentence(snapshot)
    if snapshot.degraded:
        market += (
            " (The exchange holiday calendar does not cover this date, so treat"
            " the market status as approximate.)"
        )
    return STATUS_LINE_TEMPLATE.format(
        time=format_time(snapshot.now.time()),
        weekday=f"{snapshot.now:%A}",
        date=format_date(snapshot.now.date()),
        market=market,
    )
