# CHO-227: tax-computation-guardrail

## Why

On 21 July testers found the live bot **computing tax liability in chat**. Given hypothetical lots it ran FIFO, classified each lot's holding period, and quoted:

> *"Total gain = ₹3,00,000 (Long-term) · Tax @ 10% (on gains above ₹1L) = ₹30,000."*

Two defects in one answer:

1. **Compliance.** The system prompt's non-negotiable block ([prompt.py:55](backend/app/agent/prompt.py#L55)) forbids *investment* advice — "no recommendations on buying, selling, holding, or timing" — but is **silent on tax computation**. So the bot computed a customer's tax owed, which is advice-adjacent and a real liability for a broker's support bot.
2. **Correctness.** The `10% over ₹1L` figure is **stale** — India moved listed-equity LTCG to **12.5% over ₹1.25L** for transfers on/after 23 July 2024. And there is **no tax rate anywhere in the KB or config** (grep came back empty), so the number came straight from the model's training memory, ungrounded and out of date.

The prompt already has the exact pattern that prevents this — the **BROKERAGE RULE** ([prompt.py:117](backend/app/agent/prompt.py#L117)): *"any question about brokerage… MUST call get_brokerage_rates and answer from its result — never answer from general knowledge or the knowledge base alone."* This change extends that architecture to tax. If the bot never quotes a rate, it can never quote a stale one — so this closes compliance and correctness in one move.

## What Changes

Add a **TAX RULE** to the agent system prompt, parallel to the BROKERAGE RULE:

- Any question involving **tax or capital-gains figures, holding-period classification, or a tax rate/threshold** routes to the **capital gains report** (`open_report_form` for tax, or `get_capital_gains_report` when fully specified) — the authoritative statement.
- The model MUST NOT: compute gains, apply FIFO/LIFO, classify a specific lot as short- vs long-term for a figure, or state any tax rate or exemption threshold from general knowledge.
- It MAY explain the **concept** in plain terms (what capital gains are; that holding period determines short vs long term) **without producing a figure or a rate** — the instant it becomes a number or a rate, it defers to the report.
- Reinforce in the non-negotiable block: never compute a customer's tax liability or quote tax rates/thresholds; these change with law and are not in our ground truth.
- Add one few-shot example showing the deflection (user hands over lots / asks "how much tax will I owe" → concept + offer the capital gains report, no figure, no rate).

**Design decision (from exploration):** between *refuse-and-route* and *explain-mechanism-but-never-figures*, this takes the latter — the bot stays helpful about what capital gains are, but every number and rate comes from the official statement. Computing "with correct rates" was rejected: it re-introduces the staleness bug the moment tax law shifts.

## Capabilities

### Modified Capabilities

- `agent-loop`: adds a grounding rule that tax/capital-gains figures, holding-period classification, and tax rates are **report-only**, mirroring the existing brokerage grounding rule; and tightens the non-negotiable block to forbid computing tax liability or quoting rates.

## Impact

- **Backend prompt only** — `backend/app/agent/prompt.py` (the routing-rules block + the non-negotiable block + one few-shot). No new tools; the capital gains report flow already exists. No API or frontend change.
- **Prompt-cache note & guard**: the TAX RULE is static text in the frozen instructions (block 0, before breakpoint 2 per CHO-226), so it only *grows* the cached prefix. Caching was runtime-verified active on Haiku on 2026-07-21 — `cache_read_input_tokens: 4664` on the 2nd request; cacheable prefix **4,664** vs the 4,096 floor (~570-token margin). `snapshot_text()`'s hash changes once (expected — a one-time cache re-warm). This change carries a post-edit cache-regression check (tasks 1.4 / 3.5) that re-runs the two-call probe — closing **CHO-226's open task 5.5** — and forbids any interpolated value in the cached block.
- **Tests**: agent-loop assertions that a tax-computation prompt routes to the report and the reply contains no computed figure/rate. Note prompt-behaviour is hard to assert deterministically without live model calls — the strongest guard is a structured check (routes to `open_report_form`/report tool) plus a review gate; flag the limitation rather than over-claiming a unit test.
- Linear: CHO-227 · branch `cho-227-tax-computation-guardrail` · Todo, assigned to Atharva Maskar.

## Out of scope

The P&L-report explanation defect from the same tester round is a **different failure mode** (grounding in an unseeable upstream PDF, not authority overreach) and is tracked separately as **CHO-228** — its fix waits on a look at what the KB actually returns for that question (next iteration).
