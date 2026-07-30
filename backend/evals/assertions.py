"""Shared eval assertions (CHO-276 · design D5).

Everything a case checks lives here, so a behavioural contract is reviewable in
one place instead of being re-typed per case. Two groups:

* **The no-abstention family** — `ABSTENTION_PATTERNS` plus
  :func:`abstention_match`. Applied to EVERY case (the harness funnels every
  outcome through `harness.finish`, which always runs it), because Claude's
  documented long-context failure is abstention: replying "I cannot determine…
  that was not provided" about a fact that IS in the transcript. A case that
  "passes" its routing check while declining to answer has reproduced the exact
  bug this programme exists to fix.

* **Mechanical routing checks** — first tool call, tool-input fields,
  contract-note id fidelity, and the stale-value detector ("no figure /
  no label from the spent envelope that is absent from the fresh one").
  The stale detector is why the fixtures carry two variants of the holdings and
  report-column envelopes with deliberately different values: reciting from a
  spent tool_result becomes detectable by VALUE, not by judgement.

PII: matchers return the NAME of the pattern they matched (our own constant),
never the model's words — so a report can say *what* failed without carrying
assistant text.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# --- the no-abstention family (design D5) ------------------------------------
#
# ONE definition, reused by every case. Each entry is (name, regex): the name is
# what a report records, the regex is the phrasing family. Deliberately narrow —
# the prompt's own allowed miss-phrasings ("That isn't covered in our support
# guides", "I can't pull that for your account") must NOT match, because those
# are correct behaviour when a lookup genuinely returns nothing. What matches
# here is the model disclaiming knowledge of something the seeded thread holds.

ABSTENTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("cannot-determine", r"\b(?:cannot|can'?t|could ?n'?t|unable to)\s+determine\b"),
    ("cannot-tell-from", r"\b(?:cannot|can'?t)\s+tell\b[^.?!]{0,30}\bfrom\s+(?:the|our|this)\s+(?:chat|conversation|history|messages)"),
    ("not-provided-in-history", r"\bnot\s+(?:been\s+)?(?:provided|shared|given|mentioned|specified)\b[^.?!]{0,40}\b(?:chat|conversation|history|thread)\b"),
    ("wasnt-provided", r"\b(?:was|were|is|are|has|have)\s*n'?(?:o)?t\s+(?:been\s+)?(?:provided|shared|specified)\b"),
    ("no-access-to", r"\b(?:do\s*n'?o?t|does\s*n'?o?t|no)\s+(?:have\s+)?access\s+to\b"),
    ("not-available-in-conversation", r"\bnot\s+available\b[^.?!]{0,30}\b(?:chat|conversation|history)\b"),
    ("dont-have-that-information", r"\bdo\s*n'?o?t\s+have\s+(?:that|the|this|any)\s+(?:information|detail|details|data)\b"),
    ("not-in-conversation-history", r"\bnot\s+in\s+(?:the|our|this)\s+(?:chat|conversation)\s*(?:history)?\b"),
    ("user-never-said", r"\byou\s+(?:have\s*n'?o?t|did\s*n'?o?t|never)\s+(?:told|tell|mention|mentioned|give|gave|provide|provided|share|shared)\b"),
    ("i-wasnt-given", r"\bI\s+(?:was\s*n'?o?t|have\s*n'?o?t\s+been)\s+(?:given|provided|told)\b"),
    ("no-record-in-conversation", r"\bno\s+record\b[^.?!]{0,30}\b(?:chat|conversation|history)\b"),
)

_ABSTENTION_RES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.I)) for name, pattern in ABSTENTION_PATTERNS
)


def abstention_match(text: str | None) -> str | None:
    """The NAME of the first abstention family the text matches, else None.

    Never returns the matched text: a report records `abstention:no-access-to`,
    not the assistant's sentence.
    """
    if not text:
        return None
    for name, regex in _ABSTENTION_RES:
        if regex.search(text):
            return name
    return None


# --- tool-call shape ---------------------------------------------------------


def first_tool_call(calls: list[tuple[str, dict]]) -> str | None:
    """Name of the first tool the probe turn asked for, or None if it called
    nothing. Routing is judged on the FIRST decision, not on the set."""
    return calls[0][0] if calls else None


def tool_names(calls: list[tuple[str, dict]]) -> list[str]:
    return [name for name, _ in calls]


def inputs_for(calls: list[tuple[str, dict]], name: str) -> list[dict]:
    """Every recorded input for one tool, in call order."""
    return [dict(payload) for called, payload in calls if called == name]


def field_mismatches(payload: dict, expected: dict) -> list[str]:
    """Field names in `expected` whose value the tool input did not carry.
    Returned as names only — the report keeps the observed values separately."""
    missing = []
    for field, value in expected.items():
        if payload.get(field) != value:
            missing.append(field)
    return missing


# --- contract-note id fidelity ----------------------------------------------


def emitted_ids(calls: list[tuple[str, dict]], name: str, field: str = "id") -> list[str]:
    return [
        str(payload.get(field))
        for payload in inputs_for(calls, name)
        if payload.get(field) is not None
    ]


def invented_ids(
    calls: list[tuple[str, dict]],
    name: str,
    allowed: Iterable[str],
    field: str = "id",
) -> list[str]:
    """Ids the model emitted that were never returned to it. Fabricating a
    capability token is the failure; picking the wrong one is a different (and
    much less dangerous) thing, so the two are reported separately."""
    allowed_set = set(allowed)
    return [value for value in emitted_ids(calls, name, field) if value not in allowed_set]


# --- the stale-value detector ------------------------------------------------
#
# "No figure from the spent envelope that is absent from the fresh one." A value
# the fresh result also carries is not evidence of anything (the model may have
# read it there), so it is excluded by construction — which is exactly why the
# fixtures give the seeded and fresh envelopes deliberately distinct numbers.

_DIGIT_SEPARATOR = re.compile("(?<=\\d)[,\\u0020\\u00a0\\u2009\\u202f](?=\\d)")


def _normalize_digits(text: str) -> str:
    """Drop thousands separators between digits so "4,81,500", "481,500" and
    "481500" all compare equal (Indian and Western grouping both)."""
    return _DIGIT_SEPARATOR.sub("", text)


def _number_token(value: Any) -> str:
    """A number as the digit run a reply would show: 481500.0 -> "481500",
    512350.25 -> "512350.25" (the fractional part is kept when meaningful)."""
    if isinstance(value, bool):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def stale_figures(
    text: str | None, *, seeded: Iterable[Any], fresh: Iterable[Any]
) -> list[str]:
    """Figures from the spent envelope, absent from the fresh one, that the
    reply nonetheless quotes. Non-empty ⇒ the model recited from memory."""
    if not text:
        return []
    haystack = _normalize_digits(text)
    fresh_tokens = {_number_token(value) for value in fresh}
    hits: list[str] = []
    for value in seeded:
        token = _number_token(value)
        if not token or token in fresh_tokens:
            continue
        if token in haystack and token not in hits:
            hits.append(token)
    return hits


def stale_labels(
    text: str | None, *, seeded: Iterable[str], fresh: Iterable[str]
) -> list[str]:
    """The label twin of :func:`stale_figures` — a column label the spent
    result carried and the fresh one does not must not appear in the reply."""
    if not text:
        return []
    haystack = text.lower()
    fresh_lower = {label.lower() for label in fresh}
    hits: list[str] = []
    for label in seeded:
        low = label.lower()
        if low in fresh_lower:
            continue
        if low in haystack and label not in hits:
            hits.append(label)
    return hits


# --- prose that should not have happened -------------------------------------

# Report parameters the FORM RULE forbids asking for in text (prompt.py:198+).
_PARAMETER_PHRASES = (
    "date range",
    "which dates",
    "what dates",
    "from date",
    "to date",
    "start date",
    "end date",
    "which book",
    "normal or mtf",
    "which segment",
    "equity, f&o",
    "delivery",
    "download or email",
    "which format",
    "pdf or excel",
    "financial year",
    "which fy",
)


def parameter_question(text: str | None) -> str | None:
    """The report-parameter phrase a text question asked for, or None. E1 fails
    when one of these precedes the `open_report_form` call — asking for report
    parameters in prose is the behaviour the form handover replaced."""
    if not text or "?" not in text:
        return None
    low = text.lower()
    for phrase in _PARAMETER_PHRASES:
        if phrase in low:
            return phrase
    return None


def preamble_before_tool(text: str | None) -> str | None:
    """Any assistant text emitted before the first tool call, as a SIZE marker
    ("142-chars"), or None when the call was silent (CHO-284).

    Categorical on purpose. `parameter_question` above asks *which forbidden
    phrase* preceded the call; this asks whether ANYTHING did. The live failure
    this exists for was a fluent, entirely true sentence — not a banned phrase —
    which the user reads as a finished answer just before a loading indicator
    appears under it. So the check cannot be a phrase list; it is emptiness.

    Returns the length, never the words, keeping the same PII discipline as the
    rest of this module: a report records `preamble-before-tool:142-chars`.
    """
    stripped = (text or "").strip()
    return f"{len(stripped)}-chars" if stripped else None


# --- exact-recall matchers (E4) ----------------------------------------------

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def contains_amount(text: str | None, amount: int) -> bool:
    """True when the reply quotes the amount, in any common grouping."""
    if not text:
        return False
    return str(amount) in _normalize_digits(text)


def date_forms(iso_date: str) -> list[str]:
    """The renderings of a date a reply might legitimately use."""
    year, month, day = (int(part) for part in iso_date.split("-"))
    long_month = _MONTHS[month - 1]
    short_month = long_month[:3]
    forms = [
        iso_date,
        f"{day} {long_month} {year}",
        f"{day} {short_month} {year}",
        f"{day:02d} {long_month} {year}",
        f"{day:02d} {short_month} {year}",
        f"{long_month} {day}, {year}",
        f"{long_month} {day} {year}",
        f"{short_month} {day}, {year}",
        f"{day}/{month}/{year}",
        f"{day:02d}/{month:02d}/{year}",
    ]
    for suffix in ("st", "nd", "rd", "th"):
        forms.append(f"{day}{suffix} {long_month} {year}")
        forms.append(f"{day}{suffix} {short_month} {year}")
    return forms


def contains_date(text: str | None, iso_date: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(form.lower() in low for form in date_forms(iso_date))


def contains_any(text: str | None, needles: Iterable[str]) -> str | None:
    """The first needle present in the text (case-insensitive), else None."""
    if not text:
        return None
    low = text.lower()
    for needle in needles:
        if needle.lower() in low:
            return needle
    return None
