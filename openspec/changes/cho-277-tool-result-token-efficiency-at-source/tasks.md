# CHO-277: tool-result-token-efficiency-at-source — tasks

## 1. The model-facing projection seam

- [x] 1.1 `tools.py`: add optional `model_view: Callable[[dict], dict] | None = None` to the `Tool` dataclass (default identity)
- [x] 1.2 `tools.py` `dispatch_outcome`: apply `model_view` to the success result before `json.dumps` for `content`; keep `envelope=result` (the full object) untouched
- [x] 1.3 Assert by test that `DispatchOutcome.envelope` is the unprojected result, so `loop.py:_artifact_payload` and the SSE contract cannot move
- [x] 1.4 Confirm error results and `ToolError` paths bypass the projection entirely (failures stay verbatim — they are the corrective instruction)

## 2. Money: bound the model payload, keep the card whole

- [x] 2.1 `money.py`: named row-cap constant (25) with a comment stating `_PAGE_SIZE = 500` is **per direction** (`:90` `"NoOfRecords"`) and that the uncapped model payload can reach ~67k tokens
- [x] 2.2 `money.py`: `model_view(envelope)` → newest-N `txns` slice (the stream is already newest-first), verbatim `counts` / `landed` / `totalRecords` / `partial`, plus `txnsShown` / `txnsTotal`
- [x] 2.3 Write the omission sentence: aggregates cover all *n*; the full list is on the card the user is viewing; **no** instruction to re-call the tool (zero-slot flow — a repeat call returns the same view)
- [x] 2.4 Register it as `get_money_transactions`' `model_view`; leave `run_money` and `POST /api/data/money` untouched
- [x] 2.5 Update the money tool description so the model knows the payload is bounded and the aggregates are complete
- [x] 2.6 Tests: golden model payload (72 txns → capped rows + shown/total + sentence); artifact envelope still carries all 72; aggregates exact when a landed deposit falls outside the cap; empty and `partial: true` shapes pass through unchanged; the route's 200 body is byte-identical to before
- [x] 2.7 Record the measured before/after token count for the 72-txn envelope and for a both-directions-full page
      - 72-txn envelope: **4,680 → 1,782 tokens** (10,608 → 4,263 chars) — −61.9%
      - both directions at `NoOfRecords=500` (1,000 rows): **64,150 → 1,787 tokens** (146,231 → 4,279 chars) — −97.2%
      - measured with `messages.count_tokens` (claude-sonnet-4-6) on the exact compact sorted-key JSON the dispatcher writes

## 3. KB: concise/detailed response format

- [x] 3.1 `kb/router.py`: `response_format: Literal["concise","detailed"] = "concise"` on `KbSearchRequest` (422 on anything else)
- [x] 3.2 `kb/router.py`: apply the projection in `run_kb_search` **after** `tracing.observe_retrieval` returns, so `metadata.retrieval_context` keeps full chunks
- [x] 3.3 Concise projection: `{id, topic, section, question}` for every result; `answer` + `tat` on the top 3 only; `score` dropped; retained answers bounded to 1,200 chars with a `truncated` flag
- [x] 3.4 `detailed` returns today's exact field set — no behaviour change for callers that ask for it
- [x] 3.5 `tools.py`: add `response_format` to the `search_knowledge_base` schema with a description saying when to ask for `detailed`; keep `top_k` default 10
- [x] 3.6 Tests: default is concise; detailed reproduces the pre-change field set; ids and order identical across formats; the 1,200-char bound flags truncation; `{"kind":"ok","results":[]}` unchanged; degraded `fts_only` flag unchanged; retriever span retrieval_context still full
- [x] 3.7 Record the measured before/after token count for a mean and a topic-clustered top-10 draw
      - mean top-10 draw (answers ~174 chars): **1,021 → 503 tokens** (3,348 → 1,781 chars) — −50.7%
      - p90 top-10 draw (answers ~700 chars): **2,571 → 968 tokens** — −62.3%
      - topic-clustered p99 top-10 draw (3,010 / 1,548 / 1,548 / 1,100 / 900 / 900 / 700 / 520 / 300 / 174 chars): **3,679 → 1,427 tokens** — −61.2%
      - same tokenizer; draws synthesized to the corpus length distribution (the `:5433` KB tunnel is not up in this worktree)

## 4. Specs and docs

- [x] 4.1 `openspec/specs/money-flow/spec.md` — modified Progressive disclosure requirement (delta verified against the implementation; see the note on its PII-whitelist sentence in 4.4)
- [x] 4.2 `openspec/specs/kb-retrieval/spec.md` — modified Tool-shaped endpoint requirement (delta verified against the implementation; every scenario has a test)
- [x] 4.3 `docs/api_doc/api_documentation.md:375` — KB `top_k` default 5 → 10 and document `response_format`
- [x] 4.4 Resolve the open decision on `agent-tool-registry`'s "Whitelisted payload in transcript" scenario with the reviewer: PII ceiling (no delta needed) or completeness floor (a `MODIFIED Requirements` delta on that capability)
      - **Recommendation: PII ceiling — no delta needed.** The scenario is about what must NOT leak, not about the field list being closed. It sits under "Handlers return model-consumable results", whose requirement text is entirely prohibition ("never raw upstream bodies, never raised exceptions across the dispatch boundary, and never credentialed URLs"), and it names Holdings, not money. `txnsShown` / `txnsTotal` / `note` are derived counts and one English sentence — no client data at all — so strict-subset-plus-non-PII-metadata honours the ceiling. Read as a completeness floor, the same sentence would also forbid the `fileToken` indirection the very next scenario mandates, which shows the floor reading is not the intent. Recorded as a reviewer decision only — no delta written on that capability.

## 5. Verification

- [x] 5.1 `uv run pytest` green — money route, KB route, agent loop, and artifact contract tests unchanged (527 passed, 3 skipped; baseline 499 passed, 2 skipped)
- [ ] 5.2 CHO-276 routing evals: no regression on E2 (data-card follow-up), E6 (report columns), E7 (KB follow-up)
- [ ] 5.3 Live smoke with a fresh SSO JWT: a money turn renders the full card while the stored tool_result is the bounded payload; a KB turn answers correctly from the concise form
- [ ] 5.4 Note the one-time prompt-cache invalidation (the `tools` block changed) and confirm a fresh thread's first span still reads the frozen prefix afterwards

## 6. Ship & sync

- [ ] 6.1 `git-sync` with issue key CHO-277
- [ ] 6.2 `linear-connector` — In Progress at start, summary + In Review at PR, Done at merge
