## Why

A live trace (2026-07-28, query "When does intraday square off happen") shows the model's first response emitting a complete, confident factual sentence ("Intraday positions are squared off by your broker's RMS system before market close...") in the SAME turn it requests `search_knowledge_base`. The frontend then shows a "Looking that up…" loading pill *after* that already-complete-reading sentence, before more text streams in — a backwards "answer, then loading, then more answer" sequence that reads as the app glitching rather than still working.

The `agent-loop` spec already asserts the right end state — its "Tool call is silent" scenario states the model "calls `search_knowledge_base` with no preceding assistant text" — but the requirement text backing that scenario ("User-facing voice conceals intermediary steps") only bans specific narration *phrases* ("let me check", "searching for", etc.), not preceding text categorically. A full factual statement isn't one of the banned phrases, so it slips through untouched, and the scenario's guarantee doesn't actually hold in practice. The same gap exists for `get_report_columns`, which has no preamble instruction at all. Meanwhile `get_holdings`/`get_money_transactions`/`get_brokerage_rates` already have an explicit "call directly, with no preamble text" instruction (`prompt.py:211`) — this change brings `search_knowledge_base` and `get_report_columns` in line with that existing, working pattern.

## What Changes

- Tighten the `agent-loop` spec's "User-facing voice conceals intermediary steps" requirement so it explicitly bans ANY preceding assistant text before a `search_knowledge_base` call — not just the enumerated narration phrases — closing the gap between the requirement and its own "Tool call is silent" scenario.
- Extend the "Report columns are registry-grounded" requirement similarly: `get_report_columns` SHALL be called with no preceding assistant text.
- Update `backend/app/agent/prompt.py` to explicitly instruct silent, no-preamble calling for `search_knowledge_base` and `get_report_columns`, matching the existing instruction already given for the zero-parameter data tools (`prompt.py:211`).
- No tool schemas, tool behavior, or frontend code change — this is a prompt/spec-only fix to a sequencing/UX problem.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `agent-loop`: "User-facing voice conceals intermediary steps" — ban any preceding assistant text (not just specific phrases) before `search_knowledge_base`. "Report columns are registry-grounded" — add the same no-preceding-text instruction for `get_report_columns`.

## Impact

- `backend/app/agent/prompt.py` — the only code file touched.
- `openspec/specs/agent-loop/spec.md` — two requirements tightened via this change's delta spec.
- No frontend changes; the existing `showProgress`/`NarratePill` mechanism in `ChatShell.tsx` is unaffected — it will simply have nothing (no premature text) to look confusing next to, once the model stops emitting pre-tool-call sentences.
- Independent of CHO-282/283 (table formatting) and CHO-285 (embedding latency) — this only addresses the sequencing/UX of *when* text appears relative to a tool call, not table formatting or tool call latency.
