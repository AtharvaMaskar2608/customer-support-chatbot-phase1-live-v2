"""Per-endpoint routing for the FinX report backends.

The credential is a function of the *backend*, not the app (design decision 3):

  - .NET / Go middleware report endpoints (P&L, Ledger, Tax, Contract Notes)
    authenticate with the **SessionId** in `authorization`.
  - The MIS / CML reports backend authenticates with the **SSO JWT**.

The `from:` header is a non-authenticating client build tag on every endpoint.

`route(endpoint)` returns a `RouteSpec` describing where to send the request,
which credential to put in `authorization`, the static extra headers, and how
to read the response envelope (`BodyShape`, consumed by the two-layer error
model in client.py). Wrong routing fails upstream, so it lives in one table and
is unit-tested.

Only P&L is wired end-to-end in Wave 0. Ledger / Tax / CML entries are present
so their Wave-1 flows are a route entry + a thin per-endpoint body mapping, not
new machinery. Build URLs are read from config at call time so env overrides
(and test mocks) take effect without re-import.
"""

from dataclasses import dataclass
from enum import Enum

from app import config


class Endpoint(str, Enum):
    """The upstream report endpoints, keyed independently of any app/flow."""

    PNL = "pnl"
    LEDGER = "ledger"  # Wave 1
    TAX = "tax"  # Wave 1
    CML = "cml"  # Wave 1


class AuthSource(str, Enum):
    """Which credential the client places in the `authorization` header."""

    SESSION_ID = "session_id"  # .NET / Go report endpoints
    SSO_JWT = "sso_jwt"  # MIS / CML


@dataclass(frozen=True)
class BodyShape:
    """How to read a success/failure out of the upstream response envelope.

    The two-layer error model branches on transport status first (401/204/2xx),
    then on this body status field. It NEVER string-matches `Reason` — the
    wording differs across endpoints ("Data not found." vs "Data not available.").
    """

    status_field: str  # ".NET" -> "Status"; MIS -> "statusCode"
    success_values: frozenset  # ".NET" -> {"Success"}; MIS -> {200}
    response_field: str  # where the URL / confirmation / body lives


@dataclass(frozen=True)
class RouteSpec:
    """Everything needed to make one authenticated upstream call."""

    url: str
    auth_source: AuthSource
    extra_headers: dict[str, str]
    body_shape: BodyShape
    # Prefix for the auth header value, e.g. "Session " on the contract-note
    # download sub-call. Empty for every endpoint wired so far.
    auth_prefix: str = ""


# The .NET middleware trio (P&L / Ledger / Tax) share one envelope shape.
_DOTNET_BODY_SHAPE = BodyShape(
    status_field="Status",
    success_values=frozenset({"Success"}),
    response_field="Response",
)

# The MIS / CML backend uses a camelCase envelope with a numeric status.
_MIS_BODY_SHAPE = BodyShape(
    status_field="statusCode",
    success_values=frozenset({200}),
    response_field="body",
)


def _dotnet_headers() -> dict[str, str]:
    return {
        "from": config.finx_from_header(),
        "content-type": "application/json",
    }


def _mis_headers() -> dict[str, str]:
    return {
        "authType": "jwt",
        "source": "FINX_ANDROID",
        "from": config.finx_from_header(),
        "content-type": "application/json",
    }


def route(endpoint: Endpoint) -> RouteSpec:
    """Resolve the routing spec for an endpoint (URLs read from config)."""
    if endpoint is Endpoint.PNL:
        return RouteSpec(
            url=config.upstream_pnl_url(),
            auth_source=AuthSource.SESSION_ID,
            extra_headers=_dotnet_headers(),
            body_shape=_DOTNET_BODY_SHAPE,
        )
    if endpoint is Endpoint.LEDGER:
        return RouteSpec(
            url=config.upstream_ledger_url(),
            auth_source=AuthSource.SESSION_ID,
            extra_headers=_dotnet_headers(),
            body_shape=_DOTNET_BODY_SHAPE,
        )
    if endpoint is Endpoint.TAX:
        return RouteSpec(
            url=config.upstream_tax_url(),
            auth_source=AuthSource.SESSION_ID,
            extra_headers=_dotnet_headers(),
            body_shape=_DOTNET_BODY_SHAPE,
        )
    if endpoint is Endpoint.CML:
        return RouteSpec(
            url=config.upstream_cml_url(),
            auth_source=AuthSource.SSO_JWT,
            extra_headers=_mis_headers(),
            body_shape=_MIS_BODY_SHAPE,
        )
    raise KeyError(f"no route for endpoint {endpoint!r}")
