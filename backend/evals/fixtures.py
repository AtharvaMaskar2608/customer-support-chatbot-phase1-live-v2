"""Canned tool envelopes for the eval cases (CHO-276 · task 1.7).

Every envelope here is the SHAPE the real core returns (`data/holdings.py`,
`data/money.py`, `kb/search.py`, `reports/contract_notes.py`, `columns.py`), so a
seeded `tool_result` is byte-indistinguishable from a lived one after
`json.dumps(..., sort_keys=True)`.

Two deliberate design points:

* **Two variants with distinct figures** for holdings (and for the report
  columns). The spent envelope's numbers and labels do not appear in the fresh
  one, which is what turns "did the model recite a stale value?" into a
  mechanical check instead of a judgement call (`assertions.stale_figures`).
* **Synthetic contract-note ids.** Real note ids are 600-second session-bound
  capability tokens over customer documents; nothing resembling one is committed
  here. The ids below are fixed literals that only ever exist inside an eval, so
  the case measures ID FIDELITY and must not be read as proof that a download
  works (design D6).

No credentials, no PANs, no real client codes, no live tokens.
"""

from __future__ import annotations

import datetime

from app.agent.events import friendly_range, render_memo
from app.clock import ist_today
from app.columns import load_registry

# --- date helpers ------------------------------------------------------------


def previous_month_range() -> tuple[str, str]:
    """The last full calendar month as (fromDate, toDate) ISO strings.

    Computed from the IST clock rather than hardcoded: `open_report_form`'s
    validator drops a range that runs into the future or past its 2-year cap, so
    a frozen literal would silently stop being seedable as the year moved on.
    """
    today = ist_today()
    first_of_this = today.replace(day=1)
    last_of_prev = first_of_this - datetime.timedelta(days=1)
    first_of_prev = last_of_prev.replace(day=1)
    return first_of_prev.isoformat(), last_of_prev.isoformat()


# --- E1: the completed ledger flow ------------------------------------------

LEDGER_BOOK = "Normal"


def ledger_form_envelope(from_iso: str, to_iso: str) -> dict:
    """What `open_report_form` returned when the ledger flow was opened."""
    return {
        "kind": "form",
        "flow": "ledger",
        "seed": {
            "book": LEDGER_BOOK,
            "fromDate": from_iso,
            "toDate": to_iso,
            "delivery": "download",
        },
        "prefilled": ["book", "delivery", "fromDate", "toDate"],
        "dropped": [],
        "note": (
            "The guided form is now open in the chat with its own caption; the "
            "user will fill the remaining fields and submit it there. No "
            "assistant text follows a form open — the turn ends here."
        ),
    }


def ledger_flow_memo(from_iso: str, to_iso: str) -> tuple[str, dict]:
    """The app-event memo the ledger route records on success — built with the
    production renderer so the model reads exactly what it reads in prod. The
    ISO pair inside it is what E1 expects the follow-up to carry over."""
    text = render_memo(
        "ledger",
        [f"{LEDGER_BOOK} book", friendly_range(from_iso, to_iso)],
        "download",
    )
    meta = {
        "flow": "ledger",
        "slots": {"book": LEDGER_BOOK, "fromDate": from_iso, "toDate": to_iso},
        "delivery": "download",
        "outcome": "success",
    }
    return text, meta


# --- E2: holdings, two variants with distinct figures ------------------------
#
# Same two scrips and the same cost basis (a cost basis does not move), different
# market values. Only the values that CHANGED are listed in the *_FIGURES
# tuples: quantities, cost prices and percentages are shared or small enough to
# appear incidentally in prose, so they would make the detector noisy.

HOLDINGS_SPENT = {
    "kind": "ok",
    "asOf": "2026-07-24T15:30:00+05:30",
    "rows": [
        {
            "sym": "TCS",
            "name": "Tata Consultancy Services",
            "qty": 60,
            "abp": 3450.5,
            "ltp": 4025.0,
            "current": 241500.0,
            "invested": 207030.0,
            "pnl": 34470.0,
            "pnlPct": 16.65,
            "day": 1230.0,
            "dayPct": 0.51,
            "alloc": 51.18,
        },
        {
            "sym": "RELIANCE",
            "name": "Reliance Industries",
            "qty": 90,
            "abp": 2410.0,
            "ltp": 2560.0,
            "current": 230400.0,
            "invested": 216900.0,
            "pnl": 13500.0,
            "pnlPct": 6.22,
            "day": -810.0,
            "dayPct": -0.35,
            "alloc": 48.82,
        },
    ],
    "totals": {
        "current": 471900.0,
        "invested": 423930.0,
        "pnl": 47970.0,
        "pnlPct": 11.32,
        "day": 420.0,
        "dayPct": 0.09,
        "count": 2,
    },
}

HOLDINGS_FRESH = {
    "kind": "ok",
    "asOf": "2026-07-25T11:04:00+05:30",
    "rows": [
        {
            "sym": "TCS",
            "name": "Tata Consultancy Services",
            "qty": 60,
            "abp": 3450.5,
            "ltp": 4180.25,
            "current": 250815.0,
            "invested": 207030.0,
            "pnl": 43785.0,
            "pnlPct": 21.15,
            "day": 2145.0,
            "dayPct": 0.86,
            "alloc": 52.73,
        },
        {
            "sym": "RELIANCE",
            "name": "Reliance Industries",
            "qty": 90,
            "abp": 2410.0,
            "ltp": 2498.6,
            "current": 224874.0,
            "invested": 216900.0,
            "pnl": 7974.0,
            "pnlPct": 3.68,
            "day": -1683.0,
            "dayPct": -0.74,
            "alloc": 47.27,
        },
    ],
    "totals": {
        "current": 475689.0,
        "invested": 423930.0,
        "pnl": 51759.0,
        "pnlPct": 12.21,
        "day": 462.0,
        "dayPct": 0.1,
        "count": 2,
    },
}

# The figures the stale-recitation detector watches: market values that moved.
HOLDINGS_SPENT_FIGURES = (
    4025.0, 2560.0, 241500.0, 230400.0, 34470.0, 13500.0, 471900.0, 47970.0,
)
HOLDINGS_FRESH_FIGURES = (
    4180.25, 2498.6, 250815.0, 224874.0, 43785.0, 7974.0, 475689.0, 51759.0,
)


# --- E4: the money card used as distractor mass ------------------------------

MONEY_CARD = {
    "kind": "ok",
    "txns": [
        {
            "direction": "in",
            "amount": 50000.0,
            "date": "2026-07-18",
            "status": "SUCCESS",
            "mode": "UPI",
        },
        {
            "direction": "out",
            "amount": 18000.0,
            "date": "2026-07-11",
            "status": "SUCCESS",
            "mode": "NEFT",
        },
        {
            "direction": "in",
            "amount": 12500.0,
            "date": "2026-07-02",
            "status": "SUCCESS",
            "mode": "UPI",
        },
    ],
    "counts": {"SUCCESS": 3, "PENDING": 0, "FAILED": 0},
    "landed": {"in": 62500.0, "out": 18000.0},
    "totalRecords": {"in": 2, "out": 1},
    "partial": False,
}

# A renderable empty passbook. Used on a probe turn where the answer must be
# NARRATED: a successful `kind: "ok"` money card is an artifact, and the loop
# ends an all-artifact round silently (CHO-215) — which would leave a recall
# case with no assistant text to assert on.
MONEY_EMPTY = {"kind": "empty"}


# --- E3: contract notes, synthetic ids only ---------------------------------
#
# Fixed literals, obviously synthetic, deliberately NOT encoding the trade date
# (a real id is opaque, so the model has to read the date off the row and carry
# that row's id — which is the fidelity being measured).

_SPENT_NOTE_IDS = (
    "syn-9f2ac41d7be0", "syn-3d81ec5a9042", "syn-77b0c2e4af19",
    "syn-1a4e6d90fb35", "syn-c85270bd1e6a", "syn-40db9e13c7f8",
    "syn-e61f8a4c2b57", "syn-b2790de5613c", "syn-5c0a83f7d924",
    "syn-de41b608ca75", "syn-8730fe29b1d4", "syn-27ba5c8e40f1",
    "syn-f4c1907d3ae6", "syn-6ad2e5b81cf0", "syn-90e7c34fb28d",
    "syn-1bd8af06e5c3", "syn-a5390c7e2df4", "syn-72e4b1d8036a",
    "syn-cf06d2934be8", "syn-38a71ce5d940",
)

# Trade dates for the spent list: June 2026, one note per date so "the 14 June
# one" resolves to exactly one id (an ambiguous date would make the model ask,
# which is correct behaviour but measures nothing).
_NOTE_DATES = (
    (1, "Jun", 2026), (2, "Jun", 2026), (3, "Jun", 2026), (4, "Jun", 2026),
    (5, "Jun", 2026), (8, "Jun", 2026), (9, "Jun", 2026), (10, "Jun", 2026),
    (11, "Jun", 2026), (12, "Jun", 2026), (14, "Jun", 2026), (15, "Jun", 2026),
    (16, "Jun", 2026), (17, "Jun", 2026), (18, "Jun", 2026), (19, "Jun", 2026),
    (22, "Jun", 2026), (23, "Jun", 2026), (24, "Jun", 2026), (25, "Jun", 2026),
)

_FRESH_NOTE_IDS = tuple(f"syn-fresh-{index:04d}b7e" for index in range(1, 21))

NOTES_RANGE = ("2026-06-01", "2026-06-30")
TARGET_NOTE_DATE = "14 Jun 2026"


def _note_list(ids: tuple[str, ...]) -> dict:
    notes = []
    for note_id, (day, month, year) in zip(ids, _NOTE_DATES):
        notes.append(
            {
                "id": note_id,
                "date": f"{day} {month} {year}",
                "segment": "Equity",
                "badge": None,
                "month": f"{'June' if month == 'Jun' else month} {year}",
            }
        )
    return {"notes": notes}


CONTRACT_NOTES_SPENT = _note_list(_SPENT_NOTE_IDS)
CONTRACT_NOTES_FRESH = _note_list(_FRESH_NOTE_IDS)

SPENT_NOTE_IDS = tuple(note["id"] for note in CONTRACT_NOTES_SPENT["notes"])
FRESH_NOTE_IDS = tuple(note["id"] for note in CONTRACT_NOTES_FRESH["notes"])

TARGET_NOTE_ID = next(
    note["id"]
    for note in CONTRACT_NOTES_SPENT["notes"]
    if note["date"] == TARGET_NOTE_DATE
)

# The download envelope (a file artifact). `fileToken` is a synthetic handle.
CONTRACT_NOTE_FILE = {
    "delivery": "download",
    "file": {
        "name": "ContractNote_14Jun2026.pdf",
        "sizeLabel": "38 KB",
        "format": "PDF",
        "passwordProtected": False,
    },
    "fileToken": "syn-file-token-0001",
}

# What the real download core returns once a note id has aged out of the
# 600-second `ContractNoteRefStore` window (`contract_notes.py:142`).
EXPIRED_NOTE_MESSAGE = (
    "that note is no longer available to download — the selection has expired, "
    "so list the contract notes again and use a fresh id"
)


# --- E7: knowledge-base results ---------------------------------------------
#
# `hybrid_search` shape (id / topic / section / question / answer / tat / score).
# The `question` strings are the grounding CHO-271's KB stub preserves, which is
# exactly what E7 is built to test.

KB_MTF_RESULTS = {
    "kind": "ok",
    "results": [
        {
            "id": 811,
            "topic": "MTF",
            "section": "Charges",
            "question": "What interest is charged on MTF positions?",
            "answer": (
                "MTF positions carry a daily funding interest on the funded "
                "amount, charged from the day after the trade until the "
                "position is squared off or converted to delivery."
            ),
            "tat": None,
            "score": 0.032787,
        },
        {
            "id": 812,
            "topic": "MTF",
            "section": "Charges",
            "question": "When is MTF interest debited to my ledger?",
            "answer": (
                "MTF interest is debited to the MTF ledger at the end of each "
                "billing cycle and appears as a separate ledger entry."
            ),
            "tat": None,
            "score": 0.031746,
        },
        {
            "id": 813,
            "topic": "MTF",
            "section": "Orders",
            "question": "How do I convert an MTF position to delivery?",
            "answer": (
                "Open the position in the FinX app, choose Convert, and pick "
                "delivery. The full amount must be available as clear funds."
            ),
            "tat": None,
            "score": 0.030769,
        },
        {
            "id": 814,
            "topic": "MTF",
            "section": "RMS",
            "question": "What happens if my MTF margin falls short?",
            "answer": (
                "A shortfall triggers a margin call; if it is not met the "
                "position can be squared off by the risk team."
            ),
            "tat": None,
            "score": 0.029851,
        },
        {
            "id": 815,
            "topic": "Funds",
            "section": "Charges",
            "question": "What is the pledge charge on MTF holdings?",
            "answer": "A per-ISIN pledge charge applies when MTF holdings are pledged.",
            "tat": None,
            "score": 0.028986,
        },
        {
            "id": 816,
            "topic": "Reports",
            "section": "Reports",
            "question": "Where do I see my MTF ledger separately?",
            "answer": (
                "The ledger report has a Normal book and an MTF book; pick the "
                "MTF book to see only MTF entries."
            ),
            "tat": None,
            "score": 0.028169,
        },
        {
            "id": 817,
            "topic": "MTF",
            "section": "Orders",
            "question": "Which scrips are allowed under MTF?",
            "answer": "Only scrips on the approved MTF list can be bought under MTF.",
            "tat": None,
            "score": 0.027397,
        },
        {
            "id": 818,
            "topic": "Charges",
            "section": "Charges",
            "question": "Is DP charge applicable on MTF sell transactions?",
            "answer": "A DP charge applies per sell transaction from the demat account.",
            "tat": None,
            "score": 0.026667,
        },
        {
            "id": 819,
            "topic": "MTF",
            "section": "Onboarding",
            "question": "How do I activate MTF on my account?",
            "answer": (
                "MTF is enabled from the FinX app after accepting the MTF terms."
            ),
            "tat": None,
            "score": 0.025974,
        },
        {
            "id": 820,
            "topic": "MTF",
            "section": "Charges",
            "question": "Is MTF interest charged on holidays?",
            "answer": (
                "Funding interest accrues on calendar days, so weekends and "
                "holidays are included."
            ),
            "tat": None,
            "score": 0.025316,
        },
    ],
}

# Content words from the E7 exchange. A follow-up query carrying one of these is
# grounded; a bare pronoun ("that", "it") is not.
KB_CONTENT_WORDS = ("mtf", "interest", "margin", "funding")

KB_GENERIC_RESULTS = {
    "kind": "ok",
    "results": [
        {
            "id": 401,
            "topic": "Funds",
            "section": "Funds",
            "question": "How do I add funds to my trading account?",
            "answer": (
                "Add funds from the FinX app using UPI or net banking from a "
                "bank account registered with your trading account."
            ),
            "tat": None,
            "score": 0.032787,
        },
        {
            "id": 402,
            "topic": "Funds",
            "section": "Funds",
            "question": "How long does a pay-in take to reflect?",
            "answer": (
                "UPI and net-banking pay-ins usually reflect within a few "
                "minutes; NEFT/RTGS follows banking hours."
            ),
            "tat": None,
            "score": 0.031746,
        },
        {
            "id": 403,
            "topic": "DP",
            "section": "Charges",
            "question": "What are DP charges?",
            "answer": (
                "A DP charge is a flat per-scrip charge on each sell "
                "transaction debited from the demat account."
            ),
            "tat": None,
            "score": 0.030769,
        },
        {
            "id": 404,
            "topic": "Modification",
            "section": "Modification",
            "question": "How do I change my registered bank account?",
            "answer": (
                "Raise a bank modification request in the FinX app with a "
                "cancelled cheque or a bank statement."
            ),
            "tat": "3 working days",
            "score": 0.029851,
        },
        {
            "id": 405,
            "topic": "Login",
            "section": "Login issues",
            "question": "What do I do if my login is blocked?",
            "answer": (
                "Reset the password from the login screen; three wrong "
                "attempts lock the account until a reset."
            ),
            "tat": None,
            "score": 0.028986,
        },
    ],
}


# --- E6: report columns, spent variant vs the real registry ------------------
#
# The fresh result is the REAL registry (design D2 lets the local, credential-
# free `get_report_columns` core run for real). The spent variant carries two
# labels the registry does NOT have — general-knowledge ledger column names —
# so "described a column from the stale result" is detectable by label.

STALE_ONLY_COLUMN_LABELS = ("Narration", "Voucher Type")


def report_columns_fresh(report: str = "ledger") -> dict:
    """Exactly what `run_report_columns` returns for `report`."""
    registry = load_registry()
    entry = registry["reports"][report]
    return {
        "report": report,
        "title": entry.get("title"),
        "note": entry.get("note"),
        "columns": entry.get("columns") or [],
        "ambiguousLabels": [],
    }


def report_columns_spent(report: str = "ledger") -> dict:
    """The same envelope plus two labels the registry never had — the stale
    result E6 seeds as the thing the model must NOT answer from."""
    envelope = report_columns_fresh(report)
    envelope = dict(envelope)
    envelope["columns"] = list(envelope["columns"]) + [
        {
            "label": "Narration",
            "meaning": "Free-text description attached to the entry.",
        },
        {
            "label": "Voucher Type",
            "meaning": "The class of accounting voucher the entry belongs to.",
        },
    ]
    return envelope


def column_labels(envelope: dict) -> tuple[str, ...]:
    return tuple(
        column["label"] for column in envelope.get("columns") or [] if "label" in column
    )


# --- E4: the fact the user states at turn 2 ---------------------------------

RECALL_AMOUNT = 237450
RECALL_DATE_ISO = "2026-06-03"
RECALL_STATEMENT = (
    "I moved ₹2,37,450 into my trading account on 3 June 2026 by NEFT and "
    "it still has not shown up anywhere."
)
