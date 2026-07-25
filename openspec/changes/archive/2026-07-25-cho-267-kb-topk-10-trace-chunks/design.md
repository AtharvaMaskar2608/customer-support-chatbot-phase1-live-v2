# CHO-267 — design

## Decisions

### D1 — Default k=10, max unchanged

**Choice:** `KbSearchRequest.top_k` default `10`; tool schema text says default 10; max remains 20.

**Rationale:** Product asked for deeper recall without unbounded context. Agents may still pass a lower/higher `top_k` explicitly.

### D2 — Render existing retrieval_context (no new backend write)

**Choice:** SpanTree expands `metadata.retrieval_context` string list for retriever spans. Backend `observe_retrieval` already stores chunks — no tracing schema change.

**Rationale:** Data is already persisted; gap is UI-only. Avoids re-shipping span JSON shape.
