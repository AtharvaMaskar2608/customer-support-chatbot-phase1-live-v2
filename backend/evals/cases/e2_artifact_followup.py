"""E2 — follow-up after a spent data card.

A holdings card was rendered, one turn of other business happened, and now the
user asks what a position is worth. The card is spent: its figures are a
snapshot, not the truth, so the model must re-call `get_holdings` and must not
quote the old numbers.

The fresh envelope carries deliberately different market values from the seeded
one (`fixtures.HOLDINGS_SPENT` vs `HOLDINGS_FRESH`), which is what makes "quoted
a stale figure" a value comparison rather than a judgement call. The check runs
over ALL text the probe turn emitted, including anything said BEFORE the tool
call — a recital from memory almost always lands there.

Note on the terminal shape: a successful holdings call is an artifact, and the
loop ends an all-artifact round silently (CHO-215), so a correct attempt often
emits no assistant text at all. That is production behaviour; the routing
assertion is what carries the case in that shape.

The shared no-abstention assertion applies via `harness.finish`.
"""

from __future__ import annotations

from evals import assertions, fixtures, harness


def run() -> harness.CaseOutcome:
    responses = {
        "get_holdings": harness.ok(fixtures.HOLDINGS_FRESH),
        "search_knowledge_base": harness.ok(fixtures.KB_GENERIC_RESULTS),
    }

    with harness.eval_session(responses) as session:
        session.user("show me my holdings")
        # An artifact round: in production no assistant text follows the card.
        session.tool_round("get_holdings", {}, envelope=fixtures.HOLDINGS_SPENT)

        # One intervening turn, so the card is no longer the latest thing said.
        session.user("what are DP charges?")
        session.tool_round(
            "search_knowledge_base",
            {"query": "DP charges"},
            envelope=fixtures.KB_GENERIC_RESULTS,
        )
        session.assistant(
            "A DP charge is a flat per-scrip charge on each sell transaction, "
            "debited from your demat account."
        )

        probe = session.probe("what is my TCS position worth right now?")

    failures: list[str] = []
    observed: dict = {}

    if "get_holdings" not in probe.tool_names:
        failures.append("get_holdings-not-recalled")

    stale = assertions.stale_figures(
        probe.text,
        seeded=fixtures.HOLDINGS_SPENT_FIGURES,
        fresh=fixtures.HOLDINGS_FRESH_FIGURES,
    )
    observed["staleFigures"] = stale
    if stale:
        failures.append("stale-figure:" + ",".join(stale))

    return harness.finish(probe, failures, observed)


CASE = harness.Case(
    id="E2",
    title="spent holdings card is re-fetched, never quoted from memory",
    run=run,
)
