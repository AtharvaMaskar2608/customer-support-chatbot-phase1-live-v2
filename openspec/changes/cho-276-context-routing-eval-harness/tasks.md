# CHO-276: context-routing-eval-harness — tasks

## 1. Harness skeleton

- [x] 1.1 `backend/evals/__init__.py` + `README.md` (what it is, the one command, the env var it needs, how to read the report)
- [x] 1.2 `harness.py`: build the app, seed a thread through `store.append_turn` (user_text / assistant_text / assistant_tool_use / tool_result / flow_event helpers)
- [x] 1.3 `harness.py`: recording tool double — monkeypatch `agent_tools.dispatch_outcome`, return canned `DispatchOutcome`s per tool, record every `(name, input)`
- [x] 1.4 `harness.py`: probe one turn via `POST /api/chat`, parse the SSE stream into `(event, data)` pairs, expose assistant text + tool events
- [x] 1.5 `harness.py`: in-process usage capture — enable `tracing` with a capturing fake pool, pull the `llm` spans' token/cache split, price via `trace_cost`
- [x] 1.6 `harness.py`: skip cleanly (never fail) when `ANTHROPIC_API_KEY` is absent
- [x] 1.7 `fixtures.py`: canned envelopes — holdings (two variants with distinct figures), money, contract-note list (synthetic ids), KB top-10, report columns, ledger flow-event memo
- [x] 1.8 `assertions.py`: the shared no-abstention constant + matcher; helpers for first-tool-call, tool-input fields, id-fidelity, and "no figure absent from the fresh envelope"

## 2. The live cases

- [x] 2.1 `cases/e1_report_params.py` — completed ledger flow + 3 noisy turns → "now the same for MTF": first call is `open_report_form`, `flow=ledger`, `book=MTF`, range carried from the memo, **no prose parameter question before the call**
- [x] 2.2 `cases/e2_artifact_followup.py` — spent holdings card + 1 intervening turn: `get_holdings` re-called; no figure from the seeded envelope that is absent from the fresh one
- [x] 2.3 `cases/e3_note_id_fidelity.py` — spent `list_contract_notes` (20 synthetic ids) + 3 noisy turns → "download the 14 June one": emitted id string-matches a seeded id, zero invented ids; record seed→probe elapsed seconds
- [x] 2.4 `cases/e3_note_id_fidelity.py` — recovery sub-case: a bounced (expired-id) download leads to a fresh `list_contract_notes`, never an invented id
- [x] 2.5 `cases/e4_fact_recall.py` — fact stated at turn 2, 12 noisy turns (2 KB rounds + a money card), probe at turn 14: exact amount + date echoed
- [x] 2.6 `cases/e6_report_columns.py` — spent `get_report_columns` + 2 noisy turns: tool re-called before any column is described; no label absent from the fresh result
- [x] 2.7 `cases/e7_kb_followup.py` — KB exchange + 1 intervening turn → "tell me more about that": `search_knowledge_base` re-issued with a content word from the earlier exchange, not a bare pronoun
- [x] 2.8 Every case wires the shared no-abstention assertion

## 3. E5 in the normal test suite (never live)

- [x] 3.1 `backend/tests/test_agent_loop.py`: model-emitted `raise_support_ticket` with no escalation request / no affirmation → `is_error` bounce carrying the "offer instead" instruction
- [x] 3.2 Same test asserts the respx ticket-creation route recorded **zero** requests
- [x] 3.3 Parametrize over both curation-flag states; behaviour identical in each

## 4. Runner, flag matrix, report

- [x] 4.1 `runner.py`: CLI (`uv run python -m evals.runner`) with `--case`, `--attempts`, `--arm on|off|both`
- [x] 4.2 Set the curation flag per arm; when the flag does not exist, run both arms anyway and label the sweep a baseline
- [x] 4.3 Aggregate per case: attempts, passes, pass rate, first-failure detail, per-arm token totals + INR
- [x] 4.4 Write `backend/evals/reports/routing-evals-<ISO>.json` and its markdown twin; add `backend/evals/reports/` to `.gitignore`
- [x] 4.5 Enforce the thresholds — id + ticket-guard cases 3/3, others ≥2/3 and no regression vs the off arm, zero abstention matches anywhere — and exit non-zero when any is missed

## 5. Verification

- [x] 5.1 `uv run pytest` green, including E5
- [x] 5.2 Runner with no `ANTHROPIC_API_KEY`: all live cases skipped, exit 0
- [ ] 5.3 One full sweep with a live key: report written, thresholds evaluated, no FinX credentials and no Postgres involved
      — PARTIAL: live wiring proven with a deliberately cheap slice (E1 and E4, 1 attempt each, off arm:
      both passed, 18,892 tokens, ₹4.43 total, zero blocked HTTP attempts). The full 7-case × 2-arm ×
      3-attempt matrix is a spend decision left to the user.
- [x] 5.4 Confirm no Freshdesk request is issued anywhere in the sweep or the suite
- [ ] 5.5 Attach the baseline report to CHO-276

## 6. Ship & sync

- [ ] 6.1 `git-sync` with issue key CHO-276
- [ ] 6.2 `linear-connector` — In Progress at start, summary + In Review at PR, Done at merge
