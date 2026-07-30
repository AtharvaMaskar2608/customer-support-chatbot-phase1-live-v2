## Context

`backend/app/agent/prompt.py:154-176` (USER-FACING VOICE section) bans specific narration *phrases* before/around tool calls ("let me check", "searching for", mechanism terms, self-narration, retry disclosure). `prompt.py:211` separately gives an explicit "call directly... with no preamble text" instruction, but only for `get_holdings`, `get_money_transactions`, `get_brokerage_rates` (the zero-parameter data tools). Neither `search_knowledge_base` nor `get_report_columns` has that explicit instruction — they're only covered by the phrase-level ban. A live trace showed the model emitting a complete, non-banned-phrase factual sentence before calling `search_knowledge_base`, producing a "confident answer → then a loading ring → then more answer" sequence that reads as broken to the user. The `agent-loop` spec's own "Tool call is silent" scenario already asserts no preceding text should occur here — the prompt just doesn't structurally guarantee it.

## Goals / Non-Goals

**Goals:**
- Make `search_knowledge_base` and `get_report_columns` calls happen with zero preceding assistant text, matching the existing, working pattern already used for the zero-parameter data tools.
- Close the gap between the spec's stated guarantee ("Tool call is silent") and what the prompt actually instructs.

**Non-Goals:**
- Not changing what the model says AFTER the tool result comes back (the existing USER-FACING VOICE bans on mechanism terms/self-narration already govern that, and are untouched).
- Not adding a code-level enforcement mechanism (e.g. a backend check that rejects/strips pre-tool-call text) — this is a prompt-only fix, consistent with how the existing zero-parameter-tool instruction is enforced today (prompt-only, no post-generation filter, per the spec's existing "Enforcement SHALL be via the system/primed prompt... not a post-generation regex filter" line).
- Not addressing the separate embedding-latency issue (CHO-285) or table formatting (CHO-282/283) — this change is purely about sequencing.

## Decisions

**1. Extend the existing "no preamble text" instruction rather than inventing a new mechanism.**
`prompt.py:211` already has working, spec-backed language for this exact problem on other tools. Add `search_knowledge_base` and `get_report_columns` to that same instruction rather than writing a new rule or relying solely on the phrase-ban list. Alternative considered — only add more banned phrases to the USER-FACING VOICE list: rejected, since the observed failure (a genuine factual sentence) isn't a "phrase" that can be enumerated; the fix needs to be categorical ("no text before this tool"), not another entry in a finite ban-list that a sufficiently different sentence will always evade.

**2. Prompt-only enforcement, no backend code change.**
Consistent with the existing spec's explicit choice not to post-filter assistant text (`agent-loop` spec: "Enforcement SHALL be via the system/primed prompt and tool descriptions only"). A code-level filter would also be awkward here: unlike the banned-phrase case (a fixed string list to strip), "was there any text before this specific tool_use block" requires inspecting response structure, and stripping AFTER the fact wouldn't fix the frontend already having rendered it mid-stream — the fix has to happen before generation, i.e. in the prompt.

## Risks / Trade-offs

- **[Risk]** Prompt-only fixes are probabilistic, not guaranteed — the model could still occasionally emit text before the tool call. → **Mitigation**: this is the same enforcement model already used successfully for the zero-parameter tools; no evidence it needs a stronger mechanism here. If recurrence is observed post-deploy, that would be a signal to revisit (out of scope for this change).
- **[Risk]** Tightening the instruction could make the model MORE terse post-answer too, if it over-generalizes "no preamble" beyond the tool-call moment. → **Mitigation**: scope the instruction narrowly to "before calling this tool," mirroring the exact phrasing already used for the zero-parameter tools, which hasn't shown this problem.

## Migration Plan

Prompt text change only — no data migration, no rollback complexity beyond reverting the prompt edit. Note the prompt is byte-stable/cached (per the prompt-caching work in CHO-264/278) — this edit changes the cached prefix, so the next request after deploy pays one cache-miss; expected and unavoidable for any prompt content change.

## Open Questions

- None — this is a small, well-scoped prompt edit with a clear existing pattern to follow.
