"""Backend configuration.

Values are read from the environment at call time so tests and local runs can
override them without re-importing modules.
"""

import os

UPSTREAM_PROFILE_URL_DEFAULT = (
    "https://mf.choiceindia.com/api/v2/investor/profile/extended"
)


def upstream_profile_url() -> str:
    """Upstream Get Profile endpoint (override with UPSTREAM_PROFILE_URL)."""
    return os.environ.get("UPSTREAM_PROFILE_URL", UPSTREAM_PROFILE_URL_DEFAULT)


def upstream_timeout_seconds() -> float:
    """Timeout for upstream calls (override with UPSTREAM_TIMEOUT_SECONDS)."""
    return float(os.environ.get("UPSTREAM_TIMEOUT_SECONDS", "10"))


# --- FinX report backends ---------------------------------------------------
#
# The report APIs live on two hosts (see docs/finx_android_api_reference.html):
#   - the .NET/Go middleware pair  -> api.choiceindia.com   (SessionId auth)
#   - the MIS/CML reports backend  -> finx.choiceindia.com  (SSO JWT auth)
# Every URL is env-overridable so tests can point the client at a mock and so
# hosts can change without a code release.

UPSTREAM_FINX_MIDDLEWARE_BASE_DEFAULT = "https://api.choiceindia.com"
UPSTREAM_MIS_BASE_DEFAULT = "https://finx.choiceindia.com"

# `from:` is a client build tag — NOT auth and NOT a source router (live-tested:
# the same session returns 200 with any tag or none). Any stable value works.
FINX_FROM_HEADER_DEFAULT = "web_choicejini_1.0"


def _finx_middleware_base() -> str:
    return os.environ.get(
        "UPSTREAM_FINX_MIDDLEWARE_BASE", UPSTREAM_FINX_MIDDLEWARE_BASE_DEFAULT
    )


def _mis_base() -> str:
    return os.environ.get("UPSTREAM_MIS_BASE", UPSTREAM_MIS_BASE_DEFAULT)


def finx_from_header() -> str:
    """The non-authenticating `from:` build tag (override with FINX_FROM_HEADER)."""
    return os.environ.get("FINX_FROM_HEADER", FINX_FROM_HEADER_DEFAULT)


def upstream_pnl_url() -> str:
    """GetGlobalPNLPDF endpoint (override with UPSTREAM_PNL_URL)."""
    return os.environ.get(
        "UPSTREAM_PNL_URL",
        f"{_finx_middleware_base()}/api/middleware/GetGlobalPNLPDF",
    )


def upstream_ledger_url() -> str:
    """GetLedgerDetailsPDF endpoint (override with UPSTREAM_LEDGER_URL). Wave 1."""
    return os.environ.get(
        "UPSTREAM_LEDGER_URL",
        f"{_finx_middleware_base()}/api/middleware/GetLedgerDetailsPDF",
    )


def upstream_tax_url() -> str:
    """GetTaxReportPDF endpoint (override with UPSTREAM_TAX_URL). Wave 1."""
    return os.environ.get(
        "UPSTREAM_TAX_URL",
        f"{_finx_middleware_base()}/api/middleware/GetTaxReportPDF",
    )


def upstream_cml_url() -> str:
    """MIS /mis/reports/generate endpoint (override with UPSTREAM_CML_URL). Wave 1."""
    return os.environ.get(
        "UPSTREAM_CML_URL", f"{_mis_base()}/mis/reports/generate"
    )


def report_file_ttl_seconds() -> float:
    """TTL for a generated-report download token (override REPORT_FILE_TTL_SECONDS)."""
    return float(os.environ.get("REPORT_FILE_TTL_SECONDS", "300"))


# --- FinX data backends (CHO-211 data-card flows) ---------------------------
#
# Three more upstream families, each with its own credential scheme (see
# openspec/changes/cho-211-data-card-flows/design.md, live-verified 2026-07-18):
#   - Holdings          -> finxomne.choiceindia.com  (authorization: "Session <SessionId>")
#   - Pay-In / Pay-Out  -> finx.choiceindia.com      (bare SessionId; same host as
#                          the MIS backend but a different auth scheme)
#   - Brokerage slab    -> api.choiceindia.com       (raw SSO JWT)

UPSTREAM_FINXOMNE_BASE_DEFAULT = "https://finxomne.choiceindia.com"


def _finxomne_base() -> str:
    return os.environ.get(
        "UPSTREAM_FINXOMNE_BASE", UPSTREAM_FINXOMNE_BASE_DEFAULT
    )


def upstream_holdings_url() -> str:
    """COTI Holdings endpoint (override with UPSTREAM_HOLDINGS_URL)."""
    return os.environ.get(
        "UPSTREAM_HOLDINGS_URL", f"{_finxomne_base()}/COTI/V1/Holdings"
    )


def upstream_payin_url() -> str:
    """GetPayInTxnRpt endpoint (override with UPSTREAM_PAYIN_URL)."""
    return os.environ.get(
        "UPSTREAM_PAYIN_URL", f"{_mis_base()}/api/middleware/GetPayInTxnRpt"
    )


def upstream_payout_url() -> str:
    """GetPayOutTxnRpt endpoint (override with UPSTREAM_PAYOUT_URL)."""
    return os.environ.get(
        "UPSTREAM_PAYOUT_URL", f"{_mis_base()}/api/middleware/GetPayOutTxnRpt"
    )


def upstream_brokerage_url() -> str:
    """Brokerage slab endpoint (override with UPSTREAM_BROKERAGE_URL)."""
    return os.environ.get(
        "UPSTREAM_BROKERAGE_URL",
        f"{_finx_middleware_base()}/middleware-go/v2/get-brokerage-slab",
    )
