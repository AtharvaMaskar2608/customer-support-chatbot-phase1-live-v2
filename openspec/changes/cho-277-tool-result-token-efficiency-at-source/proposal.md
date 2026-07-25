# CHO-277: tool-result-token-efficiency-at-source

## Why

CHO-271 shrinks history at **read time** — a spent tool_result becomes a stub from the next user turn onward. It can never touch the **first** round, because a tool_result is always verbatim in the turn that fetched it. This change shrinks the envelopes **at birth**, which is the only lever on that first-round cost, and the one cost component prompt caching cannot help either (a freshly appended block is always a cache write, never a read).

Two measured envelopes carry almost all of it:

- **Money.** `money.py:61` `_PAGE_SIZE = 500` is **per direction** — it is sent as `"NoOfRecords"` at `:90` on both the pay-in and pay-out calls — so one `get_money_transactions` tool_result can legitimately reach **~67,000 tokens**, ten times the entire cached prompt prefix. That is not the typical case, but the typical case is already bad: a real, live-verified **72-transaction** envelope measures **4,889 tokens** (12,445 chars at 2.55 chars/token), which is **₹12.75 — about 30% of a 15-turn conversation's entire ₹42.35 bill** — because it is re-billed on all nine model calls that follow it.
- **Knowledge base.** `top_k=10` (CHO-267's deliberate recall default) returns ten **full** Q&A answers: mean **940 tokens**, p90 1,265, and on a topic-clustered draw — which is what RRF fusion actually produces — p99 **~2,600**. Those ten results are mutually similar by construction, and mutually-similar distractors are the **worst** kind for context rot (Chroma: a single distractor already degrades recall; similarity compounds it). So the KB envelope is both the second-largest cost line and the highest-quality noise in the context.

This is the "token-efficient tool **results**" row that the doc→implementation map marks **Missing**: no row cap, no truncation, and no model-versus-UI field split anywhere in the codebase. Anthropic's own tool-writing guidance is explicit — *"implement some combination of pagination, range selection, filtering, and/or truncation with sensible default parameter values for any tool responses that could use up lots of context"* — and their measured `concise`/`detailed` response-format example went **206 tokens → 72**.

## What Changes

- **A model-facing projection seam in the dispatcher.** `tools.py:489-493` builds both paths from one object: `content=json.dumps(result, …)` (what the model and the store see) and `envelope=result` (what `loop.py:145-178` turns into the SSE artifact). A per-tool optional `model_view` on the `Tool` dataclass is applied to `content` only, defaulting to identity. The artifact path reads `.envelope` and is therefore **untouched by construction** — the pinned SSE contract cannot move. Flow cores stay unchanged, so `POST /api/data/money` and every route test keep the full envelope.
- **Money: bound the model-facing rows, keep the card whole.** The model view keeps `kind`, `counts`, `landed`, `totalRecords` and `partial` **verbatim** — these are already derived server-side over the *full* merged stream (`money.py:179-200`), so every aggregate the model needs to answer "how much landed", "how many are pending", "how many transactions are there" stays exact — and truncates `txns` to the **most recent 25** (the stream is already newest-first from `_merged_stream`, so this is a slice, not a re-sort), plus `txnsShown` / `txnsTotal` and one explicit omission sentence. Measured effect: the 72-txn envelope drops **4,889 → ~1,780 tokens**; the page-size ceiling drops **~67,000 → ~1,780**, i.e. the tail risk stops being a tail.
- **The omission sentence must not invite a re-call.** `get_money_transactions` is zero-slot (`_EMPTY_SCHEMA`) — the model cannot ask for more rows, and a re-call returns the same bounded view. The wording therefore states what is true and actionable: the aggregates cover all *n* transactions, the older rows are on the card the user is already looking at, and the user can expand it. This matters because the failure mode we are guarding against is **abstention**, and a bare "some rows were removed" is exactly the phrasing that triggers it.
- **KB: a `response_format` enum, defaulting to the cheaper form.** `search_knowledge_base` / `POST /api/kb/search` gain `response_format: "concise" | "detailed"`, default **`concise`**. `detailed` reproduces today's field set exactly (`id, topic, section, question, answer, tat, score`) so nothing is ever unavailable; `concise` returns the same `top_k` results in the same fused-score order, each carrying `id`, `topic`, `section` and `question`, with the **full `answer` (and `tat`) on the top 3** and answers omitted below that, `score` dropped, and a 1,200-character bound on any retained answer flagged `truncated`. Estimated mean: **~940 → ~360 tokens**; the win is larger on the p99 draws, because the mass is entirely in answer bodies (answer mean 174 chars, p99 1,548, max 3,010 — versus question 43, topic 8, section 23).
- **Trace fidelity is preserved.** The KB projection is applied in `run_kb_search` **after** `tracing.observe_retrieval` returns, so `metadata.retrieval_context` still carries the full `question — answer` chunk list and CHO-267's trace-viewer chunk view is unaffected.
- **Doc drift fixed while nearby:** `docs/api_doc/api_documentation.md:375` still says KB `top_k` defaults to 5; it has been 10 since CHO-267.

Interaction with the rest of the programme: every token removed here is a token curation never has to stub, a token caching never has to write, and — for the KB case — a distractor removed rather than merely deferred. It also weakens the one argument for widening the curation keep-window: a ~360-token concise KB envelope is cheap enough to keep verbatim for longer if E7 ever demands it.

## Open decisions

- **Where the omission indication is allowed to live.** `agent-tool-registry` (spec.md:31-33) says a tool_result "contains only the fields the Holdings route already exposes to the frontend". Read as a **PII ceiling** — its evident intent — a strict subset plus non-PII counts and one sentence honours it. Read as a **completeness floor**, the added `txnsShown` / `txnsTotal` / note keys need a `MODIFIED Requirements` delta on that capability. This change deliberately does **not** write that delta (another change in flight owns the tool-registry surface); the reviewer should decide. The sibling scenario "One core, two entry points" (:9-11) stays literally true — the core is untouched and both entry points still produce the same envelope; only the dispatcher's serialization of it differs.
- **What the conversation store then holds.** `loop.py:410-427` stores `outcome.content`, so after this change `turns.content` holds the **bounded** string. `conversation-store/spec.md:7`'s invariant is "replay reconstructs the messages array byte-identically to what was sent to the model" — which the bounded string satisfies exactly. The real cost is that the full money card is no longer retained server-side (the `tool` span records only `is_error` / `error_code` / `duration_ms`, never the payload). Recommendation: accept it — the store's contract is *what the model saw* — and if full-card retention is ever wanted, add it to the trace span, never to the wire array.
- **Row cap value.** 25 is a judgement: it is 4× the card's initial 6 rows, covers the recent window a "missing money" question is actually about, and lands the envelope at ~1,780 tokens. Named constant, tunable in one place.
- **Holdings is the same shape and is deliberately out of scope.** 50 rows measures 4,451 tokens with no cap either; the `model_view` seam makes it a two-line follow-up once this lands, but it gets its own change and its own spec delta.

## Capabilities

### Modified Capabilities

- `money-flow`: the model-facing money payload is bounded to the most recent transactions with an explicit omission indication and exact full-stream aggregates, while the rendered card keeps the complete merged passbook.
- `kb-retrieval`: `POST /api/kb/search` and the `search_knowledge_base` tool accept a `concise | detailed` response format, defaulting to a bounded concise payload; `detailed` reproduces the previous field set.

## Impact

- Backend: `backend/app/agent/tools.py` (`Tool.model_view`, applied in `dispatch_outcome`; money tool description), `backend/app/data/money.py` (the model-view projection + row-cap constant), `backend/app/kb/router.py` (`response_format` on `KbSearchRequest`, projection applied after the traced retrieval), `backend/app/agent/tools.py` KB schema (the new enum + its description).
- Unchanged by design: `backend/app/agent/loop.py` artifact path, the SSE artifact contract, `POST /api/data/money`, `hybrid_search` and RRF fusion, `metadata.retrieval_context` in traces, every flow core.
- Specs: `openspec/specs/money-flow/spec.md`, `openspec/specs/kb-retrieval/spec.md`.
- Docs: `docs/api_doc/api_documentation.md` (KB default `top_k` 5 → 10; new `response_format`).
- Gates: `uv run pytest` green including new golden-payload tests (money model view vs artifact envelope, both KB formats, aggregates exact under truncation); the CHO-276 routing evals show no regression on E2/E6/E7; one measured before/after token count per envelope recorded in the Linear issue.
- Prefix note: the money tool description and the KB schema change the `tools` block, i.e. **one deliberate one-time prompt-cache invalidation** across all users at deploy.
- Deploy: backend-only → one new `backendvX.Y.Z`, frontend tag untouched.
- Linear: CHO-277 · branch `cho-277-tool-result-token-efficiency-at-source`
