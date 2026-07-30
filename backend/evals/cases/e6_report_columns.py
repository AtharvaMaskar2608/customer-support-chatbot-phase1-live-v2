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

    # Cheap CHO-282 guard: even a one-column answer must not reach for a table.
    table = assertions.pipe_table(probe.text)
    observed["pipeTable"] = table
    if table:
        failures.append(f"pipe-table:{table}")

    return harness.finish(probe, failures, observed)


def run_multi() -> harness.CaseOutcome:
    """E6t — the whole column list comes back as records, never as a table.

    A one-column question (E6 above) gives the model no reason to reach for a
    table; asking for EVERY column is what does, and it is the shape CHO-282 was
    opened for. Two mechanical checks on the reply:

    * no GFM pipe-table signature anywhere — the chat is a ~310–420px column in
      every context it renders in, so a table lands either as literal `|`/`-`
      text or as CHO-282's cramped scrollable fallback;
    * bold headlines are actually present, so "no table" is satisfied by the
      record convention rather than by a run-on paragraph that merely avoids
      pipes.

    The registry-backed core runs for real (design D2), so the labels the model
    is formatting are the genuine ledger ones.
    """
    responses = {
        "get_report_columns": harness.PASSTHROUGH,
        "search_knowledge_base": harness.ok(fixtures.KB_GENERIC_RESULTS),
        "open_report_form": harness.PASSTHROUGH,
    }

    with harness.eval_session(responses) as session:
        session.user("hi")
        session.assistant("Hi! Ask me anything about your FinX account.")

        probe = session.probe("explain what every column in my ledger report means")

    failures: list[str] = []
    observed: dict = {}

    if "get_report_columns" not in probe.tool_names:
        failures.append("get_report_columns-not-called")

    table = assertions.pipe_table(probe.text)
    observed["pipeTable"] = table
    if table:
        failures.append(f"pipe-table:{table}")

    # Paired bold markers — one per record headline under the convention.
    headlines = (probe.text or "").count("**") // 2
    observed["boldHeadlines"] = headlines
    if headlines < 2:
        failures.append(f"record-headlines-missing:{headlines}")

    return harness.finish(probe, failures, observed)


CASE = harness.Case(
    id="E6",
    title="report columns re-fetched before any column is described",
    run=run,
    notes="REPORT COLUMNS RULE, prompt.py:186-192",
)

CASE_MULTI = harness.Case(
    id="E6t",
    title="a multi-column answer uses records, not a markdown table",
    run=run_multi,
    notes="MULTI-FACT REPLIES USE RECORD SHAPE, prompt.py (CHO-282)",
)
