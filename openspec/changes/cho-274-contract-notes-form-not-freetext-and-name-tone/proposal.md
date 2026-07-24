# CHO-274: contract-notes-form-not-freetext-and-name-tone

## Why

In long conversations the agent asked for contract-note date ranges in free
text (instead of the guided form) and addressed the user by first name on
almost every reply — both feel broken and irritating.

Root causes: `list_contract_notes` said "ALWAYS call this first… dates
required," which fought the FORM RULE; and the CHO-246 live-context line said
"address them by first name when it reads naturally," which the model treated
as permission to greet by name every turn.

## What

- Align `list_contract_notes` tool description + primed FORM RULE / few-shot
  so missing dates ⇒ `open_report_form flow=contract-notes`, never prose.
- Tighten `_live_context` first-name instruction: at most once per
  conversation; never start routine/consecutive replies with the name.

## Out of scope

- CHO-273 cold-load thread reset.
- Frontend contract-notes flow UI changes.
- Removing `list_contract_notes` (still valid when both dates are known).
