"""E1 — mid-thread report parameters (the north star).

A completed ledger flow (form result plus its app-event memo) followed by three
noisy turns, then "now the same for MTF". The FOLLOW-UP rule
(`prompt.py:211-218`) says that must re-open the guided form seeded from the
carried-over values, so the pass criteria are:

* the FIRST tool call is `open_report_form`;
* its input carries `flow=ledger`, `book=MTF`, and the date range from the memo —
  values that exist nowhere in the probe message, only in the seeded history;
* NO report-parameter question in prose precedes the call (asking for a date
  range in text is exactly what the form handover replaced).

`open_report_form` runs its REAL handler (design D2): the core is local and
credential-free, so the artifact carries a genuinely validated seed. The
assertion still reads the model's emitted input, which is where routing lives.

The shared no-abstention assertion applies via `harness.finish`.
"""

from __future__ import annotations

from evals import assertions, fixtures, harness


def run() -> harness.CaseOutcome:
    from_iso, to_iso = fixtures.previous_month_range()
    memo_text, memo_meta = fixtures.ledger_flow_memo(from_iso, to_iso)
    responses = {
        "open_report_form": harness.PASSTHROUGH,
        "get_ledger_report": harness.ok(
            {
                "delivery": "download",
                "file": {
                    "name": "Ledger_MTF.pdf",
                    "sizeLabel": "12 KB",
                    "format": "PDF",
                    "passwordProtected": True,
                },
                "fileToken": "syn-file-token-ledger",
            }
        ),
        "search_knowledge_base": harness.ok(fixtures.KB_GENERIC_RESULTS),
        "get_holdings": harness.ok(fixtures.HOLDINGS_FRESH),
    }

    with harness.eval_session(responses) as session:
        # --- the completed ledger flow -----------------------------------
        session.user("I need my ledger statement")
        session.tool_round(
            "open_report_form",
            {"flow": "ledger"},
            envelope=fixtures.ledger_form_envelope(from_iso, to_iso),
        )
        session.flow_event(memo_text, memo_meta)

        # --- three noisy turns between the flow and the follow-up --------
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

        session.user("how long does a pay-in take to reflect?")
        session.tool_round(
            "search_knowledge_base",
            {"query": "pay-in reflection time"},
            envelope=fixtures.KB_GENERIC_RESULTS,
        )
        session.assistant(
            "UPI and net-banking pay-ins usually reflect within a few minutes; "
            "NEFT and RTGS follow banking hours."
        )

        probe = session.probe("now the same for MTF")

    failures: list[str] = []
    observed: dict = {"expectedRange": [from_iso, to_iso]}

    first = probe.first_tool
    if first is None:
        failures.append("no-tool-call")
    elif first != "open_report_form":
        failures.append(f"first-tool-not-open_report_form:{first}")

    form_inputs = assertions.inputs_for(probe.tool_calls, "open_report_form")
    if form_inputs:
        observed["formInput"] = form_inputs[0]
        mismatches = assertions.field_mismatches(
            form_inputs[0],
            {
                "flow": "ledger",
                "book": "MTF",
                "fromDate": from_iso,
                "toDate": to_iso,
            },
        )
        if mismatches:
            failures.append("seed-mismatch:" + ",".join(mismatches))

    asked = assertions.parameter_question(probe.text_before_first_tool)
    if asked:
        failures.append(f"prose-parameter-question:{asked}")

    return harness.finish(probe, failures, observed)


CASE = harness.Case(
    id="E1",
    title="mid-thread report parameters carry over into a seeded form",
    run=run,
    notes="FOLLOW-UP rule, prompt.py:211-218",
)
