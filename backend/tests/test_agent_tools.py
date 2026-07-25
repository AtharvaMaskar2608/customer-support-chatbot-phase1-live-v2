"""Agent tool registry + dispatcher (CHO-213 · task 2.3).

Covers: the credential-isolation schema invariant (no credential field in any
tool schema), dispatch of known/unknown tools, error mapping (validation,
upstream auth, unexpected exception), and the one-core-two-entry-points
equivalence for P&L (route vs dispatch → same envelope).
"""

import asyncio
import datetime
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.agent import tools as agent_tools
from app.agent.ctx import CODE_AUTH_EXPIRED, CODE_VALIDATION, ToolCtx
from app.finx.delivery import FileTokenStore
from app.main import create_app

SESSION_ID = "test-session-token"
SSO_JWT = "test-sso-jwt"
CLIENT_CODE = "X008593"

HEADERS = {
    "Authorization": SSO_JWT,
    "X-Session-Id": SESSION_ID,
    "X-User-Id": CLIENT_CODE,
}

ARTIFACT_URL = (
    "https://client-report.choiceindia.com/PDFReports/PNLReport_X008593.pdf"
)
PDF_BYTES = b"%PDF-1.4\n" + b"x" * 5000

PNL_PARAMS = {
    "segment": "Equity",
    "fromDate": "2026-04-01",
    "toDate": "2026-07-01",
    "delivery": "download",
}

# Anything that could ever carry or select a credential/identity. Property
# names are normalized (lowercase, separators stripped) before comparison.
FORBIDDEN_PARAM_NAMES = {
    "sessionid",
    "ssotoken",
    "ssojwt",
    "jwt",
    "token",
    "accesstoken",
    "authorization",
    "clientcode",
    "clientid",
    "userid",
    "usercode",
    "loginid",
    "apikey",
    "password",
    "secret",
    "fileid",
}


def _normalize(name: str) -> str:
    return name.lower().replace("_", "").replace("-", "")


def _walk_property_names(schema: dict) -> list[str]:
    names: list[str] = []
    for key, sub in (schema.get("properties") or {}).items():
        names.append(key)
        if isinstance(sub, dict):
            names.extend(_walk_property_names(sub))
        if isinstance(sub, dict) and isinstance(sub.get("items"), dict):
            names.extend(_walk_property_names(sub["items"]))
    return names


def _ctx(http_client, **extra) -> ToolCtx:
    return ToolCtx(
        session_id=SESSION_ID,
        sso_jwt=SSO_JWT,
        client_code=CLIENT_CODE,
        http_client=http_client,
        **extra,
    )


async def _dispatch(name, params, **ctx_extra):
    async with httpx.AsyncClient() as http:
        return await agent_tools.dispatch(name, params, _ctx(http, **ctx_extra))


# --- schema invariants (credential isolation, task 2.3) ----------------------


def test_no_credential_fields_in_any_schema():
    schemas = agent_tools.tool_schemas()
    assert len(schemas) == 12  # 8 capabilities (notes=2) + form + ticket + get_report_columns (CHO-228)
    for schema in schemas:
        for name in _walk_property_names(schema["input_schema"]):
            assert _normalize(name) not in FORBIDDEN_PARAM_NAMES, (
                f"{schema['name']} exposes credential-shaped param {name!r}"
            )


def test_schemas_are_closed_objects():
    for schema in agent_tools.tool_schemas():
        input_schema = schema["input_schema"]
        assert input_schema["type"] == "object"
        assert input_schema["additionalProperties"] is False
        assert schema["description"]  # prescriptive text present


def test_required_fields_match_the_request_models():
    required = {
        s["name"]: set(s["input_schema"]["required"])
        for s in agent_tools.tool_schemas()
    }
    assert required["get_pnl_report"] == {
        "segment", "fromDate", "toDate", "delivery",
    }
    assert required["get_ledger_report"] == {
        "book", "fromDate", "toDate", "delivery",
    }
    assert required["get_capital_gains_report"] == {"fy", "format", "delivery"}
    assert required["list_contract_notes"] == {"fromDate", "toDate"}
    assert required["download_contract_note"] == {"id"}
    assert required["get_holdings"] == set()
    assert required["get_money_transactions"] == set()
    assert required["get_brokerage_rates"] == set()
    assert required["search_knowledge_base"] == {"query"}
    assert required["raise_support_ticket"] == {"reason"}


def test_zero_slot_tools_expose_no_parameters():
    by_name = {s["name"]: s for s in agent_tools.tool_schemas()}
    for name in ("get_holdings", "get_money_transactions", "get_brokerage_rates"):
        assert by_name[name]["input_schema"]["properties"] == {}


def test_search_knowledge_base_description_hides_mechanism_nouns():
    """CHO-265: Anthropic-facing KB tool copy must not prime mechanism leaks."""
    by_name = {s["name"]: s for s in agent_tools.tool_schemas()}
    desc = by_name["search_knowledge_base"]["description"]
    for banned in ("knowledge base", "search results", "Summarize the results"):
        assert banned not in desc
    assert "Answer the user directly" in desc
    # internal tool name stays
    assert by_name["search_knowledge_base"]["name"] == "search_knowledge_base"
    brokerage = by_name["get_brokerage_rates"]["description"]
    assert "prefer" not in brokerage.lower() or "prefer search" not in brokerage
    assert "call search_knowledge_base instead" in brokerage


# --- dispatch ----------------------------------------------------------------


def test_dispatch_unknown_tool_is_error_not_raise():
    content, is_error, duration_ms = asyncio.run(
        _dispatch("open_bank_vault", {})
    )
    assert is_error is True
    assert "unknown tool" in content
    assert duration_ms >= 0


def test_dispatch_validation_error_names_the_fields():
    content, is_error, _ = asyncio.run(
        _dispatch("get_pnl_report", {"segment": "Equity"})
    )
    assert is_error is True
    assert "fromDate" in content and "toDate" in content
    assert "ask the user" in content


@respx.mock
def test_dispatch_maps_upstream_401_to_auth_expired():
    respx.post(config.upstream_holdings_url()).mock(
        return_value=httpx.Response(401)
    )

    async def scenario():
        async with httpx.AsyncClient() as http:
            return await agent_tools.dispatch_outcome(
                "get_holdings", {}, _ctx(http)
            )

    outcome = asyncio.run(scenario())
    assert outcome.is_error is True
    assert outcome.error_code == CODE_AUTH_EXPIRED
    assert "sign in" in outcome.content


def test_dispatch_catches_unexpected_handler_exception(monkeypatch, caplog):
    async def boom(params, ctx):
        raise RuntimeError("secret input ABCDE1234F")

    monkeypatch.setattr(agent_tools.TOOLS["get_holdings"], "handler", boom)
    content, is_error, _ = asyncio.run(_dispatch("get_holdings", {}))
    assert is_error is True
    assert "unexpectedly" in content
    # log carries the exception type only — never the message/input
    assert "ABCDE1234F" not in caplog.text


def test_dispatch_validation_outcome_carries_code():
    async def scenario():
        async with httpx.AsyncClient() as http:
            return await agent_tools.dispatch_outcome(
                "get_ledger_report", {"book": "Savings"}, _ctx(http)
            )

    outcome = asyncio.run(scenario())
    assert outcome.is_error is True
    assert outcome.error_code == CODE_VALIDATION
    assert outcome.envelope is None


@respx.mock
def test_dispatch_success_returns_compact_sorted_json():
    respx.post(config.upstream_brokerage_url()).mock(
        return_value=httpx.Response(
            200,
            json={
                "Status": "Success",
                "Response": [
                    {"title": "Equity", "list": [{"title": "Delivery", "desc": "0.1%"}]}
                ],
            },
        )
    )
    content, is_error, _ = asyncio.run(_dispatch("get_brokerage_rates", {}))
    assert is_error is False
    payload = json.loads(content)
    assert payload == {
        "kind": "ok",
        "groups": [{"title": "Equity", "list": [{"title": "Delivery", "desc": "0.1%"}]}],
    }
    # compact + sorted keys: deterministic transcript bytes
    assert content == json.dumps(payload, sort_keys=True, separators=(",", ":"))


# --- one core, two entry points (P&L) ----------------------------------------


def _mock_pnl_download():
    respx.post(config.upstream_pnl_url()).mock(
        return_value=httpx.Response(
            200,
            json={"Status": "Success", "Response": ARTIFACT_URL, "Reason": ""},
        )
    )
    respx.get(ARTIFACT_URL).mock(
        return_value=httpx.Response(
            200, content=PDF_BYTES, headers={"content-type": "application/pdf"}
        )
    )


@respx.mock
def test_one_core_two_entry_points_pnl_equivalence(monkeypatch):
    """POST /api/report/pnl and dispatch('get_pnl_report') run the same core
    and produce the same normalized envelope (fileToken is a fresh opaque
    token per call — everything else must match byte-for-byte)."""
    monkeypatch.setattr("app.config.database_url", lambda: None)
    _mock_pnl_download()

    with TestClient(create_app()) as client:
        route_payload = client.post(
            "/api/report/pnl", headers=HEADERS, json=PNL_PARAMS
        ).json()

    content, is_error, _ = asyncio.run(
        _dispatch(
            "get_pnl_report",
            PNL_PARAMS,
            report_files=FileTokenStore(ttl_seconds=60),
        )
    )
    assert is_error is False
    tool_payload = json.loads(content)

    def _without_token(payload):
        return {k: v for k, v in payload.items() if k != "fileToken"}

    assert _without_token(tool_payload) == _without_token(route_payload)
    assert tool_payload["fileToken"] and route_payload["fileToken"]
    assert tool_payload["fileToken"] != route_payload["fileToken"]
    assert tool_payload["file"]["name"] == "PnL_Equity_2026-04-01_to_2026-07-01.pdf"


@respx.mock
def test_dispatch_ignores_credential_shaped_input(monkeypatch):
    """A tool input smuggling ClientId/SessionId is ignored: the upstream call
    carries only header-derived credentials (extra='ignore' + ctx injection)."""
    route = respx.post(config.upstream_pnl_url()).mock(
        return_value=httpx.Response(
            200,
            json={"Status": "Success", "Response": "user@example.com", "Reason": ""},
        )
    )
    params = {
        **PNL_PARAMS,
        "delivery": "email",
        "ClientId": "EVIL01",
        "SessionId": "stolen-session",
    }
    content, is_error, _ = asyncio.run(_dispatch("get_pnl_report", params))
    assert is_error is False
    sent = json.loads(route.calls.last.request.content)
    assert sent["ClientId"] == CLIENT_CODE
    assert sent["UserId"] == CLIENT_CODE
    assert sent["SessionId"] == SESSION_ID
    assert "EVIL01" not in json.dumps(sent)


# --- CHO-277: the model-facing projection seam --------------------------------
#
# `Tool.model_view` shapes the tool_result `content` only. `DispatchOutcome.
# envelope` is ALWAYS the unprojected result, which is what loop.py's
# `_artifact_payload` reads — so the pinned SSE artifact contract cannot move.
# (The loop-level assertion lives here rather than in test_agent_loop.py, which
# two sibling changes own.)

MONEY_ROWS = 72


def _money_upstream(indices: range, list_key: str) -> httpx.Response:
    """Rows on strictly decreasing timestamps (index 0 = newest), so the two
    directions interleave deterministically in the merged stream."""
    base = datetime.datetime(2026, 7, 20, 12, 0, 0)
    rows = [
        {
            "Amount": 100.0 + i,
            "Status": "SUCCESS",
            "RequestedDateTime": (
                base - datetime.timedelta(minutes=i)
            ).isoformat(),
            "ModeOfPayment": "UPI",
            "DepositBankName": "ICICI NSE CLIENT A/C - 000405107280",
            "ClientBankName": "HDFC",
            "ClientBankAccNo": "50100218008829",
            "VoucherNo": f"V{i}",
            "Reason": "",
        }
        for i in indices
    ]
    return httpx.Response(
        200,
        json={
            "Status": "Success",
            "Response": {list_key: rows, "TotalCount": [{"TotalRecords": len(rows)}]},
            "Reason": "",
        },
    )


def _mock_money(count: int = MONEY_ROWS) -> None:
    respx.post(config.upstream_payin_url()).mock(
        return_value=_money_upstream(range(0, count, 2), "PayInTxn")
    )
    respx.post(config.upstream_payout_url()).mock(
        return_value=_money_upstream(range(1, count, 2), "PayOutTxn")
    )


def _money_outcome():
    async def scenario():
        async with httpx.AsyncClient() as http:
            return await agent_tools.dispatch_outcome(
                "get_money_transactions", {}, _ctx(http)
            )

    return asyncio.run(scenario())


def test_tools_without_a_model_view_serialize_the_envelope_verbatim():
    """The seam defaults to identity — only money opts in today."""
    opted_in = {
        t.name for t in agent_tools._TOOL_LIST if t.model_view is not None
    }
    assert opted_in == {"get_money_transactions"}


@respx.mock
def test_money_model_view_bounds_content_but_not_the_envelope():
    _mock_money()

    outcome = _money_outcome()

    assert outcome.is_error is False
    model_payload = json.loads(outcome.content)
    # what the model reads: capped rows + shown/total + the omission note
    assert len(model_payload["txns"]) == 25
    assert model_payload["txnsShown"] == 25
    assert model_payload["txnsTotal"] == MONEY_ROWS
    assert "note" in model_payload
    # what the frontend renders: every row, and none of the projection's keys
    assert len(outcome.envelope["txns"]) == MONEY_ROWS
    assert not {"txnsShown", "txnsTotal", "note"} & set(outcome.envelope)


@respx.mock
def test_artifact_payload_still_carries_every_row():
    """loop.py builds the SSE `data` artifact from `outcome.envelope`, so the
    card is unaffected by the projection — asserted through the real function."""
    from app.agent.loop import _artifact_payload

    _mock_money()
    outcome = _money_outcome()

    artifact = _artifact_payload("get_money_transactions", outcome)

    assert artifact["kind"] == "data"
    assert artifact["tool"] == "get_money_transactions"
    assert len(artifact["txns"]) == MONEY_ROWS
    assert "txnsShown" not in artifact and "note" not in artifact


@respx.mock
def test_model_view_never_touches_an_error_result(monkeypatch):
    """A failure message IS the corrective instruction to the model — it must
    reach the transcript verbatim, never through a projection."""
    calls = []

    def spy(envelope):
        calls.append(envelope)
        return {"kind": "ok"}

    monkeypatch.setattr(
        agent_tools.TOOLS["get_money_transactions"], "model_view", spy
    )
    respx.post(config.upstream_payin_url()).mock(return_value=httpx.Response(401))
    respx.post(config.upstream_payout_url()).mock(return_value=httpx.Response(500))

    outcome = _money_outcome()

    assert outcome.is_error is True
    assert outcome.error_code == CODE_AUTH_EXPIRED
    assert "sign in" in outcome.content
    assert outcome.envelope is None
    assert calls == []


def test_model_view_is_bypassed_for_unknown_tool_and_handler_exception(monkeypatch):
    calls = []

    def spy(envelope):
        calls.append(envelope)
        return envelope

    async def boom(params, ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent_tools.TOOLS["get_holdings"], "model_view", spy)
    monkeypatch.setattr(agent_tools.TOOLS["get_holdings"], "handler", boom)

    assert asyncio.run(_dispatch("no_such_tool", {}))[1] is True
    assert asyncio.run(_dispatch("get_holdings", {}))[1] is True
    assert calls == []


@respx.mock
def test_a_raising_model_view_degrades_to_the_full_envelope(monkeypatch, caplog):
    """A projection bug must cost tokens, never a healthy tool call — and the
    log may carry the exception type only."""
    def broken(envelope):
        raise ValueError("PAN ABCDE1234F")

    monkeypatch.setattr(
        agent_tools.TOOLS["get_money_transactions"], "model_view", broken
    )
    _mock_money()

    outcome = _money_outcome()

    assert outcome.is_error is False
    assert len(json.loads(outcome.content)["txns"]) == MONEY_ROWS
    assert "ABCDE1234F" not in caplog.text
    assert "ValueError" in caplog.text


def test_kb_schema_exposes_the_response_format_enum():
    by_name = {s["name"]: s for s in agent_tools.tool_schemas()}
    props = by_name["search_knowledge_base"]["input_schema"]["properties"]
    assert props["response_format"]["enum"] == ["concise", "detailed"]
    assert "detailed" in props["response_format"]["description"]
    # the CHO-267 recall default is unchanged
    assert "default 10" in props["top_k"]["description"]
    assert "response_format" not in (
        by_name["search_knowledge_base"]["input_schema"]["required"]
    )


def test_money_description_tells_the_model_the_aggregates_are_complete():
    by_name = {s["name"]: s for s in agent_tools.tool_schemas()}
    desc = by_name["get_money_transactions"]["description"]
    assert "capped" in desc
    assert "exact" in desc
    assert "card" in desc
