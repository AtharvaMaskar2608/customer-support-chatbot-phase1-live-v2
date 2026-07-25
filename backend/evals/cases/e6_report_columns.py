"""E6 — report columns are never described from memory.

The standing compliance rule (`prompt.py:186-192`) is absolute: any question
about what a report contains or what a column MEANS must call
`get_report_columns` and answer only from its result, using the labels verbatim.
Mid-thread, with the earlier result spent, that rule is what stops the bot
describing columns a report never had — the grounding bug CHO-228 fixed.

The seeded (spent) result carries two labels the registry does NOT have
(`fixtures.STALE_ONLY_COLUMN_LABELS`), and the probe-turn call runs the REAL
registry-backed core (design D2 permits it — local, credential-free). So there
are two mechanical checks:

* nothing that looks like a column label appears BEFORE the tool call
  (describing first, checking second, is the violation);
* no stale-only label appears anywhere in the reply.

The shared no-abstention assertion applies via `harness.finish`.
"""

from __future__ import annotations

from evals import assertions, fixtures, harness


def run() -> harness.CaseOutcome:
    spent = fixtures.report_columns_spent("ledger")
    fresh = fixtures.report_columns_fresh("ledger")
    spent_labels = fixtures.column_labels(spent)
    fresh_labels = fixtures.column_labels(fresh)

    responses = {
        "get_report_columns": harness.PASSTHROUGH,
        "search_knowledge_base": harness.ok(fixtures.KB_GENERIC_RESULTS),
        "get_holdings": harness.ok(fixtures.HOLDINGS_FRESH),
        "open_report_form": harness.PASSTHROUGH,
    }

    with harness.eval_session(responses) as session:
        session.user("what does my ledger report contain?")
        session.tool_round(
            "get_report_columns", {"report": "ledger"}, envelope=spent
        )
        session.assistant(
            "Your ledger lists "
            + ", ".join(spent_labels[:-1])
            + f" and {spent_labels[-1]} for every entry."
        )

        # Two noisy turns, so the columns result is no longer the latest thing.
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

        session.user("show me my holdings")
        session.tool_round("get_holdings", {}, envelope=fixtures.HOLDINGS_SPENT)

        probe = session.probe("remind me what the Balance column means")

    failures: list[str] = []
    observed: dict = {"staleOnlyLabels": list(fixtures.STALE_ONLY_COLUMN_LABELS)}

    if "get_report_columns" not in probe.tool_names:
        failures.append("get_report_columns-not-recalled")

    described_early = assertions.contains_any(
        probe.text_before_first_tool, set(spent_labels) | set(fresh_labels)
    )
    observed["labelBeforeCall"] = described_early
    if described_early:
        failures.append(f"column-described-before-recall:{described_early}")

    stale = assertions.stale_labels(
        probe.text, seeded=spent_labels, fresh=fresh_labels
    )
    observed["staleLabelsQuoted"] = stale
    if stale:
        failures.append("stale-label:" + ",".join(stale))

    return harness.finish(probe, failures, observed)


CASE = harness.Case(
    id="E6",
    title="report columns re-fetched before any column is described",
    run=run,
    notes="REPORT COLUMNS RULE, prompt.py:186-192",
)
