"""Boundary normalization + PII masking for the FinX data endpoints (CHO-211).

Upstream inconsistencies are normalized ONCE, here, server-side — the frontend
never sees them (design: "Normalization layer"):

  - Units: Holdings `LTP`/`CP` arrive in paise (÷100); `ABP` is already rupees
    (confirmed against FinX's own CSV export in docs/prototype/samples/).
  - Status casing: `SUCCESS` (pay-in) vs `Success`/`Failure`/`CANCELLED`
    (pay-out) → one canonical enum, matched case-insensitively.
  - Dates: three upstream formats → ISO 8601 (seconds precision)
      pay-in    "2026-07-08T16:19:45.29"  (ISO-T, stray fraction)
      pay-out   "2026-06-10 21:01:13"     (space-separated)
      holdings  "17-07-2026 15:59:40"     (DD-MM-YYYY LUT)
  - Empty sentinels: `""` (pay-out) and `"1900-01-01T00:00:00"` (pay-in)
    → None.

Masking (the PII forwarding whitelist contract): bank destinations leave the
backend only as "<bank word> ••<last-4>" — a full account number never does.
"""

import datetime
import re

# Canonical transaction statuses (display-only downstream — never branched on).
STATUS_SUCCESS = "SUCCESS"
STATUS_PENDING = "PENDING"
STATUS_FAILURE = "FAILURE"
STATUS_CANCELLED = "CANCELLED"

_STATUS_CANONICAL = {
    "success": STATUS_SUCCESS,
    "pending": STATUS_PENDING,
    "failure": STATUS_FAILURE,
    "failed": STATUS_FAILURE,
    "cancelled": STATUS_CANCELLED,
    "canceled": STATUS_CANCELLED,
}

# Holdings LUT: "17-07-2026 15:59:40" (DD-MM-YYYY, day-first).
_DDMMYYYY_RE = re.compile(
    r"^(\d{2})-(\d{2})-(\d{4})[ T](\d{2}):(\d{2}):(\d{2})$"
)

# Pay-in's "no value yet" sentinel, e.g. AccountsDateTime on a pending txn.
_SENTINEL_PREFIX = "1900-01-01"


def paise_to_rupees(value: object) -> float | None:
    """Holdings LTP/CP arrive in paise: 11579 → 115.79 (ABP is NOT paise)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value / 100, 2)


def normalize_status(value: object) -> str | None:
    """Case-insensitive status → canonical SUCCESS|PENDING|FAILURE|CANCELLED.

    An unrecognized (but non-empty) status passes through uppercased —
    display-only, never a branch input.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return _STATUS_CANONICAL.get(stripped.lower(), stripped.upper())


def parse_upstream_datetime(value: object) -> datetime.datetime | None:
    """Parse any of the three upstream date formats; sentinels → None."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.startswith(_SENTINEL_PREFIX):
        return None
    match = _DDMMYYYY_RE.match(stripped)
    if match:
        day, month, year, hh, mm, ss = (int(g) for g in match.groups())
        try:
            return datetime.datetime(year, month, day, hh, mm, ss)
        except ValueError:
            return None
    try:
        # Python ≥3.11 fromisoformat accepts both "T" and space separators and
        # the truncated fraction pay-in emits ("…T16:19:45.29").
        return datetime.datetime.fromisoformat(stripped)
    except ValueError:
        return None


def to_iso(value: object) -> str | None:
    """Any upstream date format → ISO 8601 (seconds precision), or None."""
    parsed = parse_upstream_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat(timespec="seconds")


def blank_to_none(value: object) -> str | None:
    """The pay-in/out "" empty-sentinel → None; non-strings never pass."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _last4(value: object) -> str | None:
    """Last four digits of the longest-suffix digit run in a string."""
    if not isinstance(value, str):
        return None
    runs = re.findall(r"\d{4,}", value)
    if not runs:
        return None
    return runs[-1][-4:]


def mask_payin_destination(deposit_bank_name: object) -> str | None:
    """Pay-in destination from `DepositBankName`, masked to bank word + last-4.

    "ICICI NSE CLIENT A/C - 000405107280" → "ICICI ••7280". The full account
    number MUST never survive this function.
    """
    if not isinstance(deposit_bank_name, str):
        return None
    stripped = deposit_bank_name.strip()
    if not stripped:
        return None
    bank_word = stripped.split()[0]
    last4 = _last4(stripped)
    if last4 is None:
        return bank_word
    return f"{bank_word} ••{last4}"


def mask_payout_destination(
    client_bank_name: object, client_bank_acc_no: object
) -> str | None:
    """Pay-out destination: `ClientBankName` (or "Bank") + acc-no last-4.

    ("", "50100218008829") → "Bank ••8829". The full account number MUST
    never survive this function.
    """
    name = blank_to_none(client_bank_name)
    last4 = _last4(client_bank_acc_no)
    if last4 is None:
        return name
    return f"{name or 'Bank'} ••{last4}"
