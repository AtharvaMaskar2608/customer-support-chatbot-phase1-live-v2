## Context

`backend/app/kb/embed.py::embed_query()` posts to OpenAI's embeddings endpoint using the single app-wide `httpx.AsyncClient` (built once in `backend/app/main.py:42-46`, IPv4-forced via `local_address="0.0.0.0"`, timeout = `config.upstream_timeout_seconds()` — 10s by default). On any `httpx.HTTPError` (including timeouts) it retries once more (`for attempt in (1, 2)`), each attempt bounded by the same 10s client-level timeout. `backend/app/kb/router.py:125-126` calls `embed_query()` *before* opening the `tracing.observe_retrieval()` span (`tracing.py:424-446`), so the embedding call's own duration is invisible in the trace today — it only shows up as the gap between the parent `tool` span's total duration and the `retriever` sub-span's duration. That's exactly how the ~20s stall was diagnosed: 20.02s tool span, 4ms retriever span, no span accounting for the other ~20s.

The existing `kb-retrieval` spec requirement ("Query embedding at request time") already sanctions degrading to FTS-only on embedding failure — that contract is correct and stays. The problem is purely how long the request takes to *reach* that degraded state when OpenAI is slow.

## Goals / Non-Goals

**Goals:**
- Bound the embedding call's worst-case latency to a small ceiling (single-digit seconds, not ~20s) before falling back to FTS-only.
- Give the embedding call a timeout independent of `upstream_timeout_seconds()`, which is tuned for FinX upstream calls (a different service, different latency profile).
- Make the embedding call's own duration a first-class, visible span in tracing, so this class of regression is visible directly instead of requiring manual gap arithmetic on a trace.
- Preserve today's degrade-to-FTS-only behavior exactly — this is a latency bound, not a behavior change.

**Non-Goals:**
- Not changing the hybrid retrieval (FTS + vector + RRF) logic itself.
- Not adding circuit breakers, global backoff state, or cross-request rate limiting for OpenAI calls — out of scope for a latency-bound fix.
- Not addressing OpenAI reliability broadly; this only bounds how much of that unreliability leaks into user-visible latency.

## Decisions

**1. Dedicated, shorter timeout for the embedding call, separate from `upstream_timeout_seconds()`.**
Add a new config value (e.g. `kb_embed_timeout_seconds()`, env `KB_EMBED_TIMEOUT_SECONDS`, sensible short default) rather than reusing or shrinking `upstream_timeout_seconds()`. Alternative considered — lowering `upstream_timeout_seconds()` globally: rejected, since that value also governs FinX upstream calls (report generation, holdings, money), which have a different, already-tuned latency profile; shrinking it globally risks premature timeouts on legitimate slow FinX calls to fix a problem that's specific to one OpenAI endpoint.

**2. Per-request timeout override on the existing shared client, not a second `httpx.AsyncClient`.**
httpx supports overriding `timeout=` on an individual `.post()` call without needing a dedicated client instance. Use that in `embed_query()` rather than standing up a second client with its own connection pool/lifecycle in `main.py`. Alternative considered — a dedicated `AsyncClient` for OpenAI calls: rejected as unnecessary lifecycle/complexity for what's just a per-call timeout difference; the IPv4 transport fix and connection reuse benefits of the shared client still apply.

**3. Keep two attempts, but shrink the budget per attempt (not the attempt count).**
The two-attempt retry design itself is sound — a transient blip is worth one quick retry. The bug is that each attempt gets the *full* 10s budget. Shrink each attempt's timeout so the worst case (both attempts fail) lands in the single-digit seconds, not ~20s. Alternative considered — drop to one attempt only: rejected, since a single transient network blip would then unnecessarily push a request to FTS-only degradation when a fast retry would likely have succeeded; the count isn't the problem, the per-attempt budget is.

**4. Add a dedicated tracing span around the embedding call, mirroring `observe_retrieval`'s existing pattern.**
`tracing.py` already has the shape for this (`observe_retrieval` at `tracing.py:424-446` opens a span, runs the wrapped call, records duration/metadata). Add an analogous span (e.g. `observe_embedding`) around the `embed_query()` call in `kb/router.py`, nested under the same `tool` parent span the `retriever` span already nests under — so a future trace shows embedding duration directly as its own span instead of requiring the gap-inference used to diagnose this one.

## Risks / Trade-offs

- **[Risk]** A shorter per-attempt timeout could push MORE requests into FTS-only degradation if OpenAI's normal healthy latency is closer to the new ceiling than assumed. → **Mitigation**: pick the new timeout from real observed healthy-path latency (sample existing traces for typical successful embedding-call duration) rather than guessing; start slightly conservative and tune from post-deploy trace data if needed.
- **[Risk]** Bounding retry budget means an OpenAI slow-but-not-broken day produces more FTS-only answers than today. → **Mitigation**: this trade-off is already explicitly sanctioned by the existing `kb-retrieval` spec requirement (FTS-only degradation is a designed, acceptable outcome, not a failure) — consistently bounded latency in exchange for a slightly higher degraded-mode rate is the intended trade.
- **[Risk]** A new span type in the trace could surprise anything downstream that assumes a fixed shape under a `tool` span (eval harness, observability dashboard). → **Mitigation**: purely additive (one new sibling span next to the existing `retriever` span); check `backend/evals/` and the `observability-dashboard`/`observability-tracing` specs for hard assumptions about span counts before landing.

## Migration Plan

No data migration. Pure code + config change. The new timeout env var should default sensibly (matching the pattern of `UPSTREAM_TIMEOUT_SECONDS` defaulting to `"10"`) so no `.env` changes are required to deploy. Ship as a normal backend release; no special rollback beyond reverting the deploy if the new timeout proves too aggressive in practice.

## Open Questions

- What's the right timeout value empirically? Needs a look at real historical trace data for typical *successful* embedding-call latency before hardcoding a specific number.
- Should there be a tiny delay/jitter between attempt 1 and attempt 2, or retry immediately? Leaning toward immediate retry (simplest; a network blip likely resolves within well under a second) but worth a second look during implementation.
- Exact name/placement of the new tracing span — implementation should mirror `observe_retrieval`'s existing conventions as closely as possible rather than inventing a new pattern.
