# CHO-276 — design

## Decisions

### D1 — Seed history through the store, generate only the probe turn

**Choice:** Each case builds its thread by calling `store.append_turn(...)` directly for every prior turn (user text, assistant text, `assistant_tool_use`, `tool_result`, `flow_event`), then issues **one** `POST /api/chat` for the probe message.

**Rationale:** `append_turn` is synchronous, assigns `seq` and enqueues the write with no await in between, so wire order is persistence order — a seeded thread is byte-indistinguishable from a lived one at `thread.messages()`. Generating 14 turns live per attempt would cost ~10× more, take minutes, and make failures non-reproducible (the distractor mass would differ between the flag-on and flag-off arms, destroying the comparison). Seeding makes the two arms differ **only** in the curation transform, which is the whole measurement.

### D2 — Substitute the tool layer, do not call Choice APIs

**Choice:** Monkeypatch `agent_tools.dispatch_outcome` with a recording fake that returns canned `DispatchOutcome`s per tool name and appends every `(name, input)` to a list. Assertions read that list plus the SSE event stream. E1 (`forms.py`) and E6 (`columns.py`) MAY use the real handlers — both cores are local and credential-free.

**Rationale:** The pattern already exists in `tests/test_agent_loop.py`, so there is nothing to invent. It buys three things at once: **no FinX credentials** (so any engineer can run the sweep, and it does not decay with the 8-hour SSO token), **determinism** on the tool side so a failure is attributable to context and not to upstream flakiness, and **control of the fresh envelope**, which is what makes E2's "no stale figures" assertion mechanical rather than a judgement call.

**Cost:** the harness does not exercise the real upstreams — deliberate. This is a routing/recall gate, not an integration suite; upstream contracts are covered by the existing respx route tests.

### D3 — Capture cost in-process with a fake pool, not from a live Postgres

**Choice:** Enable `tracing` for the run with a capturing fake pool (the `tests/test_agent_tracing.py` shape) and read the `llm` spans' `input_tokens` / `output_tokens` / `cache_read` / `cache_creation` off the captured rows, priced through `trace_cost`.

**Rationale:** The cost delta is a required output of the sweep, and requiring a live `agent_traces` table would drag a DB dependency (and a tunnel) into a gate meant to be runnable from a laptop with one env var. The span tree is the same object that would have been persisted, so the numbers are the production numbers.

### D4 — Missing key skips; E5 lives in the normal suite

**Choice:** No `ANTHROPIC_API_KEY` ⇒ every live case reports `skipped` and the runner exits 0. E5 is a pytest case in `backend/tests/test_agent_loop.py`.

**Rationale:** A gate that fails on a laptop without a key trains people to ignore it. Meanwhile E5 is the one case that **must** run on every commit and must **never** run live: `raise_support_ticket` has no dry-run (`FRESHDESK_API_ROOT` / `FRESHDESK_API_KEY` are the only knobs), so a live attempt at the guard's rejection branch would file real tickets exactly when the guard is broken. respx makes "zero POSTs to `/tickets`" a first-class assertion, which is the actual invariant — stronger than any live observation.

### D5 — The no-abstention regex is shared, and applies to all seven cases

**Choice:** One documented constant in `assertions.py`, matched against the concatenated assistant text of the probe turn, asserted in every case.

**Rationale:** Chroma's finding is that Claude's long-context failure is abstention, not hallucination. Without this assertion a case can "pass" its routing check while declining to answer, which is the regression. Keeping it in one place also keeps the phrase list reviewable — it is a behavioural contract, not test scaffolding.

### D6 — E3 states its precondition instead of hiding it

**Choice:** The contract-note id case runs with synthetic ids under the faked dispatcher and asserts **fidelity only** (every emitted id string-matches a seeded id; zero ids that do not). The report records the seed→probe elapsed seconds, and the case documents that a variant run against the real dispatcher is only valid inside the **600-second** `ContractNoteRefStore` TTL (`contract_notes.py:142`). A companion sub-case seeds a bounced (expired) download and asserts the model re-calls `list_contract_notes` rather than inventing an id.

**Rationale:** Without this the case is a false green in both directions: with real ids a slow run fails for a reason unrelated to context, and with synthetic ids a pass could be misread as "downloads work". Naming the window turns a latent trap into a stated precondition — and the recovery sub-case is what actually protects production, since the ids expire there too.

### D7 — Report artifact is written, not printed

**Choice:** `backend/evals/reports/routing-evals-<ISO8601>.json` plus a markdown twin; directory gitignored.

**Rationale:** The gate's output has to be attachable to a Linear comment and diffable between sweeps (the flag-on/flag-off delta is only meaningful against a prior baseline). Terminal output alone makes the merge gate unreviewable — the defect that made CHO-271's original "runner under `scripts/`" sketch unacceptable.

## Non-goals

- LLM-judge scoring, rubric grading, or any assertion that needs a second model call.
- A live-credential end-to-end suite (upstream contracts are already covered by the respx route tests).
- Any change to the loop, prompt, tools, or store — this change adds only test-side code plus one pytest case.
