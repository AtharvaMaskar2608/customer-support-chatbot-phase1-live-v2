"""E7 — pronoun follow-up after a knowledge-base answer.

"Tell me more about that", one turn after a KB exchange about MTF interest. The
model has to resolve "that" from the history and re-issue
`search_knowledge_base` with a query carrying a content word from the earlier
exchange — a bare pronoun query retrieves nothing useful.

This is the case that decides whether the `question` strings a curated KB stub
preserves are sufficient grounding: with the full envelope spent, the pronoun
can only be resolved from whatever the curated form kept.

The shared no-abstention assertion applies via `harness.finish`.
"""

from __future__ import annotations

from evals import assertions, fixtures, harness


def run() -> harness.CaseOutcome:
    responses = {
        "search_knowledge_base": harness.ok(fixtures.KB_MTF_RESULTS),
        "get_holdings": harness.ok(fixtures.HOLDINGS_FRESH),
        "open_report_form": harness.PASSTHROUGH,
    }

    with harness.eval_session(responses) as session:
        session.user("why was MTF interest charged on my account?")
        session.tool_round(
            "search_knowledge_base",
            {"query": "MTF interest charges"},
            envelope=fixtures.KB_MTF_RESULTS,
        )
        session.assistant(
            "MTF positions carry a daily funding interest on the funded amount, "
            "charged from the day after the trade until the position is squared "
            "off or converted to delivery."
        )

        # One intervening turn.
        session.user("show me my holdings")
        session.tool_round("get_holdings", {}, envelope=fixtures.HOLDINGS_SPENT)

        probe = session.probe("tell me more about that")

    failures: list[str] = []
    observed: dict = {}

    kb_inputs = assertions.inputs_for(probe.tool_calls, "search_knowledge_base")
    queries = [str(payload.get("query") or "") for payload in kb_inputs]
    observed["kbQueries"] = queries

    if not kb_inputs:
        failures.append("search_knowledge_base-not-reissued")
    else:
        grounded = any(
            assertions.contains_any(query, fixtures.KB_CONTENT_WORDS)
            for query in queries
        )
        observed["grounded"] = grounded
        if not grounded:
            failures.append("query-not-grounded")

    return harness.finish(probe, failures, observed)


CASE = harness.Case(
    id="E7",
    title="pronoun follow-up re-issues a grounded knowledge-base query",
    run=run,
)
