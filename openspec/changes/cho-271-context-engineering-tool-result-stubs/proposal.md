# CHO-271: context-engineering-tool-result-stubs

## Why

Mid-conversation the agent regresses: a report follow-up that should re-open a seeded guided form
starts asking for parameters in prose instead, and facts stated early in the thread stop being
recalled. The measured cause is context composition, not a prompt bug.

Measured on a representative 15-turn widget session (real `count_tokens` against
`claude-sonnet-4-6`, envelopes built through the real code paths):

- history at turn 15 = **12,628 tok**, of which **91.3% is `tool_result` content** and only
  **1.8% is the user's own words** (assistant prose 5.4%, `tool_use` blocks 1.5%). CHO-263's
  "the needle is ~3% of the context" estimate was conservative.
- **53.9% of history was never read by the model in the turn that produced it** — artifact-only
  rounds short-circuit before any continuation call (`backend/app/agent/loop.py:463-479`), so a
  holdings (949 tok) or money (4,889 tok) envelope is streamed to the frontend and stored, and
  first enters a model call on the *next* turn.
- one 72-transaction `get_money_transactions` envelope (4,889 tok) accounts for **30% of the whole
  conversation's bill**; at `_PAGE_SIZE = 500` *per direction* (`app/data/money.py:61`) a single
  result can legitimately reach ~67k tokens.

That mass is the documented long-context failure mode, not just spend. Chroma's context-rot work
finds Claude's characteristic failure is **abstention** — answering "that was not provided in the
chat history" when the fact *was* present — once enough distractor mass sits between the fact and
the question. The fix is to remove distractor mass, not to add instructions.

**This is a correctness change, not a cost change.** CHO-264's caching makes bloat cheap; it does
not make it harmless. The cost table exists only to prove curation costs nothing: 15-turn
conversation ₹42.35 today → ₹14.31 with CHO-264 → **₹9.89 with curation (−77%)**, marginal turn-15
cost ₹3.86 → ₹0.31, final history 12,628 → ~2,323 tok. Signal ratio (user + assistant prose +
memos) moves from ~10% to ~45% of history.

## What Changes

**What stays vs what goes — three separate layers.** Nothing is deleted anywhere; only what the model
*reads* changes.

| Layer | What happens | Why |
|---|---|---|
| **Postgres store** (`thread.turns`, `turns` table) | **Kept forever, byte-for-byte.** Every tool result stays in full. | It is the audit record, the source of ticket transcripts, the trace-replay input and the training corpus. Curation is a read-time projection — the store is never mutated, and **nothing in this layer enters a prompt directly**. |
| **Model-facing context** (what the request carries) | **Spent payloads removed**, replaced by deterministic stubs. History ~12.6k → ~3.1k tok at turn 15. | This is the only layer with the abstention/context-rot problem, and the only layer this change touches. |
| **API request structure** | **The `tool_result` block itself must remain.** Only its `content` string becomes the stub; `type`, `tool_use_id` and `is_error` pass through. | The Messages API 400s on a `tool_use` block with no matching `tool_result`. Dropping blocks is not an option at any K. |

**The irreducible set that deliberately stays verbatim:**

- **The current turn's own results** — the model cannot answer the question it was called for without
  them (this is what K=1 means).
- **Error results** (any tool) — the error text *is* the corrective instruction, ≤~60 tok, and keeping
  it prevents retry loops.
- **`open_report_form` seed envelopes and `raise_support_ticket` results** — 69–110 tok and ~38 tok;
  these are the routing exemplars this change exists to reinforce.
- **KB matched `question` strings** — ~120 tok kept in place of ~940 verbatim, so a pronoun follow-up
  can see what was found and re-search instead of abstaining.
- **`list_contract_notes` ids** with their dates — the download tool forbids inventing an id, so the ids
  must survive (with their ~600 s expiry stated).

**Why stub rather than delete.** A bare deletion, or an unauthored "data removed" placeholder, is the
wording most likely to *induce* the exact failure mode this change exists to fix — Claude's documented
long-context failure is abstaining ("that was not provided in the chat history") rather than acting. So
every stub is authored, names what the user already saw, and **ends with an actionable recovery clause**
telling the model which tool to call again.

- **New curated read-time projection.** A new pure module `backend/app/agent/curation.py` builds a
  `messages_for_model` view in which **spent** `tool_result` blocks keep their `type`,
  `tool_use_id` and `is_error`, and only the `content` string is replaced by a deterministic stub.
  Every `tool_use` block therefore still has its matching `tool_result` block (the API 400s
  otherwise). **The lossless store is never mutated** — curation is a pure function of stored bytes
  plus `meta`, so replay, ticket transcripts, caps, feedback anchors and the training corpus are
  untouched by construction.
- **Per-class rules, K pinned per class in code** (no env knob):
  - **Errors are never curated** (`meta["is_error"] is True`, any tool) — an error's content *is*
    the corrective instruction ("call `open_report_form` instead"), ≤~60 tok each, and keeping it
    prevents retry loops.
  - **`open_report_form` and `raise_support_ticket` results are never curated** — 69–110 tok and
    ~38 tok. The `open_report_form` envelope (`flow` + `seed` + `prefilled`) is the strongest
    in-context exemplar of exactly the routing behaviour this change exists to restore; stubbing it
    would be self-defeating.
  - **Artifact class** (`get_holdings`, `get_money_transactions`, `get_brokerage_rates`, the P&L /
    ledger / capital-gains file envelopes, `download_contract_note`) → stub at **K=1**: verbatim
    inside its own turn, stubbed from the next user message onward.
  - **KB results** (`search_knowledge_base`) → stub that **preserves the matched `question`
    strings** and drops `answer` / `tat` / `score` (~940 → ~120 tok, 7.8×), so a pronoun follow-up
    ("tell me more about that") can see *what was found* and reformulate a search instead of
    abstaining.
  - **`get_report_columns`** → labels dropped too: the REPORT COLUMNS RULE mandates answering only
    from a fresh call, so a stub that keeps labels invites describing a column from its label.
  - **`list_contract_notes`** → **id-preserving** stub: every note `id` with its date and segment
    (cap the 40 newest + an explicit omission line), and the stub **states the ~600-second
    expiry** — ids are opaque session-bound capability tokens from `ContractNoteRefStore`
    (`ttl_seconds=600.0`, `app/reports/contract_notes.py:142`), so they are not PII and self-expire,
    but a stale id must never be presented as usable.
  - Any unregistered tool name → verbatim (**fail-open**): adding a tool can never silently degrade
    context.
- **Stub shape modelled on the shipped app-event memo** (`app/agent/events.py:25`), with a distinct
  noun so curation notes are never confused with app *events*: `[App note — generated by the app,
  not typed by the user]`. Stubs are deterministic (no model call, no clock read, built only from
  stored envelope fields), carry counts / customer-facing labels / ISO dates / opaque ids and
  **never ₹ amounts**, and **always end with an actionable recovery clause** — an unauthored "data
  removed" placeholder is precisely the wording most likely to induce the abstention failure this
  change exists to fix.
- **Boundary.** Watermark `W` = `seq` of the newest `user_text` turn; a `tool_result` turn is
  curated iff `turn.seq < W` (plus the class rules). `W` is within-turn stable (mid-turn appends are
  `tool_result` / `flow_event`, never `user_text`), monotone, and byte-deterministic. Because
  results are appended *after* their user message, a stub rewrite never touches bytes at or before the
  newest `user_text` block — the position CHO-264's per-round marker already writes an entry at on
  every turn — so the two changes compound rather than fight. (The just-finished turn's *intra-turn*
  entries do cover those bytes and expire when the watermark advances; bridging that gap is CHO-264's
  lookback problem, and it is a consequence of curation being correct, not a defect.)
- **One integration seam.** An optional `transform=` parameter on `Thread.messages()` keeps the
  merge/partition logic in one place and leaves the lossless default byte-identical; one call site
  changes, at `backend/app/agent/loop.py:303`. Per-`seq` memoisation lives in a non-persisted
  `Thread.curated` dict (precedent: `first_name` / `name_fetched`, `store.py:160-165`).
- **Observability.** Add `curated_turns` and `history_tokens_est` to the `llm` trace span (~5 lines)
  — traces record `redact(user_input)` + usage today, never the messages array, so a curation bug is
  currently invisible in the trace viewer.
- **Single flag `AGENT_CONTEXT_CURATION`, default off at merge.** Merge with the flag off, run the
  CHO-276 routing evals with it off and on, flip the env var on prod, then a follow-up commit
  changes the default. Behavioural risk earns a gate the cache work does not need.

## Open decisions

- **Default flip is a separate commit**, deliberately: the merge gate is the CHO-276 eval run, not
  this diff.
- **If the KB pronoun follow-up eval still fails**, the fix is to enrich the KB stub (add `topic`),
  **never to raise K** — K=2 pushes the readable cache anchor back one user turn and roughly doubles
  the per-turn write delta, paying with the exact property the scheme rests on.
- `list_contract_notes` ids expire in 600 s. The stub states it; making the id-based recovery path
  robust (re-mint on a bounced download) is a pre-existing gap this change surfaces, not fixes.

## Capabilities

### Modified Capabilities

- `conversation-store`: exposes a **curated model-facing projection** of a thread's turns — spent
  `tool_result` content replaced by deterministic stubs, stored turns unmutated, `tool_use` /
  `tool_result` pairing preserved, byte-stable for a given watermark.
- `agent-loop`: the loop sends the curated projection when `AGENT_CONTEXT_CURATION` is enabled
  (default off at merge), and the projection preserves the routing signal — form seed envelopes stay
  verbatim, so a mid-conversation report request still opens a seeded guided form rather than asking
  for parameters in prose.

## Impact

- **New**: `backend/app/agent/curation.py` (pure: stub renderers, watermark, transform closure),
  `backend/tests/test_agent_curation.py`.
- **Backend edits**: `backend/app/agent/store.py` (optional `transform=` on `Thread.messages()`,
  non-persisted `Thread.curated`), `backend/app/agent/loop.py:298-304` (one call site),
  `backend/app/config.py` (`agent_context_curation()`, mirroring `tracing_enabled()` at `:330`),
  `backend/app/agent/tracing.py` (two extra `llm` span metadata fields),
  `backend/tests/test_agent_loop.py` (one new integration test), `.env.example`.
- **Spec deltas**: `openspec/specs/conversation-store/spec.md` (ADDED — the curated projection; the
  existing byte-identical-replay requirement at line 7 is **CHO-264's** to modify, not this
  change's), `openspec/specs/agent-loop/spec.md` (ADDED — curated context + routing-signal
  preservation).
- **Not touched**: SSE contract, artifact payloads, frontend, DB schema, tool schemas, prompt text
  (no `prompt_snapshots` row, no `prompt_hash` change).
- **Gates**: `cd backend && uv run pytest` green including the 16 new curation tests; then the
  CHO-276 routing evals at 3 attempts each with the flag off and on — mid-thread seeded form, no
  stale figures, note-id survival within a 10-minute window, turn-2 fact recalled at turn 14, ticket
  affirmation guard, column compliance, KB pronoun follow-up — with zero abstention-regex matches.
- **Rollout**: backend-only → one new `backendvX.Y.Z` (frontend tag untouched). Flag flip on prod is
  a user-gated SSH action (`docker rm -f jini-backend` + `docker run … -e AGENT_CONTEXT_CURATION=1`),
  so both the flag and its safe default must be readable from the container env.
- **Rollback**: `AGENT_CONTEXT_CURATION=0` + container recreate; the lossless store means no data to
  repair.
- **Blocked by CHO-276** (the routing-eval harness is this change's merge gate). Composes with
  CHO-264 (caching); does not depend on it.
- Linear: CHO-271 · branch `cho-271-context-engineering-tool-result-stubs`
