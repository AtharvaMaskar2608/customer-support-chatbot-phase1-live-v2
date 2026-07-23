# CHO-267: kb-topk-10-trace-chunks

## Why

Default KB retrieval returns 5 chunks, which is thin for harder support questions. The trace viewer already persists fused docs on retriever spans (`metadata.retrieval_context`) but only shows a count — operators cannot inspect what the model saw.

## What Changes

- Raise KB search default `top_k` from **5 → 10** (max stays 20) on the REST contract and agent tool schema description.
- Trace viewer: expanding a `retriever` span renders the stored `retrieval_context` chunk list (not just `{"count": N}`).

## Capabilities

### Modified Capabilities

- `kb-retrieval`: default `top_k` is 10.
- `observability-dashboard`: retriever span expand shows retrieval context chunks.

## Impact

- Backend: `backend/app/kb/router.py`, `backend/app/agent/tools.py`, `openspec/specs/kb-retrieval/spec.md`
- Frontend: `frontend/src/traces/SpanTree.tsx`
- Linear: CHO-267 · branch `cho-267-kb-topk-10-trace-chunks`
