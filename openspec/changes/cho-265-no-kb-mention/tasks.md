# CHO-265: no-kb-mention — tasks

## 1. USER-FACING VOICE prompt block

- [x] 1.1 In `backend/app/agent/prompt.py`, add a **USER-FACING VOICE** subsection to `PRIMED_INSTRUCTIONS` with the five banned categories (mechanism, process narration, retry disclosure, process-tied uncertainty/guessing-after-miss, self-narration) from CHO-265 — include the full Linear phrase lists — plus allowed miss-phrasing templates
- [x] 1.2 Document the narrowed uncertainty rule in that block: ban hedges when narrating lookup confidence, papering over empty/failed lookup, or inventing likely causes; do not globally forbid soft language in clean factual answers
- [x] 1.3 Consolidate or replace the scattered one-liner ("Never narrate retrieval or internal steps…") so voice rules live in one place; keep CHO-241 ticket narration / offer-never-decide intact
- [x] 1.4 Soften primed tool-list / brokerage-fallback wording that tells the model what to *say* about the knowledge base, without changing routing semantics
- [x] 1.5 Add one compact few-shot `<example>` if token budget allows: how-to → silent tool call → direct answer; or miss → allowed phrasing + ticket offer

## 2. Tool description rewrite

- [x] 2.1 In `backend/app/agent/tools.py`, rewrite `search_knowledge_base` description — no "knowledge base", "search results", or "Summarize the results"; frame as fetching support answers for general product/process questions; keep the tool name unchanged
- [x] 2.2 Soften other tool descriptions that cross-reference KB in user-leakable wording (e.g. `get_brokerage_rates` "prefer search_knowledge_base" line) so the model is less likely to echo mechanism nouns

## 3. Verification

- [x] 3.1 `cd backend && uv run pytest` green — update prompt snapshot test if present; extend a test asserting USER-FACING VOICE / banned phrases appear in `PRIMED_INSTRUCTIONS` / `snapshot_text()` when applicable
- [x] 3.2 Manual spot-check against Jam theme: (a) general how-to with a hit — direct answer, no banned phrases; (b) obscure / outside-shares cost-price style miss — allowed miss phrasing + optional ticket ask, no KB/search/retry/likely/may-involve/let-me-raise

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-265 (branch `cho-265-no-kb-mention`)
- [ ] 4.2 `linear-connector` — summary comment + state on merge
