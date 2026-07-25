# agent-loop

## ADDED Requirements

### Requirement: The loop sends the curated model context
When curation is enabled the loop SHALL build each model round's history from the store's curated
projection instead of the lossless wire array, so that spent tool-result payloads are replaced by
deterministic stubs before the request is sent. The behaviour SHALL be config-gated by a single
environment flag, **default off at merge** and flipped on only after the routing evals pass, and with
the flag off the assembled messages array SHALL be byte-identical to the pre-change array. Enabling or
disabling curation SHALL NOT change the SSE contract, the artifact payloads, the stored transcript, the
ticket transcript, or the derived conversation counters. Each `llm` trace span SHALL record how many
turns were curated and an estimate of the history token count, so the flag's effect is observable
without a special run.

#### Scenario: Curation is off by default at merge
- **WHEN** the backend runs without the curation flag set
- **THEN** the messages array sent to the model is byte-identical to the pre-change array, and the trace span records zero curated turns

#### Scenario: A stubbed data result makes the model re-call the tool
- **WHEN** the user asks a follow-up about their holdings one turn after the holdings card rendered, and the holdings result has been stubbed
- **THEN** the model re-issues `get_holdings` and answers only from the fresh envelope, quoting no figure that is absent from it

#### Scenario: The model does not abstain over curated history
- **WHEN** the user asks about a fact they stated earlier in a long thread whose tool results have been stubbed
- **THEN** the reply answers from the conversation rather than claiming the information was not provided in the chat history

### Requirement: Curated context preserves the routing signal
The curated projection SHALL preserve the in-context exemplars that drive routing: `open_report_form`
seed envelopes and `raise_support_ticket` results SHALL be sent verbatim for the life of the thread,
and error results SHALL keep their corrective text verbatim. Consequently a mid-conversation report
request SHALL continue to open a seeded guided form rather than asking the user for parameters in
prose, and a stub for a report-columns result SHALL direct the model to call `get_report_columns`
again rather than describing a column from a remembered label.

#### Scenario: Mid-thread follow-up still opens a seeded form
- **WHEN** a ledger report was completed at an earlier turn, several noisy turns have followed, and the user says "now the same for MTF"
- **THEN** the first tool call is `open_report_form` with the carried-over values seeded, and the model asks no clarifying question before calling it

#### Scenario: Column answers stay registry-grounded
- **WHEN** the user asks what a report column means two turns after a `get_report_columns` result was returned and stubbed
- **THEN** the model calls `get_report_columns` again and describes the column only from the fresh result
