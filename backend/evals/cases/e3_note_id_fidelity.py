"""E3 — contract-note id fidelity, plus the expiry-recovery sub-case.

**What this measures, and what it does not (design D6).** Contract-note ids are
session-bound capability tokens with a 600-second TTL
(`ContractNoteRefStore(ttl_seconds=600.0)`, `contract_notes.py:142`). Under the
doubled tool layer the ids here are SYNTHETIC, so the case asserts **id fidelity
only** — every emitted id string-matches an id that was returned to the model,
and no id is invented. It is not evidence that the download path works. The
report records the seed→probe elapsed seconds precisely so a reviewer can tell
whether a variant run against real ids would have fallen inside the window.

Two cases live here:

* **E3** — a spent list of twenty notes plus three noisy turns, then "download
  the 14 June one". Hard-fail (3/3): a fabricated capability token is the kind of
  miss that is an incident, not a flake. The probe-turn list double returns the
  SAME ids as the seed, so re-listing (legitimate, even cautious) does not change
  the id space the fidelity check works over.
* **E3r** — the recovery path. A download already bounced because its id expired.
  The model must re-list rather than invent an id, and the fresh list carries
  DIFFERENT ids so an invented or recycled one is detectable.

The shared no-abstention assertion applies to both via `harness.finish`.
"""

from __future__ import annotations

from evals import assertions, fixtures, harness

_NOTE_DATE_BY_ID = {
    note["id"]: note["date"]
    for note in list(fixtures.CONTRACT_NOTES_SPENT["notes"])
    + list(fixtures.CONTRACT_NOTES_FRESH["notes"])
}


def _noisy_turns(session: harness.Session) -> None:
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

    session.user("how do I change my registered bank account?")
    session.tool_round(
        "search_knowledge_base",
        {"query": "change registered bank account"},
        envelope=fixtures.KB_GENERIC_RESULTS,
    )
    session.assistant(
        "Raise a bank modification request in the FinX app with a cancelled "
        "cheque or a bank statement."
    )


def run_id_fidelity() -> harness.CaseOutcome:
    from_iso, to_iso = fixtures.NOTES_RANGE
    responses = {
        # Same ids as the seed: a cautious re-list must not move the goalposts.
        "list_contract_notes": harness.ok(fixtures.CONTRACT_NOTES_SPENT),
        "download_contract_note": harness.ok(fixtures.CONTRACT_NOTE_FILE),
        "search_knowledge_base": harness.ok(fixtures.KB_GENERIC_RESULTS),
        "get_holdings": harness.ok(fixtures.HOLDINGS_FRESH),
        "open_report_form": harness.PASSTHROUGH,
    }

    with harness.eval_session(responses) as session:
        session.user("list my contract notes for June 2026")
        session.tool_round(
            "list_contract_notes",
            {"fromDate": from_iso, "toDate": to_iso},
            envelope=fixtures.CONTRACT_NOTES_SPENT,
        )
        session.assistant(
            "There are 20 contract notes for June 2026. Tell me which date you "
            "want and I will pull that one."
        )
        _noisy_turns(session)

        probe = session.probe("download the 14 June one")

    failures: list[str] = []
    observed: dict = {"targetNoteDate": fixtures.TARGET_NOTE_DATE}

    emitted = assertions.emitted_ids(probe.tool_calls, "download_contract_note")
    observed["emittedIds"] = emitted
    observed["pickedNoteDates"] = [_NOTE_DATE_BY_ID.get(value) for value in emitted]
    # Informational, deliberately not a failure: the spec scopes this case to
    # fidelity, so picking the wrong date is reported, not gated.
    observed["pickedTargetNote"] = fixtures.TARGET_NOTE_ID in emitted

    if "download_contract_note" not in probe.tool_names:
        failures.append("download_contract_note-not-called")
    elif not emitted:
        failures.append("download-called-without-id")

    invented = assertions.invented_ids(
        probe.tool_calls, "download_contract_note", fixtures.SPENT_NOTE_IDS
    )
    observed["inventedIds"] = invented
    if invented:
        failures.append(f"invented-ids:{len(invented)}")

    return harness.finish(probe, failures, observed)


def run_expiry_recovery() -> harness.CaseOutcome:
    from_iso, to_iso = fixtures.NOTES_RANGE
    responses = {
        # A DIFFERENT id space on the fresh list: recycling the expired id or
        # inventing one is then detectable.
        "list_contract_notes": harness.ok(fixtures.CONTRACT_NOTES_FRESH),
        "download_contract_note": harness.ok(fixtures.CONTRACT_NOTE_FILE),
        "search_knowledge_base": harness.ok(fixtures.KB_GENERIC_RESULTS),
        "open_report_form": harness.PASSTHROUGH,
    }

    with harness.eval_session(responses) as session:
        session.user("list my contract notes for June 2026")
        session.tool_round(
            "list_contract_notes",
            {"fromDate": from_iso, "toDate": to_iso},
            envelope=fixtures.CONTRACT_NOTES_SPENT,
        )
        session.assistant(
            "There are 20 contract notes for June 2026. Which date would you like?"
        )
        session.user("the 14 June one")
        # The bounce: the id aged out of the 600-second window.
        session.tool_round(
            "download_contract_note",
            {"id": fixtures.TARGET_NOTE_ID},
            error=fixtures.EXPIRED_NOTE_MESSAGE,
        )
        session.assistant(
            "That note is not available to download any more — the earlier "
            "selection has expired."
        )

        probe = session.probe("please try that download again")

    failures: list[str] = []
    observed: dict = {}

    if "list_contract_notes" not in probe.tool_names:
        failures.append("list_contract_notes-not-reissued")
    elif probe.first_tool != "list_contract_notes":
        failures.append(f"first-tool-not-relist:{probe.first_tool}")

    allowed = tuple(fixtures.SPENT_NOTE_IDS) + tuple(fixtures.FRESH_NOTE_IDS)
    emitted = assertions.emitted_ids(probe.tool_calls, "download_contract_note")
    invented = assertions.invented_ids(
        probe.tool_calls, "download_contract_note", allowed
    )
    observed["emittedIds"] = emitted
    observed["inventedIds"] = invented
    if invented:
        failures.append(f"invented-ids:{len(invented)}")

    return harness.finish(probe, failures, observed)


CASE = harness.Case(
    id="E3",
    title="contract-note id fidelity — zero invented ids",
    run=run_id_fidelity,
    hard_fail=True,
    notes="synthetic ids; fidelity only (design D6). 600s TTL applies to real runs.",
)

CASE_RECOVERY = harness.Case(
    id="E3r",
    title="expired note id recovers by re-listing, never by inventing",
    run=run_expiry_recovery,
)
