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
