# CHO-227: tax-computation-guardrail — tasks

> Implementation deferred to the next iteration (this was captured in explore mode). Do the prompt edit outside explore mode.

## 1. Prompt: the TAX RULE

- [ ] 1.1 In `backend/app/agent/prompt.py`, add a TAX RULE to the routing-rules block, modelled on the BROKERAGE RULE: tax/capital-gains figures, holding-period classification, and tax rates are report-only — route to `open_report_form` (tax) / `get_capital_gains_report`; never compute or quote a rate from general knowledge.
- [ ] 1.2 Permit concept-level explanation with no figure and no rate (what capital gains are; holding period → short vs long term); the moment it is a number or a rate, defer to the report.
- [ ] 1.3 Reinforce the non-negotiable block: never compute a customer's tax liability or quote a tax rate/threshold.
- [ ] 1.4 Placement discipline (prompt-cache): the TAX RULE is STATIC text in `PRIMED_INSTRUCTIONS` (block 0, before breakpoint 2 — beside the BROKERAGE RULE at line 117), never after a breakpoint and with NO interpolated/volatile value; the IST status line stays LAST. Static text here only grows the cached prefix.

## 2. Few-shot

- [ ] 2.1 Add one example: user supplies lots / asks "how much tax will I owe" → the model explains capital gains come from the official statement, offers the capital gains report (form), and gives NO computed figure and NO rate.

## 3. Verification

- [ ] 3.1 Structured check: a tax-computation prompt results in a route to the tax report flow, not an inline computation.
- [ ] 3.2 Confirm the reply carries no rate/threshold string (regex guard on the known-stale patterns: "10%", "12.5%", "₹1L"/"1.25", "LTCG @").
- [ ] 3.3 `snapshot_text()` hash changes exactly once (expected — prompt edit); existing prompt/agent tests updated to the new snapshot.
- [ ] 3.4 `cd backend && uv run pytest`.
- [ ] 3.5 Prompt-cache regression guard (also closes CHO-226 task 5.5): after the edit, re-run the two-call probe on Haiku — the cacheable prefix (system + tools + primed bp2 block) must stay ≥ 4096 tokens (verified baseline **4,664** on 2026-07-21; the TAX RULE only grows it), call 1 shows `cache_creation_input_tokens > 0`, call 2 shows `cache_read_input_tokens > 0`. Keep the probe repeatable so a future prompt edit that silently breaks caching fails loudly.

## 4. Ship & sync

- [x] 4.1 CHO-227 minted in Linear — Todo, assigned to Atharva Maskar, branch `cho-227-tax-computation-guardrail`.
- [ ] 4.2 `git-sync` with issue key CHO-227.
- [ ] 4.3 `linear-connector` — summary comment + state on merge.
