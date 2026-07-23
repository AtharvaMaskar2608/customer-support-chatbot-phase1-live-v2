# CHO-252: followup-seeded-form — tasks

## 1. Re-route follow-ups through the seeded form

- [ ] 1.1 In `backend/app/agent/prompt.py`, reword the report slot-filling instruction: execute a report tool directly ONLY when the user states every parameter (incl. delivery) in the CURRENT message; when values are carried over from a prior flow event (follow-up / "same for …"), call `open_report_form` seeded with them instead
- [ ] 1.2 Add/adjust the few-shot guidance so "now the same for MTF" and "now the same for ledger" open a seeded, editable form (not a direct file), and cross-report "same" maps the period onto the target flow (relying on the form validator to drop inapplicable fields)
- [ ] 1.3 Keep the fully-specified single-message path executing directly (unchanged)

## 2. Verification

- [ ] 2.1 `cd backend && uv run pytest` green (update any agent/prompt snapshot or follow-up transcript test; the prompt-hash change is expected)
- [ ] 2.2 Manual: generate a Normal ledger, then "now the same for MTF" → a seeded, editable ledger FlowCard appears (MTF + carried range); nothing generates until delivery is tapped
- [ ] 2.3 Manual: after a P&L, "now the same for ledger" → seeded ledger form asking for the book, no auto-generation
- [ ] 2.4 Confirm a one-message "F&O P&L 1–30 June 2026, download" still executes directly (no form)

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-252
- [ ] 3.2 `linear-connector` — summary comment + state on merge
