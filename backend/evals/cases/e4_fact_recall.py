"""E4 — a fact from turn two recalled at turn fourteen.

This is the context-rot metric, measured directly. The user states an amount and
a date at their second message; twelve noisy messages follow (knowledge-base
rounds, a money card, a holdings card, a report-columns round — the
mutually-similar distractor mass Chroma's work identifies as the trigger); the
fourteenth message asks for the amount and date back.

Pass criteria: the reply carries that exact amount and that date, and does not
abstain. Abstention is the failure this case exists to catch: "I cannot
determine the amount — that was not provided" about a figure the transcript
holds.

One fixture choice matters here. The money tool answers with the EMPTY passbook
on the probe turn (`fixtures.MONEY_EMPTY`), because a successful money card is an
artifact and the loop ends an all-artifact round silently (CHO-215) — a recall
case needs the turn to end in narration whatever the model decides to call.

The shared no-abstention assertion applies via `harness.finish`.
"""

from __future__ import annotations

from evals import assertions, fixtures, harness


def run() -> harness.CaseOutcome:
    responses = {
        "search_knowledge_base": harness.ok(fixtures.KB_GENERIC_RESULTS),
        "get_money_transactions": harness.ok(fixtures.MONEY_EMPTY),
        "get_holdings": harness.ok(fixtures.HOLDINGS_FRESH),
        "get_report_columns": harness.PASSTHROUGH,
        "open_report_form": harness.PASSTHROUGH,
    }

    def kb_turn(session: harness.Session, question: str, query: str, answer: str) -> None:
        session.user(question)
        session.tool_round(
            "search_knowledge_base",
            {"query": query},
            envelope=fixtures.KB_GENERIC_RESULTS,
        )
        session.assistant(answer)

    with harness.eval_session(responses) as session:
        # 1
        kb_turn(
            session,
            "how do I add funds to my trading account?",
            "add funds to trading account",
            "Add funds from the FinX app using UPI or net banking from a bank "
            "account registered with your trading account.",
        )
        # 2 — THE FACT
        session.user(fixtures.RECALL_STATEMENT)
        session.assistant(
            "Let me look at the pay-in and pay-out records on your account."
        )
        # 3 — a money card (artifact round, no narration in production)
        session.user("can you check my pay-ins?")
        session.tool_round(
            "get_money_transactions", {}, envelope=fixtures.MONEY_CARD
        )
        # 4
        kb_turn(
            session,
            "what are DP charges?",
            "DP charges",
            "A DP charge is a flat per-scrip charge on each sell transaction, "
            "debited from your demat account.",
        )
        # 5
        kb_turn(
            session,
            "how do I change my registered bank account?",
            "change registered bank account",
            "Raise a bank modification request in the FinX app with a cancelled "
            "cheque or a bank statement.",
        )
        # 6 — a holdings card
        session.user("show me my holdings")
        session.tool_round("get_holdings", {}, envelope=fixtures.HOLDINGS_SPENT)
        # 7 — a report-columns round
        session.user("what does the Balance column in the ledger mean?")
        session.tool_round(
            "get_report_columns",
            {"report": "ledger"},
            envelope=fixtures.report_columns_fresh(),
        )
        session.assistant(
            "Balance is your running ledger balance after the entry."
        )
        # 8
        session.user("thanks, that helps")
        session.assistant("Happy to help. Anything else?")
        # 9
        kb_turn(
            session,
            "what do I do if my login is blocked?",
            "login blocked",
            "Reset the password from the login screen; three wrong attempts "
            "lock the account until a reset.",
        )
        # 10
        kb_turn(
            session,
            "how long does a pay-in take to reflect?",
            "pay-in reflection time",
            "UPI and net-banking pay-ins usually reflect within a few minutes; "
            "NEFT and RTGS follow banking hours.",
        )
        # 11
        kb_turn(
            session,
            "is there a charge for pledging holdings?",
            "pledge charge",
            "A per-ISIN pledge charge applies when holdings are pledged.",
        )
        # 12
        session.user("ok")
        session.assistant("Noted.")
        # 13
        kb_turn(
            session,
            "where do I see my MTF ledger separately?",
            "MTF ledger separate",
            "The ledger report has a Normal book and an MTF book; pick the MTF "
            "book to see only MTF entries.",
        )

        # 14 — the probe
        probe = session.probe(
            "before we go on, remind me: what exact amount and what date did I "
            "give you earlier for that transfer that never showed up?"
        )

    failures: list[str] = []
    observed = {
        "userMessages": sum(
            1 for turn in session.thread.turns if turn.kind == "user_text"
        ),
        "amountEchoed": assertions.contains_amount(probe.text, fixtures.RECALL_AMOUNT),
        "dateEchoed": assertions.contains_date(probe.text, fixtures.RECALL_DATE_ISO),
    }

    if not observed["amountEchoed"]:
        failures.append("amount-not-echoed")
    if not observed["dateEchoed"]:
        failures.append("date-not-echoed")

    return harness.finish(probe, failures, observed)


CASE = harness.Case(
    id="E4",
    title="amount + date stated at turn 2 recalled exactly at turn 14",
    run=run,
    notes="the abstention metric, measured directly",
)
