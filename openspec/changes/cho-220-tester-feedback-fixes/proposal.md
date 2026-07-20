# CHO-220 · Tester Feedback Fixes

## Why

First production tester feedback (19 Jul evening, via Rohan) surfaced four real issues, triaged against the live system: KB answers ramble; the bot *refuses* account-closure questions even though the KB has a 9-entry Account Closure topic (Haiku reads "delete my account" as an unperformable action instead of a process question); the product claims report PDFs are PAN-password-protected but tester-opened PDFs are not (upstream doesn't encrypt them — the claim is ours and it's wrong); and pay-in/pay-out reportedly failed during evening testing (diagnosis from prod logs in scope). Explicitly out of scope per user: customer-care number in the KB, ticket-status lookup.

## What Changes

- **Prompt — concise, non-refusing knowledge answers**: KB narration leads with the direct answer (≈1–3 short sentences; detail only on request). The prompt gains the KB's REAL topic catalog (18 topics incl. Account Closure) plus a hard rule: process/how-to questions are always answered from the KB — the bot never refuses a how-to as "can't do that"; for account actions it cannot perform, it explains the process and offers a ticket.
- **PAN claims removed everywhere** (tester-verified false): backend `passwordProtected` flags → `False` (P&L, ledger, tax), file-card `password: PAN` notes and "Sealing with your PAN…" narration dropped, help copy rewritten, prompt/tool-description mentions removed. Contract notes were already claim-free.
- **Pay-in/pay-out diagnosis**: harvest prod logs for the reported failure; fix here if it's ours, document if it's session-expiry during testing.

## Capabilities

### Modified Capabilities

- `agent-loop`: adds the concise/non-refusing knowledge-answer requirement (prompt-enforced, KB catalog enumerated).
- `pnl-report-flow`, `ledger-report-flow`, `capital-gains-report-flow`: result presentation loses the PAN-password claims.
- `report-chat-shell`: narration example and artifact-caption wording lose PAN references.

## Impact

- Backend: `app/agent/prompt.py` (catalog + brevity + refusal rule; PAN line), `app/agent/tools.py` (descriptions), `app/{report,reports/ledger,reports/tax}.py` (flags). Frontend: `flows/{pnl,ledger,tax}.ts`, `chat/messages.ts`, `chat/ChatShell.tsx`. Tests updated where they assert the old copy/flags.
- No schema, config, or API-shape changes (the `passwordProtected` field remains in envelopes, now truthfully `false`).
