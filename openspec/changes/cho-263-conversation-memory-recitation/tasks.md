# CHO-263: conversation-memory-recitation — tasks

## 1. Decide whether to build (the gate)

- [ ] 1.1 Confirm CHO-271 has shipped with `AGENT_CONTEXT_CURATION=1` on prod
- [ ] 1.2 Re-run CHO-276 eval E1 (mid-thread report follow-up opens a seeded guided form) and E4 (fact stated at turn 2 recalled at turn 14), 3 attempts each, with curation on
- [ ] 1.3 If both pass: close CHO-263 as not-needed, record the measured pass rates and the history-composition numbers in the Linear comment, and stop here
- [ ] 1.4 If either fails: record which, with the failing transcripts, and continue

## 2. Deterministic recitation renderer

- [ ] 2.1 Renderer that walks `thread.turns` and collects the facts to recite: `flow_event` `meta["slots"]` (+ `flow`, `delivery`, `outcome`), the latest `open_report_form` seed, and any open request not yet satisfied
- [ ] 2.2 Render one `<system-reminder>` block — slot labels, flow names, ISO dates and short open-request summaries only; never currency amounts, credentials, file tokens, masked contacts or upstream fields
- [ ] 2.3 Pure and byte-stable: no model call, no clock read, no request state — the same thread state renders the same bytes
- [ ] 2.4 Return nothing when there is nothing to recite (fresh thread, or no flow events and no open request)

## 3. Loop integration

- [ ] 3.1 `loop.py`: append the block after all history, beside the existing escalation / wrapup reminders (`:305-308`) so it sits after every cache breakpoint
- [ ] 3.2 Never stored — the block must not appear in `thread.turns` or in any persisted turn
- [ ] 3.3 Order the trailing blocks explicitly (recitation relative to the reminders) and pin that order in a test

## 4. Tests

- [ ] 4.1 Golden block for a thread with one completed form flow (slots + ISO dates listed)
- [ ] 4.2 Golden block for a no-data flow event and for a thread with an open unsatisfied request
- [ ] 4.3 Block absent on a fresh thread — request bytes identical to the no-block path
- [ ] 4.4 Placement: every message before the trailing block is byte-identical with and without the block, so the cached prefix cannot churn
- [ ] 4.5 Byte stability: two assemblies of the same thread state produce identical block bytes
- [ ] 4.6 Never stored: after a turn with the block, no stored turn contains `<system-reminder>`
- [ ] 4.7 Content guard: the block contains no currency symbol-bearing slot value, no credential, no file token
- [ ] 4.8 `cd backend && uv run pytest` green (existing request-assembly and reminder tests updated for the extra trailing block)

## 5. Eval verification

- [ ] 5.1 Re-run the failing CHO-276 case(s) with the block on: must flip to pass, ≥2/3 attempts
- [ ] 5.2 No regression on the other CHO-276 cases, and zero abstention-regex matches
- [ ] 5.3 Confirm prod traces show no change in `cache_read` ratio (the block is post-breakpoint, so the cached prefix must be unaffected)

## 6. Ship & sync

- [ ] 6.1 `git-sync` with issue key CHO-263
- [ ] 6.2 `linear-connector` — summary comment + state on merge (or the not-needed closure from 1.3, with the measurements)
