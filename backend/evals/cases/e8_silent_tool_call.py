"""E8 — lookups happen BEFORE any text, not alongside it (CHO-284).

The live trace that opened CHO-284 ("When does intraday square off happen") has
the model emitting a complete, fluent, entirely correct sentence in the SAME
model round it requests `search_knowledge_base`. The frontend streams that text,
then shows its loading pill, then streams the grounded answer — so the user reads
a finished answer, watches a spinner appear underneath it, and then gets a second
answer. It looks like the app glitched.

Nothing in the phrase-level bans catches this: the sentence was not "let me
check" or "searching for", it was a plain factual statement. That is why the
check here is categorical — `assertions.preamble_before_tool` asserts the
pre-tool text is EMPTY, not that it avoided a list of words. A ban-list can
always be evaded by a sufficiently different sentence; emptiness cannot.

Two probes, one per tool named in the spec delta:

* E8 — `search_knowledge_base`, on the original reproduction question. The topic
  is deliberately one the model could answer from general knowledge, which is
  what tempts the premature sentence in the first place.
* E8c — `get_report_columns`, on a column question that names its report (so the
  ambiguous-label branch is not what is being measured).

Both also assert the tool was actually called: "no text before the call" is
vacuous if there was no call. Neither says anything about the reply AFTER the
result — that must stay a full, natural answer, and the shared no-abstention
assertion (via `harness.finish`) is what guards it from collapsing into terse.
"""

from __future__ import annotations

from evals import assertions, fixtures, harness


def _silence_failures(probe: harness.Probe, tool: str) -> tuple[list[str], dict]:
    """The shared verdict: `tool` was called, and nothing preceded the call."""
    failures: list[str] = []
    observed: dict = {}

    if tool not in probe.tool_names:
        failures.append(f"{tool}-not-called")

    preamble = assertions.preamble_before_tool(probe.text_before_first_tool)
    observed["preambleBeforeTool"] = preamble
    if preamble:
        failures.append(f"preamble-before-tool:{preamble}")

    return failures, observed


def run() -> harness.CaseOutcome:
    responses = {
        "search_knowledge_base": harness.ok(fixtures.KB_INTRADAY_RESULTS),
        "get_holdings": harness.ok(fixtures.HOLDINGS_FRESH),
        "open_report_form": harness.PASSTHROUGH,
    }

    with harness.eval_session(responses) as session:
        # A short, ordinary lead-in — the reproduction was an early turn, not a
        # long-context failure, so the thread is kept close to what was traced.
        session.user("hi")
        session.assistant("Hi! Ask me anything about your FinX account.")

        probe = session.probe("When does intraday square off happen")

    failures, observed = _silence_failures(probe, "search_knowledge_base")
    return harness.finish(probe, failures, observed)


def run_columns() -> harness.CaseOutcome:
    responses = {
        "get_report_columns": harness.PASSTHROUGH,
        "search_knowledge_base": harness.ok(fixtures.KB_GENERIC_RESULTS),
        "open_report_form": harness.PASSTHROUGH,
    }

    with harness.eval_session(responses) as session:
        session.user("hi")
        session.assistant("Hi! Ask me anything about your FinX account.")

        probe = session.probe("what does the Net Qty column mean in my P&L report?")

    failures, observed = _silence_failures(probe, "get_report_columns")
    return harness.finish(probe, failures, observed)


CASE = harness.Case(
    id="E8",
    title="search_knowledge_base is called with zero text before it",
    run=run,
    notes="NO PREAMBLE BEFORE A TOOL CALL, prompt.py (CHO-284)",
)

CASE_COLUMNS = harness.Case(
    id="E8c",
    title="get_report_columns is called with zero text before it",
    run=run_columns,
    notes="NO PREAMBLE BEFORE A TOOL CALL, prompt.py (CHO-284)",
)
