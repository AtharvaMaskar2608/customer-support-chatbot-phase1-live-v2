"""Unit tests for the CHO-211 boundary normalizers and PII maskers
(app.data.normalize) — every upstream inconsistency in one place."""

import pytest

from app.data.normalize import (
    blank_to_none,
    mask_payin_destination,
    mask_payout_destination,
    normalize_status,
    paise_to_rupees,
    to_iso,
)


# --- paise → rupees ---------------------------------------------------------

def test_paise_decode_matches_finx_csv_export():
    # GOLDBEES LTP 11579 paise → ₹115.79, the value in FinX's own CSV
    # (docs/prototype/samples/X008593_Holding_Overall_Report_*.csv).
    assert paise_to_rupees(11579) == 115.79


def test_paise_decode_handles_ints_and_floats():
    assert paise_to_rupees(24680) == 246.80
    assert paise_to_rupees(24830.0) == 248.30
    assert paise_to_rupees(0) == 0.0


def test_paise_decode_rejects_non_numbers():
    assert paise_to_rupees("11579") is None
    assert paise_to_rupees(None) is None
    assert paise_to_rupees(True) is None  # bool is not a price


# --- status casing ----------------------------------------------------------

@pytest.mark.parametrize(
    "raw,canonical",
    [
        ("SUCCESS", "SUCCESS"),  # pay-in casing
        ("Success", "SUCCESS"),  # pay-out casing
        ("success", "SUCCESS"),
        ("PENDING", "PENDING"),
        ("Pending", "PENDING"),
        ("Failure", "FAILURE"),  # pay-out casing
        ("FAILED", "FAILURE"),
        ("failed", "FAILURE"),
        ("CANCELLED", "CANCELLED"),  # pay-out casing
        ("cancelled", "CANCELLED"),
    ],
)
def test_status_matched_case_insensitively(raw, canonical):
    assert normalize_status(raw) == canonical


def test_status_empty_or_non_string_is_none():
    assert normalize_status("") is None
    assert normalize_status("   ") is None
    assert normalize_status(None) is None
    assert normalize_status(7) is None


# --- dates → ISO 8601 -------------------------------------------------------

def test_payin_iso_t_format_with_stray_fraction():
    assert to_iso("2026-07-08T16:19:45.29") == "2026-07-08T16:19:45"


def test_payout_space_separated_format():
    assert to_iso("2026-06-10 21:01:13") == "2026-06-10T21:01:13"


def test_holdings_lut_is_day_first():
    # DD-MM-YYYY: 17-07 is 17 July, not month 17.
    assert to_iso("17-07-2026 15:59:40") == "2026-07-17T15:59:40"


def test_empty_sentinels_become_none():
    assert to_iso("") is None  # pay-out sentinel
    assert to_iso("1900-01-01T00:00:00") is None  # pay-in sentinel
    assert to_iso(None) is None


def test_unparseable_date_is_none_not_garbage():
    assert to_iso("not a date") is None


def test_blank_to_none():
    assert blank_to_none("") is None
    assert blank_to_none("  ") is None
    assert blank_to_none("UPI") == "UPI"
    assert blank_to_none(None) is None
    assert blank_to_none(42) is None


# --- PII maskers ------------------------------------------------------------

def test_payin_destination_masks_to_bank_word_plus_last4():
    masked = mask_payin_destination("ICICI NSE CLIENT A/C - 000405107280")
    assert masked == "ICICI ••7280"
    # The full account number must never survive the mask.
    assert "000405107280" not in masked


def test_payin_destination_without_account_number_keeps_bank_word():
    assert mask_payin_destination("ICICI") == "ICICI"


def test_payin_destination_empty_is_none():
    assert mask_payin_destination("") is None
    assert mask_payin_destination(None) is None


def test_payout_destination_masks_with_bank_fallback():
    masked = mask_payout_destination("", "50100218008829")
    assert masked == "Bank ••8829"
    assert "50100218008829" not in masked


def test_payout_destination_uses_bank_name_when_present():
    assert mask_payout_destination("HDFC", "50100218008829") == "HDFC ••8829"


def test_payout_destination_empty_is_none():
    assert mask_payout_destination("", "") is None
    assert mask_payout_destination(None, None) is None
