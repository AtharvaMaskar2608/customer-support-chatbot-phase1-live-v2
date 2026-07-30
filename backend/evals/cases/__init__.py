"""The gate cases (CHO-276 · task 2), one module per case.

`ALL_CASES` is the registry the runner sweeps, in gate order. E5 — the
ticket-affirmation guard — is deliberately ABSENT: `raise_support_ticket` has no
dry-run mode, so a live attempt at the guard's rejection branch would file real
Freshdesk tickets exactly when the guard is broken. It lives in the normal test
suite instead (`backend/tests/test_agent_loop.py`), where respx makes "zero POSTs
to /tickets" a first-class assertion.
"""

from evals.cases import (
    e1_report_params,
    e2_artifact_followup,
    e3_note_id_fidelity,
    e4_fact_recall,
    e6_report_columns,
    e7_kb_followup,
    e8_silent_tool_call,
)

ALL_CASES = (
    e1_report_params.CASE,
    e2_artifact_followup.CASE,
    e3_note_id_fidelity.CASE,
    e3_note_id_fidelity.CASE_RECOVERY,
    e4_fact_recall.CASE,
    e6_report_columns.CASE,
    e7_kb_followup.CASE,
    e8_silent_tool_call.CASE,
    e8_silent_tool_call.CASE_COLUMNS,
)

CASES_BY_ID = {case.id: case for case in ALL_CASES}

# Proven in pytest, never live — see the module docstring.
PYTEST_ONLY_CASES = {
    "E5": (
        "ticket-affirmation guard — backend/tests/test_agent_loop.py"
        "::test_unaffirmed_model_ticket_is_rejected_with_zero_freshdesk_requests"
    )
}
