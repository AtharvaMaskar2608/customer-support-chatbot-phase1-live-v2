"""Eval harness plumbing (CHO-276 · design D1/D2/D3/D4).

What a case gets from here:

* :func:`eval_session` — a FastAPI app wired for evals. The conversation store
  is memory-only, `agent_tools.dispatch_outcome` is replaced by a recording
  double serving canned envelopes, `tracing` runs against a capturing fake pool
  so token usage is available in-process, and `app.state.http_client` REFUSES
  every outbound request. The only network call an attempt can make is the
  Anthropic Messages API, for the probe turn.
* seeding helpers (`Session.user` / `.assistant` / `.tool_round` /
  `.flow_event`) that write prior turns straight through `store.append_turn`, so
  a fourteen-turn thread costs ONE model call (design D1).
* :meth:`Session.probe` — one real `POST /api/chat`, returned as parsed SSE
  events, assistant text, recorded tool calls and priced token usage.

Invariants this module enforces rather than merely documents:

* **No FinX / Freshdesk / Choice / Profile request is possible.**
  `app.state.http_client` is :class:`BlockedHttpClient`: every verb raises and
  the attempt is recorded (host only — never a credentialed URL). The report
  carries the count, which is how "no Freshdesk request anywhere in the sweep"
  is confirmed rather than assumed.
* **No Postgres.** `config.database_url` is forced to None for the session, so
  no pool is created and the store never enqueues a write.
* **No credentials.** The eval identity is synthetic; the only secret read is
  `ANTHROPIC_API_KEY`, and it is never written to a report.
* **A missing key is a SKIP, not a failure** (:func:`api_key_present`).

PII: nothing here logs or returns message text. `CaseOutcome.observed` carries
only what a case asserts on (tool names, tool-input fields, synthetic ids) and
failure reasons drawn from `assertions`' own vocabulary.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator
from unittest import mock
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from app import config, greeting
from app.agent import tools as agent_tools
from app.agent import tracing
from app.agent.tools import DispatchOutcome
from app.agent.trace_cost import inr_from_usd, usd_for_usage
from app.main import create_app

from evals import assertions

# Synthetic identity: not a session token, not a client code, not a JWT. The
# tool layer is doubled and the HTTP client blocked, so nothing authenticates
# with these — they only key the in-memory thread.
SESSION_ID = "cho276-eval-thread"
SSO_JWT = "cho276-eval-not-a-real-jwt"
CLIENT_CODE = "EVAL0001"

HEADERS = {
    "Authorization": SSO_JWT,
    "X-Session-Id": SESSION_ID,
    "X-User-Id": CLIENT_CODE,
}

# What an unstubbed tool returns. Neutral on purpose: it must not nudge the
# model into abstaining (that is the very thing every case asserts against).
UNSTUBBED_TOOL_MESSAGE = (
    "That lookup is not available for this request — continue with what you "
    "already have."
)


class HarnessError(RuntimeError):
    """A failure of the harness itself (bad SSE, non-200 probe) as opposed to a
    behavioural failure of the model. Reported distinctly."""


def api_key_present() -> bool:
    """The one env var the live cases need. False ⇒ every case skips and the
    runner exits 0 (task 1.6 / 5.2)."""
    return bool(config.anthropic_api_key())


# --- outbound network: blocked by construction -------------------------------


def _host(url: Any) -> str:
    """Hostname only. A full upstream URL can carry a report token, so it never
    reaches a log or a report."""
    try:
        return urlsplit(str(url)).hostname or "unknown-host"
    except ValueError:
        return "unparseable-host"


class BlockedHttpClient:
    """Stands in for the shared `httpx.AsyncClient`.

    Every request raises, so a tool core that slipped past the double cannot
    reach FinX, Freshdesk, or the Profile API. Attempts are recorded by host so
    the sweep can state "zero Freshdesk requests" as an observation.
    """

    def __init__(self) -> None:
        self.attempts: list[str] = []

    async def _blocked(self, method: str, url: Any) -> None:
        self.attempts.append(f"{method} {_host(url)}")
        raise AssertionError(
            "eval harness blocked an outbound HTTP request "
            f"({method} {_host(url)}) — the tool layer must be doubled"
        )

    async def post(self, url: Any, *args: Any, **kwargs: Any) -> None:
        await self._blocked("POST", url)

    async def get(self, url: Any, *args: Any, **kwargs: Any) -> None:
        await self._blocked("GET", url)

    async def request(self, method: str, url: Any, *args: Any, **kwargs: Any) -> None:
        await self._blocked(str(method).upper(), url)


class CapturingPool:
    """The fake pool that opens tracing's gate (design D3).

    `tracing.observe_turn` is a pass-through when no pool is present, so the
    span tree — and with it the token/cache split we price — only exists when
    `ctx.pg_pool` is set. This object satisfies that check without a database:
    `execute` records, and every read verb raises, because nothing in an eval
    should ever read from Postgres.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, sql: str, *args: Any) -> None:
        self.calls.append(sql.strip().split("\n")[0][:60])

    async def close(self) -> None:
        """The app's lifespan closes the pool on shutdown."""

    async def fetch(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("eval harness must not read from Postgres")

    async def fetchrow(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("eval harness must not read from Postgres")

    def acquire(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("eval harness must not acquire a Postgres connection")


# --- the recording tool double (design D2) -----------------------------------


@dataclass
class Reply:
    """One canned answer from the doubled tool layer.

    `envelope` is a success envelope (serialized exactly as the real dispatcher
    does, so the wire bytes match production); `error` is the actionable message
    an `is_error` tool_result carries.
    """

    envelope: dict | None = None
    error: str | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


def ok(envelope: dict) -> Reply:
    return Reply(envelope=envelope)


def err(message: str) -> Reply:
    return Reply(error=message)


PASSTHROUGH = "passthrough"


class ToolDouble:
    """Replaces `agent_tools.dispatch_outcome`.

    * records every `(tool name, input)` — the routing assertions read this;
    * answers from `responses[name]`, a list consumed in order with the last
      entry repeating (so a case can bounce a call and then serve a fresh
      result, as E3's recovery sub-case needs);
    * `responses[name] is PASSTHROUGH` runs the REAL dispatcher, which design
      D2 allows for the two credential-free local cores (`open_report_form`,
      `get_report_columns`);
    * an unstubbed tool gets a neutral `is_error` — it never reaches a handler.
    """

    def __init__(
        self,
        responses: dict[str, Any],
        *,
        original: Callable[..., Any],
    ) -> None:
        self._responses: dict[str, Any] = {}
        for name, value in responses.items():
            if value is PASSTHROUGH:
                self._responses[name] = PASSTHROUGH
            elif isinstance(value, list):
                self._responses[name] = list(value)
            else:
                self._responses[name] = [value]
        self._original = original
        self._counts: dict[str, int] = {}
        self.calls: list[tuple[str, dict]] = []

    async def dispatch_outcome(
        self, name: str, tool_input: Any, ctx: Any
    ) -> DispatchOutcome:
        payload = dict(tool_input) if isinstance(tool_input, dict) else {}
        self.calls.append((name, payload))
        configured = self._responses.get(name)
        if configured is PASSTHROUGH:
            return await self._original(name, tool_input, ctx)
        if configured is None:
            return DispatchOutcome(
                content=UNSTUBBED_TOOL_MESSAGE, is_error=True, duration_ms=1
            )
        index = min(self._counts.get(name, 0), len(configured) - 1)
        self._counts[name] = self._counts.get(name, 0) + 1
        reply: Reply = configured[index]
        if reply.is_error:
            return DispatchOutcome(
                content=str(reply.error), is_error=True, duration_ms=1
            )
        return DispatchOutcome(
            content=tool_result_content(reply.envelope or {}),
            is_error=False,
            duration_ms=1,
            envelope=reply.envelope,
        )


def tool_result_content(envelope: dict) -> str:
    """The exact bytes the real dispatcher puts in a tool_result block, so a
    seeded result is indistinguishable from a lived one."""
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))


# --- usage + cost ------------------------------------------------------------


@dataclass
class Usage:
    """Token usage for one attempt, read off the `llm` spans tracing built."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    rounds: int = 0
    model: str | None = None
    inr: float | None = None

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    def add(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens
            + other.cache_creation_tokens,
            rounds=self.rounds + other.rounds,
            model=other.model or self.model,
            inr=round((self.inr or 0.0) + (other.inr or 0.0), 6)
            if (self.inr is not None or other.inr is not None)
            else None,
        )

    def as_dict(self) -> dict:
        return {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cacheReadTokens": self.cache_read_tokens,
            "cacheCreationTokens": self.cache_creation_tokens,
            "totalTokens": self.total_tokens,
            "modelRounds": self.rounds,
            "model": self.model,
            "inr": self.inr,
        }


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def usage_from_traces(traces: list[Any]) -> Usage:
    """Sum the `llm` spans of every captured trace and price them with the
    production cost model (`trace_cost`) — the same numbers the dashboard
    would show, without a live `agent_traces` table (design D3)."""
    usage = Usage()
    total_usd = 0.0
    priced = False
    for trace in traces:
        for span in trace.spans:
            if span.type != "llm":
                continue
            meta = span.metadata or {}
            usage.rounds += 1
            usage.input_tokens += _int(meta.get("input_tokens"))
            usage.output_tokens += _int(meta.get("output_tokens"))
            usage.cache_read_tokens += _int(meta.get("cache_read_input_tokens"))
            usage.cache_creation_tokens += _int(
                meta.get("cache_creation_input_tokens")
            )
            model = meta.get("model")
            if isinstance(model, str):
                usage.model = model
            usd = usd_for_usage(
                model=model if isinstance(model, str) else None,
                input_tokens=_int(meta.get("input_tokens")),
                output_tokens=_int(meta.get("output_tokens")),
                cache_read_input_tokens=_int(meta.get("cache_read_input_tokens")),
                cache_creation_input_tokens=_int(
                    meta.get("cache_creation_input_tokens")
                ),
            )
            if usd is not None:
                priced = True
                total_usd += usd
    usage.inr = inr_from_usd(total_usd) if priced else None
    return usage


# --- the probe result --------------------------------------------------------


@dataclass
class Probe:
    """One real `/api/chat` turn, as the assertions see it."""

    events: list[tuple[str | None, dict | None]]
    text: str
    text_before_first_tool: str
    tool_calls: list[tuple[str, dict]]
    usage: Usage
    seed_to_probe_seconds: float
    latency_seconds: float
    blocked_http_attempts: list[str]
    error_event: str | None

    @property
    def tool_names(self) -> list[str]:
        return assertions.tool_names(self.tool_calls)

    @property
    def first_tool(self) -> str | None:
        return assertions.first_tool_call(self.tool_calls)


# --- case protocol -----------------------------------------------------------


@dataclass
class CaseOutcome:
    """The verdict of one attempt. `observed` is small, non-PII, and carries
    only what the case asserted on."""

    passed: bool
    failures: list[str]
    observed: dict
    usage: Usage
    abstained: bool
    seed_to_probe_seconds: float | None = None
    error: str | None = None


@dataclass
class Case:
    id: str
    title: str
    run: Callable[[], CaseOutcome]
    # The merge gate wants 3/3 from the cases where a single miss is a real
    # incident (a fabricated capability token); everything else is >= 2/3.
    hard_fail: bool = False
    notes: str = ""


def finish(
    probe: Probe, failures: list[str], observed: dict | None = None
) -> CaseOutcome:
    """Build the outcome AND apply the shared no-abstention assertion.

    Every case returns through here (task 2.8), so the assertion cannot be
    forgotten in a new case: abstention is appended to `failures` whatever else
    the case checked.
    """
    abstention = assertions.abstention_match(probe.text)
    all_failures = list(failures)
    if abstention:
        all_failures.append(f"abstention:{abstention}")
    obs = {
        "firstTool": probe.first_tool,
        "tools": probe.tool_names,
        "modelRounds": probe.usage.rounds,
        "latencySeconds": probe.latency_seconds,
        "blockedHttpAttempts": probe.blocked_http_attempts,
    }
    if probe.error_event:
        obs["sseError"] = probe.error_event
        all_failures.append(f"sse-error:{probe.error_event}")
    obs.update(observed or {})
    return CaseOutcome(
        passed=not all_failures,
        failures=all_failures,
        observed=obs,
        usage=probe.usage,
        abstained=bool(abstention),
        seed_to_probe_seconds=round(probe.seed_to_probe_seconds, 3),
    )


# --- the session -------------------------------------------------------------


def _parse_sse(text: str) -> list[tuple[str | None, dict | None]]:
    events: list[tuple[str | None, dict | None]] = []
    for chunk in text.strip().split("\n\n"):
        if not chunk.strip():
            continue
        event = None
        data: dict | None = None
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                try:
                    data = json.loads(line[len("data: ") :])
                except json.JSONDecodeError as exc:
                    raise HarnessError(f"unparseable SSE data ({exc.msg})") from None
        events.append((event, data))
    return events


class Session:
    """Seeding + probing against one eval app instance."""

    def __init__(
        self,
        *,
        app: Any,
        client: TestClient,
        double: ToolDouble,
        traces: list[Any],
        http: BlockedHttpClient,
    ) -> None:
        self._app = app
        self._client = client
        self._double = double
        self._traces = traces
        self._http = http
        self._store = app.state.conversation_store
        self._thread = asyncio.run(
            self._store.get_thread(SESSION_ID, client_code=CLIENT_CODE)
        )
        # The loop fetches the client's first name once per conversation. It is
        # a real Profile API call — pre-marked as done so the probe turn cannot
        # even try (BlockedHttpClient is the backstop, this is the intent).
        self._thread.name_fetched = True
        self._tool_use_seq = 0
        # Elapsed seconds are reported from the FIRST seeded turn, not the last:
        # the number exists so a reviewer can tell whether a variant run against
        # REAL contract-note ids stayed inside their 600-second TTL, and that
        # clock starts when the note list enters the thread (design D6).
        self._seed_started: float | None = None

    # -- seeding (design D1: prior turns cost nothing) -----------------------

    @property
    def thread(self) -> Any:
        return self._thread

    @property
    def app(self) -> Any:
        """The live app. Exposed so a plumbing self-check can swap in a scripted
        Anthropic client (`app.state.anthropic_client`) and exercise the seeding,
        SSE parsing and usage capture without spending anything."""
        return self._app

    @property
    def turn_count(self) -> int:
        return len(self._thread.turns)

    def _append(self, **kwargs: Any) -> None:
        if self._seed_started is None:
            self._seed_started = time.monotonic()
        self._store.append_turn(self._thread, **kwargs)

    def user(self, text: str) -> None:
        self._append(
            role="user", kind="user_text", content=[{"type": "text", "text": text}]
        )

    def assistant(self, text: str) -> None:
        self._append(
            role="assistant",
            kind="assistant_text",
            content=[{"type": "text", "text": text}],
            meta={"model": config.agent_model(), "stop_reason": "end_turn"},
        )

    def flow_event(self, text: str, meta: dict | None = None) -> None:
        """A widget completion as the app records it (`agent.events`)."""
        self._append(
            role="user",
            kind="flow_event",
            content=[{"type": "text", "text": text}],
            meta=meta or {},
        )

    def tool_round(
        self,
        name: str,
        tool_input: dict | None = None,
        *,
        envelope: dict | None = None,
        error: str | None = None,
        text: str | None = None,
    ) -> None:
        """One assistant tool_use turn plus its tool_result turn, exactly as the
        loop writes them (kinds, block shapes, meta) — so `thread.messages()`
        replays byte-identically to a lived thread."""
        self._tool_use_seq += 1
        block_id = f"eval_tu_{self._tool_use_seq}"
        content: list[dict] = []
        if text:
            content.append({"type": "text", "text": text})
        content.append(
            {
                "type": "tool_use",
                "id": block_id,
                "name": name,
                "input": tool_input or {},
            }
        )
        self._append(
            role="assistant",
            kind="assistant_tool_use",
            content=content,
            meta={"model": config.agent_model(), "stop_reason": "tool_use"},
        )
        is_error = error is not None
        self._append(
            role="user",
            kind="tool_result",
            content=[
                {
                    "type": "tool_result",
                    "tool_use_id": block_id,
                    "content": error
                    if is_error
                    else tool_result_content(envelope or {}),
                    "is_error": is_error,
                }
            ],
            meta={"tool_name": name, "is_error": is_error, "duration_ms": 1},
        )

    # -- probing (the ONE live model call) -----------------------------------

    def probe(self, message: str) -> Probe:
        seed_to_probe = (
            0.0 if self._seed_started is None else time.monotonic() - self._seed_started
        )
        self._traces.clear()
        self._double.calls.clear()
        started = time.perf_counter()
        response = self._client.post(
            "/api/chat", headers=HEADERS, json={"message": message}
        )
        latency = time.perf_counter() - started
        if response.status_code != 200:
            raise HarnessError(f"probe returned HTTP {response.status_code}")
        events = _parse_sse(response.text)
        text_parts: list[str] = []
        pre_tool_parts: list[str] = []
        seen_tool = False
        error_event: str | None = None
        for event, data in events:
            if event == "text" and isinstance(data, dict):
                delta = str(data.get("delta") or "")
                text_parts.append(delta)
                if not seen_tool:
                    pre_tool_parts.append(delta)
            elif event == "tool":
                seen_tool = True
            elif event == "error" and isinstance(data, dict):
                error_event = str(data.get("error"))
        return Probe(
            events=events,
            text="".join(text_parts),
            text_before_first_tool="".join(pre_tool_parts),
            tool_calls=list(self._double.calls),
            usage=usage_from_traces(self._traces),
            seed_to_probe_seconds=seed_to_probe,
            latency_seconds=round(latency, 3),
            blocked_http_attempts=list(self._http.attempts),
            error_event=error_event,
        )


@contextlib.contextmanager
def eval_session(
    responses: dict[str, Any] | None = None,
) -> Iterator[Session]:
    """An app wired for one eval attempt. See the module docstring for the
    invariants this establishes."""
    traces: list[Any] = []

    def _capture(pool: Any, trace: Any) -> None:
        """Replaces tracing's fire-and-forget persist.

        The span tree is captured synchronously instead of being written by a
        background task, so an attempt's usage is available the moment the
        request returns — a `create_task` write can outlive the TestClient's
        event loop and make the numbers non-deterministic. The capturing pool
        stays wired up as tracing's enable gate; nothing is persisted.
        """
        traces.append(trace)

    original_dispatch = agent_tools.dispatch_outcome
    double = ToolDouble(responses or {}, original=original_dispatch)
    http = BlockedHttpClient()

    async def _no_name(*args: Any, **kwargs: Any) -> None:
        return None

    with contextlib.ExitStack() as stack:
        # Memory-only store: no DATABASE_URL means no pool, so no turn write is
        # ever enqueued and no tunnel is needed.
        stack.enter_context(mock.patch.object(config, "database_url", lambda: None))
        stack.enter_context(mock.patch.object(greeting, "fetch_first_name", _no_name))
        stack.enter_context(
            mock.patch.object(agent_tools, "dispatch_outcome", double.dispatch_outcome)
        )
        stack.enter_context(mock.patch.object(tracing, "_schedule_persist", _capture))
        # Tracing IS the usage meter here, so it is forced on for the session
        # rather than left to AGENT_TRACING — an operator with tracing disabled
        # must still get token/INR numbers out of a sweep.
        stack.enter_context(mock.patch.object(config, "tracing_enabled", lambda: True))
        app = create_app()
        tracing.configure()
        client = stack.enter_context(TestClient(app))
        # Replace the shared resources the lifespan installed: tracing needs a
        # pool object to build spans, and nothing may reach an upstream.
        app.state.pg_pool = CapturingPool()
        app.state.http_client = http
        try:
            yield Session(
                app=app, client=client, double=double, traces=traces, http=http
            )
        finally:
            tracing._ENABLED = False
