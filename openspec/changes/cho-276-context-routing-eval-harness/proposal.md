# CHO-276: context-routing-eval-harness

## Why

CHO-271 names "routing evals must pass" as its merge gate. **That gate is unrunnable today**: `backend/evals/` does not exist and `scripts/` holds only `ship-tarball.sh`. Nothing in this repo measures routing or recall — `agent_traces` records tokens/cost, `tests/test_agent_store.py` pins byte-identical replay, and both are blind to *what the model decided*.

So the failure mode the context-engineering programme exists to fix has **no detector**. Its documented shape is not a crash: Chroma's context-rot work found Claude's characteristic long-context failure is **abstention** — answering *"I cannot determine… that was not provided in the chat history"* about a fact that **was** in the transcript — once enough mutually-similar distractor mass sits between the fact and the question. Our history is 91.3% tool_results and 1.8% user words at turn 15, which is close to that worst case. A curation bug therefore ships as a silent behavioural regression with a *falling* cost curve: every dashboard would look healthy.

This change builds the detector. It is net-new work sitting on CHO-271's critical path, and it is deliberately scoped to be independently landable and useful before curation exists (the flag-off arm is a recorded baseline).

## What Changes

- **New tracked harness `backend/evals/`** — a runner, one module per case, shared assertions, and canned fixtures. It is **not** part of `uv run pytest`: the live cases need `ANTHROPIC_API_KEY`, so they run under a separate invocation (`uv run python -m evals.runner`) and **skip — never fail — when the key is absent**, keeping CI green.
- **Seven gate cases (E1–E7)**, each run in **both curation-flag states, 3 attempts each**, recording the per-arm cost delta:
  - **E1 — mid-thread report parameters (the north star).** After a completed ledger flow plus three noisy turns, "now the same for MTF" must produce an `open_report_form` call seeded `flow=ledger`, `book=MTF` with the range carried from the flow-event memo — and **no prose parameter question** before it.
  - **E2 — post-artifact follow-up.** After a stubbed holdings card, a follow-up must re-call `get_holdings` and quote **no figure from the stale envelope**.
  - **E3 — note-id fidelity.** After a `list_contract_notes` result, "download the 14 June one" must call `download_contract_note` with an id that **string-matches an id present in the seed**, with **zero fabricated ids**. Hard-fail (3/3).
  - **E4 — long-range fact recall.** A fact the user states at turn 2 must be recalled exactly at turn 14. This is the context-rot / abstention metric, measured directly.
  - **E5 — ticket-affirmation guard.** A model-emitted `raise_support_ticket` with no escalation request or affirmation must still be rejected. Hard-fail (3/3), and **pytest + respx only, never a live eval** (see below).
  - **E6 — report-columns discipline.** Mid-thread, after a stubbed `get_report_columns` result, the model must re-call the tool **before describing any column** (the standing compliance rule at `prompt.py:186-192`).
  - **E7 — KB pronoun follow-up grounding.** "Tell me more about that" one turn after a KB answer must re-issue `search_knowledge_base` with a query carrying a content word from the earlier exchange. This is the case that decides whether the KB stub's preserved `question` strings are sufficient grounding.
- **A shared no-abstention assertion on every case.** The assistant text must not match the abstention family (*"cannot determine"*, *"not provided in the chat history"*, *"don't have access to"*, …). Present in all seven cases, because abstention-while-the-fact-is-present is precisely the north-star bug — a case that "passes" by declining to answer is a failure.
- **Credential-free by construction.** History is seeded through `store.append_turn`; the tool layer is substituted with a recording fake serving canned envelopes; usage/cost is captured in-process through `tracing` with a capturing fake pool. **No FinX/SSO credentials, no Postgres, no Freshdesk** — only `ANTHROPIC_API_KEY`, and only for the probe turn of each case.
- **E5 is a hard exception and stays out of the live suite.** `raise_support_ticket` has **no dry-run mode** (`config.py` exposes only `FRESHDESK_API_ROOT` / `FRESHDESK_API_KEY`), and the case's whole point is to exercise the branch where the guard must reject. A live run that regressed would **open real Freshdesk tickets** — the eval would cause the incident it is meant to catch. It therefore lands in `backend/tests/test_agent_loop.py` beside the existing `_fd_env` + respx Freshdesk cases, asserting the `is_error` bounce **and zero `POST /tickets`**.
- **A report artifact per sweep** — JSON plus a readable markdown twin, carrying per-case pass rate, first-failure detail, and the flag-on vs flag-off token/INR delta.

## Open decisions

- **Flag axis before the flag exists.** The runner sets `AGENT_CONTEXT_CURATION` per arm. If CHO-276 lands before CHO-271, both arms are identical and the sweep records a **baseline** — intended, and the reason this change does not block on curation. Recommendation: land it first and capture the baseline.
- **E3's two readings.** With the faked tool layer the ids are synthetic, so the case measures **id fidelity only** and must not be read as proof the download path works; against the real dispatcher the ids are 600-second capability tokens (`ContractNoteRefStore(ttl_seconds=600.0)`, `contract_notes.py:142`) and the run must finish inside that window. Both are specced, and the report records the seed→probe elapsed time so a reviewer can see which reading applies.
- **E2's "no stale figures" needs two envelopes.** The fake serves a *second*, deliberately different holdings envelope on the probe turn, so a stale quote is detectable by value rather than by judgement. This is the one case whose fixture design carries the assertion.

## Capabilities

### Added Capabilities

- `context-routing-evals`: a tracked, separately-invoked routing and recall eval harness — seeded conversation histories, a substituted tool layer, seven gate cases with a shared no-abstention assertion, a flag-matrix sweep with per-case pass rates and cost deltas, and a key-gated skip so the default test run stays green.

## Impact

- New (backend, tracked): `backend/evals/__init__.py`, `runner.py`, `harness.py`, `fixtures.py`, `assertions.py`, `cases/e1_report_params.py`, `cases/e2_artifact_followup.py`, `cases/e3_note_id_fidelity.py`, `cases/e4_fact_recall.py`, `cases/e6_report_columns.py`, `cases/e7_kb_followup.py`, `README.md`.
- Edited: `backend/tests/test_agent_loop.py` (E5 — guard rejection with zero Freshdesk POSTs, both flag states), `.gitignore` (`backend/evals/reports/`).
- Read-only dependencies (no change): `store.append_turn`, `agent_tools.dispatch_outcome`, `tracing` + `trace_cost`, the SSE contract.
- Gates: `uv run pytest` green (E5 included); one full sweep recorded and attached to the Linear issue; the live cases skip cleanly with no `ANTHROPIC_API_KEY`.
- Not in scope: LLM-judge scoring, a live-credential end-to-end suite, and any change to the agent loop, prompt, or tools.
- Linear: CHO-276 · branch `cho-276-context-routing-eval-harness`
