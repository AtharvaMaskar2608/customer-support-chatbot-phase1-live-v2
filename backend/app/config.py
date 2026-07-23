"""Backend configuration.

Values are read from the environment at call time so tests and local runs can
override them without re-importing modules.
"""

import os
import re
from urllib.parse import quote

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


# --- KB retrieval (CHO-212) -------------------------------------------------
#
# The knowledge base lives in Postgres (dev: SSH tunnel on localhost:5433).
# DATABASE_URL and OPENAI_API_KEY are secrets: read from the environment, with
# a dev-convenience fallback to the untracked repo-root .env so `uv run
# uvicorn` works without exporting. Values are never logged.

_ROOT_ENV = os.path.join(os.path.dirname(__file__), "..", "..", ".env")


def _root_env_value(key: str) -> str | None:
    """Minimal .env reader. Tolerates the formats found in the wild in this
    repo's .env: `KEY=v`, `KEY = "v"` (spaces), and `export KEY="v"`."""
    pattern = re.compile(rf"^(?:export\s+)?{re.escape(key)}\s*=\s*(.*)$")
    try:
        with open(_ROOT_ENV, encoding="utf-8") as fh:
            for line in fh:
                match = pattern.match(line.strip())
                if match:
                    return match.group(1).strip().strip("'\"") or None
    except OSError:
        return None
    return None


def _secret(key: str) -> str | None:
    return os.environ.get(key) or _root_env_value(key)


def _normalize_dsn(dsn: str) -> str:
    """Percent-encode the DSN's userinfo so asyncpg's urlparse-based DSN
    parser accepts passwords with special characters (a raw '[' reads as IPv6
    syntax and raises). psql accepts both forms, so normalizing is safe.
    Already-encoded userinfo (contains '%') is left untouched."""
    if "://" not in dsn or "@" not in dsn:
        return dsn
    scheme, rest = dsn.split("://", 1)
    auth, hostpart = rest.rsplit("@", 1)
    if "%" in auth:
        return dsn
    if ":" in auth:
        user, password = auth.split(":", 1)
        auth = f"{quote(user, safe='')}:{quote(password, safe='')}"
    else:
        auth = quote(auth, safe="")
    return f"{scheme}://{auth}@{hostpart}"


def database_url() -> str | None:
    """Postgres DSN for the KB (env DATABASE_URL, or repo-root .env in dev)."""
    dsn = _secret("DATABASE_URL")
    return _normalize_dsn(dsn) if dsn else None


def openai_api_key() -> str | None:
    """OpenAI key for query embeddings (env, or repo-root .env in dev)."""
    return _secret("OPENAI_API_KEY")


def kb_embed_model() -> str:
    """Embedding model — MUST match the corpus embeddings (3072-d)."""
    return os.environ.get("KB_EMBED_MODEL", "text-embedding-3-large")


# --- Freshdesk escalation (CHO-218) ------------------------------------------
#
# Ticket creation credentials + routing. The API key is a secret (env, or
# repo-root .env in dev — never logged, never in tool schemas); the API root
# and group id are env-overridable so switching to a production group later
# is a config change, not code. All read at call time.

FRESHDESK_GROUP_ID_DEFAULT = 22000168676  # the chatbot-testing group


def freshdesk_api_root() -> str | None:
    """Freshdesk API v2 root: FRESHDESK_API_ROOT, else built from
    FRESHDESK_DOMAIN as https://{domain}.freshdesk.com/api/v2. None when
    neither is configured (ticketing then degrades to UPSTREAM_ERROR)."""
    root = _secret("FRESHDESK_API_ROOT")
    if root:
        return root.rstrip("/")
    domain = _secret("FRESHDESK_DOMAIN")
    return f"https://{domain}.freshdesk.com/api/v2" if domain else None


def freshdesk_api_key() -> str | None:
    """Freshdesk API key (env, or repo-root .env in dev). Never logged."""
    return _secret("FRESHDESK_API_KEY")


def freshdesk_group_id() -> int:
    """Freshdesk group id for bot tickets (FRESHDESK_GROUP_ID env override;
    the default is the chatbot-testing group per design D1)."""
    return int(
        os.environ.get("FRESHDESK_GROUP_ID", str(FRESHDESK_GROUP_ID_DEFAULT))
    )


# --- Agent loop (CHO-213) ----------------------------------------------------
#
# Model + thinking are two env knobs (design D10). The thinking request-param
# mapping is per-model and lives HERE so the loop code stays model-agnostic:
# the two supported models straddle the thinking-API generation change
# (Haiku 4.5 still takes budget_tokens; Sonnet 4.6 deprecates it in favour of
# adaptive + effort), so "minimal" cannot be one literal.

AGENT_MODEL_DEFAULT = "claude-haiku-4-5"
AGENT_MODELS = ("claude-haiku-4-5", "claude-sonnet-4-6")
AGENT_THINKING_MODES = ("off", "minimal")

# API minimum for budget_tokens; must stay < agent_max_tokens().
_HAIKU_THINKING_BUDGET = 1024


def agent_model() -> str:
    """Loop model (AGENT_MODEL env; unknown values fall back to the default)."""
    model = os.environ.get("AGENT_MODEL", AGENT_MODEL_DEFAULT)
    return model if model in AGENT_MODELS else AGENT_MODEL_DEFAULT


def agent_thinking() -> str:
    """Thinking mode (AGENT_THINKING env): "off" (default) or "minimal"."""
    mode = os.environ.get("AGENT_THINKING", "off")
    return mode if mode in AGENT_THINKING_MODES else "off"


def agent_thinking_params(model: str, mode: str) -> dict:
    """Per-model request kwargs for the chosen thinking mode (design D10).

    off               -> {} (omit `thinking` on both models)
    minimal + haiku   -> {"thinking": {"type": "enabled", "budget_tokens": 1024}}
                         (1024 = API minimum; must be < max_tokens)
    minimal + sonnet  -> {"thinking": {"type": "adaptive"},
                          "output_config": {"effort": "low"}}
                         (budget_tokens is deprecated on 4.6; effort is
                          unsupported on Haiku)
    No other thinking configuration is ever sent.
    """
    if mode != "minimal":
        return {}
    if model == "claude-sonnet-4-6":
        return {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "low"},
        }
    return {
        "thinking": {"type": "enabled", "budget_tokens": _HAIKU_THINKING_BUDGET}
    }


def agent_max_tokens() -> int:
    """max_tokens per model call (AGENT_MAX_TOKENS env). The default (4096)
    exceeds the Haiku minimal-thinking budget (1024), as the API requires."""
    return int(os.environ.get("AGENT_MAX_TOKENS", "4096"))


def clarify_cap() -> int:
    """Max clarifying questions per task window (CLARIFY_CAP env)."""
    return int(os.environ.get("CLARIFY_CAP", "2"))


def task_turn_cap() -> int:
    """Max user turns per task window (TASK_TURN_CAP env)."""
    return int(os.environ.get("TASK_TURN_CAP", "100"))


def session_turn_cap() -> int:
    """Max user turns per session — the dumb backstop (SESSION_TURN_CAP env)."""
    return int(os.environ.get("SESSION_TURN_CAP", "100"))


def agent_max_tool_rounds() -> int:
    """Inner guard: tool rounds per user message (AGENT_MAX_TOOL_ROUNDS env)."""
    return int(os.environ.get("AGENT_MAX_TOOL_ROUNDS", "5"))


def anthropic_api_key() -> str | None:
    """Anthropic key for the agent loop (env, or repo-root .env in dev)."""
    return _secret("ANTHROPIC_API_KEY")


# --- DeepEval tracing (CHO-244) ----------------------------------------------
#
# Observability is config-gated: with no CONFIDENT_API_KEY (and no explicit
# DEEPEVAL_TRACING) tracing is entirely off — the observe wrappers pass through.
# The key is a secret (env, or repo-root .env in dev; never logged). Environment
# and sampling rate are plain env knobs.


def confident_api_key() -> str | None:
    """Confident AI key for exporting DeepEval traces (env, or repo-root .env).
    None ⇒ tracing stays off. Never logged."""
    return _secret("CONFIDENT_API_KEY")


def deepeval_env() -> str:
    """Trace environment tag (DEEPEVAL_ENV): development/staging/production."""
    return os.environ.get("DEEPEVAL_ENV", "development")


def deepeval_sampling_rate() -> float:
    """Fraction of turns to trace (DEEPEVAL_SAMPLING_RATE, default 1.0)."""
    try:
        return float(os.environ.get("DEEPEVAL_SAMPLING_RATE", "1.0"))
    except ValueError:
        return 1.0


def tracing_enabled() -> bool:
    """Tracing is on when a Confident key is present, or DEEPEVAL_TRACING is
    truthy (local-only collection without export)."""
    if confident_api_key():
        return True
    return os.environ.get("DEEPEVAL_TRACING", "").strip().lower() in {
        "1", "true", "yes", "on",
    }
