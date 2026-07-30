## 1. Prompt update

- [x] 1.1 In `backend/app/agent/prompt.py`, extend the existing "call directly... with no preamble text" instruction (currently at `prompt.py:211`, scoped to `get_holdings`/`get_money_transactions`/`get_brokerage_rates`) to explicitly include `search_knowledge_base` and `get_report_columns`.
- [x] 1.2 Make the instruction categorical (no preceding assistant text of any kind before these tool calls), not just a reference to the existing banned-phrase list — the failure mode observed was a fluent factual sentence, not a banned phrase.

## 2. Verify against the eval harness

- [x] 2.1 Check `backend/evals/cases/` (e.g. `e7_kb_followup.py`) for existing assertions about tool-call sequencing/preamble; add or extend a case that asserts zero assistant text precedes a `search_knowledge_base`/`get_report_columns` tool_use block in the same model round. (Nothing existing was categorical — E6 only bans a column *label* before the call, E1 only bans a report-parameter *question*. Added `evals/cases/e8_silent_tool_call.py`: **E8** for `search_knowledge_base` on the original repro question, **E8c** for `get_report_columns`, both asserting the pre-tool text is EMPTY via the new `assertions.preamble_before_tool`.)
- [ ] 2.2 Run the eval harness (`backend/evals/runner.py`) against the updated prompt and confirm no regressions in existing KB/report-column cases.

## 3. Manual verification

- [ ] 3.1 Re-run the original reproduction query ("When does intraday square off happen") against a local backend and confirm the response now shows no assistant text before the tool call — the loading indicator appears first, then one complete grounded answer.
- [ ] 3.2 Spot-check a `get_report_columns`-triggering question (e.g. "what does Net Qty mean in my P&L") for the same silent-call behavior.

## 4. Ship

- [x] 4.1 Confirm the prompt-cache prefix change is expected/acceptable (one cache-miss on first request post-deploy per the design notes) — no action needed beyond awareness. (Measured with `count_tokens` on `claude-sonnet-4-6`, same assembly before/after the edit: **+145 tokens**, cacheable prefix **6,731 → ~6,876**. Recorded in `prompt.py`'s module docstring. CHO-264 tasks 7.2/7.3 quote the old 6,731 for their prod canary and need the new figure when that canary is run.)
