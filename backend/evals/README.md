# Routing & recall evals (CHO-276)

Does the agent still **route correctly** deep into a conversation? `agent_traces`
records tokens and cost, and `tests/test_agent_store.py` pins byte-identical
replay — both are blind to *what the model decided*. This harness is the
detector, and it is the merge gate for the context-engineering work (CHO-271
curation, CHO-277 payload projection).

The failure it hunts is not a crash. Claude's characteristic long-context failure
is **abstention**: answering *"I cannot determine… that was not provided in the
chat history"* about a fact that **was** in the transcript, once enough
mutually-similar distractor mass sits between the fact and the question. Our
history is ~91% tool_results by turn 15, close to that worst case — so a curation
bug would ship as a silent behavioural regression with a *falling* cost curve.
Every dashboard would look healthy.

## The one command

```bash
cd backend
uv run python -m evals.runner                    # both arms, 3 attempts each
uv run python -m evals.runner --case E1 --attempts 1
uv run python -m evals.runner --arm off --quiet
```

* **Needs `ANTHROPIC_API_KEY`** (env, or the untracked repo-root `.env`) — and
  nothing else. **No** FinX/SSO credentials, **no** Postgres, **no** Freshdesk.
* **No key ⇒ every case is skipped and the runner exits 0.** A gate that fails on
  a laptop without a key trains people to ignore it.
* **Not part of `uv run pytest`** (`pyproject.toml` pins `testpaths = ["tests"]`),
  so the default test run never makes a model call.
* Exit code: `0` when every threshold is met (or everything skipped), `1` when a
  threshold is missed, `2` on bad arguments.

## How a case works

1. **Seed the history through the store.** Every prior turn is written with
   `store.append_turn` — user text, assistant text, `assistant_tool_use`,
   `tool_result`, `flow_event` memos. `append_turn` assigns `seq` and enqueues
   with no await in between, so a seeded thread is byte-indistinguishable from a
   lived one at `thread.messages()`. A fourteen-turn thread therefore costs
   **one** model call, and both flag arms see the *identical* distractor mass —
   which is the whole measurement.
2. **Double the tool layer.** `agent_tools.dispatch_outcome` is replaced by a
   recording fake serving canned envelopes and recording every
   `(tool name, input)`. The two purely local cores (`open_report_form`,
   `get_report_columns`) may run for real. Nothing reaches an upstream: the
   shared HTTP client is replaced by one that raises on every request and counts
   the attempt.
3. **Probe exactly one turn** through `POST /api/chat` and assert on what the
   model *did*: which tool it called first, with which inputs, and whether any
   figure, label or id it emitted is absent from the fresh envelope.

## The cases

| id | what it pins | gate |
|---|---|---|
| E1 | mid-thread report parameters: after a completed ledger flow + 3 noisy turns, "now the same for MTF" opens a form seeded `flow=ledger, book=MTF` with the range from the memo, and asks no parameter question in prose | ≥2/3 |
| E2 | a spent holdings card is re-fetched, and no figure from it that the fresh envelope lacks is quoted | ≥2/3 |
| E3 | contract-note id fidelity: the emitted id string-matches a seeded id, zero invented ids | **3/3** |
| E3r | an expired-id bounce recovers by re-listing, never by inventing an id | ≥2/3 |
| E4 | an amount + date stated at turn 2 recalled exactly at turn 14 — the abstention metric | ≥2/3 |
| E6 | report columns re-fetched before any column is described; no stale-only label quoted | ≥2/3 |
| E7 | "tell me more about that" re-issues a KB query carrying a content word, not a bare pronoun | ≥2/3 |
| E5 | the ticket-affirmation guard still rejects an unaffirmed `raise_support_ticket` | **pytest only** |

Plus one assertion **every** case applies: the probe turn's assistant text must
not match the abstention family (`assertions.ABSTENTION_PATTERNS`, one constant,
reused everywhere). A case that "passes" its routing check while declining to
answer has reproduced the exact bug — so the harness funnels every outcome
through `harness.finish`, which always runs it.

### Why E5 is never live

`raise_support_ticket` has **no dry-run mode** (`config.py` exposes only
`FRESHDESK_API_ROOT` / `FRESHDESK_API_KEY`), and the case's whole point is the
branch where the guard must *reject*. A live run that regressed would open real
Freshdesk tickets — the eval would cause the incident it exists to catch. It
lives in `backend/tests/test_agent_loop.py`, where respx makes "zero POSTs to
`/tickets`" a first-class assertion, which is the stronger statement anyway.

### Why E3 states a precondition

Contract-note ids are session-bound capability tokens that expire after **600
seconds** (`ContractNoteRefStore(ttl_seconds=600.0)`, `contract_notes.py:142`).
Under the doubled tool layer the ids are synthetic, so E3 asserts **id fidelity
only** and must **not** be read as evidence that the download path works. The
report records the seed→probe elapsed seconds so a reviewer can tell whether a
variant run against real ids fell inside the window.

## Reading the report

Each sweep writes `evals/reports/routing-evals-<ISO>.json` and a markdown twin
(the directory is gitignored). They carry, per case and per arm: attempts,
passes, pass rate, the first failure's reasons, the values the case asserted on,
and the token split (input / output / cache-read / cache-creation) priced to INR
by `app.agent.trace_cost` — the same cost model the operator dashboard uses.

* **`kind: "baseline"`** means the curation flag `AGENT_CONTEXT_CURATION` does not
  exist yet (it lands with CHO-271), so both arms are identical by construction
  and there is nothing to compare — record it and move on. It flips to
  `"comparison"` automatically once anything in `app/` reads the flag.
* **`blockedHttpAttempts` / `freshdeskRequests`** should both be empty/zero. They
  are how "no upstream request was made anywhere in the sweep" is an observation
  rather than a claim.
* Reports never contain the API key, assistant text, or anything beyond what a
  case asserts on. The writer refuses to emit a file containing the key.

## Adding a case

Add `cases/eN_<name>.py` exporting a `harness.Case`, register it in
`cases/__init__.py`, and return through `harness.finish` so the shared
no-abstention assertion applies. Put every new envelope in `fixtures.py` — and if
the case is about staleness, give the spent and fresh variants **deliberately
different values**, because that is what makes "recited from memory" mechanical.
