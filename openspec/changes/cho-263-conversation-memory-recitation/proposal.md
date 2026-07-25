# CHO-263: conversation-memory-recitation

## Why

The original ticket bundled two ideas: collapse spent tool results to memos, and recite the
conversation's key facts back to the model each turn. **The first half is now CHO-271** (curated
`messages_for_model` view with deterministic per-tool stubs). This change retains only the second
half — a running key-facts block — and it is **conditional**: build it only if the recall failures
survive CHO-271.

The measured premise that validated the ticket, on a representative 15-turn session (real
`count_tokens`, envelopes built through the real code paths):

| Class | Share of history (12,628 tok) |
|---|---|
| all `tool_result` content | **91.3%** |
| assistant prose | 5.4% |
| assistant `tool_use` blocks | 1.5% |
| **the user's own words** | **1.8%** |

So the ticket's "the needle is ~3% of the context" was **conservative** — it is 1.8% of history and
1.2% of the whole prompt. CHO-271 moves the human-readable share of history from ~10% to ~45% by
removing distractor mass, which is the direct fix for the abstention failure mode (Chroma's
context-rot finding: Claude answers "that was not provided in the chat history" when the fact *was*
present, once enough distractor mass separates it from the question).

A recitation block is the *second* lever, and it is only worth its complexity if removing the
distractors is not enough. Deciding it by measurement rather than intuition is the whole point of
sequencing it after CHO-271.

## What Changes

- **If and only if** CHO-276's eval E1 (mid-thread report follow-up opens a seeded guided form) or E4
  (a fact stated at turn 2 is recalled at turn 14) still fail **after CHO-271 ships with curation on**,
  add a deterministic trailing **key-facts recitation block** to each model request.
- **Deterministic and server-rendered.** The block is rebuilt each request from structure that already
  exists: `flow_event` turns' `meta["slots"]` (`app/agent/events.py:112-117` — already structured,
  with `friendly_range()` giving both a human label and the ISO pair), plus the latest
  `open_report_form` seed, plus any open request the user made that has not been satisfied. **No model
  call, no summarizer** — a synthesized summary would be non-deterministic, would churn the cached
  prefix, and (per the numeric-fidelity finding behind CHO-271) must never restate figures.
- **Tail placement, zero cache cost.** The block is appended as a trailing `<system-reminder>` block
  *after* all history — the same mechanism and position the escalation / wrapup reminders already use
  (`loop.py:95-99`, `:305-308`) — so it sits after every cache breakpoint and can never invalidate a
  cached prefix. It is never stored, so the thread stays wire-faithful.
- **Content limited to labels.** Slot labels, ISO dates, flow names and short open-request summaries
  only — never currency amounts, credentials, file tokens or upstream fields, matching the existing
  memo guardrails.
- **Omitted entirely when there is nothing to recite** — a fresh thread's request is byte-identical to
  today's.

## Open decisions

- **Whether to build at all** is decided by the CHO-276 eval results after CHO-271's flag is on. If
  both E1 and E4 pass, close this issue as not-needed and record the measurement.
- If only the KB pronoun follow-up fails, the fix belongs in CHO-271's KB stub (add `topic`), not here.
- Whether the block also recites the user's own stated facts (amounts, reference numbers) or only
  app-derived slots. Reciting user figures re-introduces numbers into a derived artifact; if it is
  needed, quote the user's exact words rather than paraphrasing them.

## Capabilities

### Modified Capabilities

- `agent-loop`: each model request MAY carry a deterministic, server-rendered key-facts recitation
  block positioned after all conversation history — built from `flow_event` slots and open requests,
  never model-authored, omitted when there is nothing to recite.

## Impact

- **Backend only, and only if the gate opens**: `backend/app/agent/loop.py` (append the block beside
  the existing reminders), a small renderer (either in `app/agent/events.py` beside the memo renderers
  or a new `app/agent/recall.py`), `backend/tests/` coverage for the renderer plus a request-assembly
  test.
- **Spec delta**: `openspec/specs/agent-loop/spec.md` (ADDED — the recitation block).
- **Not touched**: the conversation store (the block is never stored), the SSE contract, the prompt
  constants and therefore `prompt_snapshots` / `prompt_hash`, the frontend.
- **Gates**: `cd backend && uv run pytest` green; the block is byte-stable for a given thread state;
  request bytes before the block are unchanged (assert the cached prefix is untouched); the CHO-276
  evals E1 and E4 flip from fail to pass with it on, with no regression elsewhere.
- **Blocked by CHO-271 and CHO-276** — CHO-271 must ship with curation on and the evals must be run
  before this change is justified.
- Linear: CHO-263 · branch `cho-263-conversation-memory-recitation`
