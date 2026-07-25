# CHO-271 — design

## What the code already guarantees (verified, with line refs)

| Fact | Where |
|---|---|
| `thread.messages()` is the **only** production consumer of the store's wire array | `app/agent/loop.py:303` (the only non-test `.messages()` call in the repo) |
| Merge + partition: consecutive user-role turns merge into one message; `tool_result` blocks stable-partitioned first | `app/agent/store.py:171-191` (partition at `:186-188`) |
| A stored `tool_result` block is `{content: str, is_error: bool, tool_use_id: str, type: str}` with canonical key order; `content` is a **string** (compact sorted-key JSON of the envelope) | `loop.py:410-427`, `tools.py:488-493`, `store.py:109-118` |
| `meta` on a `tool_result` turn is `{tool_name, is_error, duration_ms}`, persisted as jsonb → survives rehydration | `loop.py:422-426`, `store.py:522-531` |
| Artifact-only rounds return before any continuation call — the model **never saw** those envelopes in that turn | `loop.py:463-479` |
| Mixed / errored rounds DO send the envelope verbatim in the same turn's continuation call | `loop.py:485-488` |
| Ticket transcripts and the CHO-241/270 affirmation guard read `thread.turns` (`user_text` / `assistant_text`), never the wire array | `tickets.py:62`, `:114-119`, `:213-238` |
| `caps.evaluate` reads `turn.kind` + `turn.meta["is_error"]`, never content | `caps.py:44-46`, `:61-88` |
| Traces record `redact(user_input)` + output + usage — **not** the messages array | `tracing.py:339-375` |
| `Thread` already carries non-persisted transient fields (CHO-246 `first_name`, `name_fetched`) | `store.py:160-165` |
| `list_contract_notes` ids are opaque, session-bound, **600 s** capability tokens | `reports/contract_notes.py:142` (`ttl_seconds: float = 600.0`), minted at `:300` |
| Installed `anthropic==0.117.0` exposes `context_management` / `clear_tool_uses_20250919` **only** on `client.beta.messages.*` | `.venv/.../types/beta/beta_clear_tool_uses_20250919_edit_param.py` |

**Consequence, and the entire safety argument for this change:** the curated view is a one-line
change at `loop.py:303`. No other subsystem — tickets, caps, feedback anchors, traces, the SSE
contract, the training corpus — can observe it.

## Evidence, and what each piece changes in the design

**(a) Anthropic's context editing results (+29%, +39% with memory, 84% token reduction on 100-turn
evals).** Validates the *mechanism class*: clearing spent tool results is the lightest-touch
compaction and it improves task performance, not only cost. It does **not** transfer as a number —
those runs are 100-turn / 100k-token regimes where a token threshold fires. Our sessions are 10–15
turns and ~19k tokens of total prompt, so the same feature would never trigger here. Directional
prior only; our own measurements are the forecast.

**(b) Chroma's context-rot work: Claude's documented long-context failure is ABSTENTION** — "I
cannot determine… that was not provided in the chat history" when the fact *was* present, once
enough distractor mass separates fact from question. Two design consequences, both adopted:

1. The intervention target is **removing distractor mass**, not adding instructions.
2. **Stub wording must never read as an absence claim.** A stub that says only "data removed" is the
   wording most likely to *induce* the failure we are fixing. Every template therefore ends with an
   actionable recovery clause ("call `get_holdings` again if you need them"), and the eval gate
   asserts on abstention phrasing explicitly.

**(c) Compaction-style summarization preserved 3/3 high-level facts but 0/3 exact numeric table
cells.** Disqualifying for a financial assistant whose payloads *are* numeric cells — holdings
valuations, ledger amounts, capital-gains figures, brokerage rates. Hard invariant: **never
summarize numbers; make them re-fetchable.** Stubs carry counts, labels, ISO dates and ids only. A
stale ₹ figure paraphrased into a memo is strictly worse than an explicit "call the tool again": it
is unfalsifiable to the model and would be quoted to a customer as current.

## Build, not adopt — why server-side context editing is rejected for this phase

`BetaClearToolUses20250919EditParam` in the installed SDK exposes `trigger`
(`input_tokens` | `tool_uses`), `keep`, `clear_at_least`, `clear_tool_inputs`, `exclude_tools`, and
reports `cleared_tool_uses` / `cleared_input_tokens`.

| Axis | `clear_tool_uses_20250919` | This change |
|---|---|---|
| Would it even fire? | `input_tokens` triggers are tuned for 100k-class agents; our whole prefix at turn 14 is ~19k tok, so it never fires. A `tool_uses` **count** trigger cannot distinguish a 55-tok file envelope from a 3,250-tok money envelope. | Rule is per tool class, per turn boundary. |
| Selectivity | `exclude_tools` is **name-only**: cannot keep `is_error=True` results while clearing successes of the same tool; cannot keep ids-only from `list_contract_notes`. | Exactly the class table below. |
| Recovery text | Prunes to a placeholder **we do not author** — no "call `get_holdings` again", no id map, no columns rule. Removes noise, adds no signal, and an unauthored placeholder is the abstention trigger from (b). | The stub text *is* the added signal. |
| Migration cost | `client.messages.stream` → `client.beta.messages.stream(betas=[…], context_management=…)`: a beta migration on the single hot-path call site the whole loop is built around (`loop.py:330-334` via `tracing.observe_model_round`) of a shipped, live product. | One line at `loop.py:303`, behind a flag. |
| Cache boundary | Server-side clearing rewrites prefix bytes at a boundary chosen by a threshold we do not control. | Boundary is ours and provably monotone. |

**Verdict: build.** Never hybrid — two independent prefix-mutating layers with different boundaries
is untestable cache behaviour. If the loop ever moves to the beta path for other reasons, the natural
companion is `clear_thinking_20251015` (thinking is off here anyway), not `clear_tool_uses` layered
on stubs.

**`compact_20260112` is permanently ruled out for this product**, not merely deferred: 0/3 fidelity
on exact numeric table cells (see (c)), unsupported on `claude-haiku-4-5` (a configured model
option), its usage lands in `usage.iterations` which `app/agent/trace_cost.py:14-27` does not read
(silently breaking cost accounting), and it holds the stream open — touching the pinned SSE contract.

## What "spent" means — the rule

Deterministic, keyed only on `meta["tool_name"]`, `meta["is_error"]` and turn `seq`.
**Opt-in by tool name, fail-open**: an unregistered tool is never curated.

| Class | Tools | Rule | Why |
|---|---|---|---|
| **Never — failures** | any result with `meta["is_error"] is True` | verbatim forever | The error content *is* the corrective instruction (the `get_pnl_report` bounce says to call `open_report_form` instead; the CHO-241 guard says not to raise a ticket unless the user asked). ≤~60 tok each, and keeping them prevents retry loops. `AUTH_EXPIRED` short-circuits anyway (`loop.py:485`). Keeps the existing error-bounce test byte-stable. |
| **Never — routing / state** | `open_report_form`, `raise_support_ticket` | verbatim forever | 69–110 tok and ~38 tok measured. The `open_report_form` envelope carries `flow` + `seed` + `prefilled` + `note` (`forms.py:170-177`) — it is the strongest in-context exemplar of the exact behaviour this change exists to reinforce. The ticket envelope is followed by a `flow_event` memo anyway (`loop.py:439-456`). |
| **Artifact → stub at K=1** | `get_holdings`, `get_money_transactions`, `get_brokerage_rates`, `get_pnl_report`, `get_ledger_report`, `get_capital_gains_report`, `download_contract_note` | verbatim within its own turn; stubbed from the next user message onward | Artifact-only rounds short-circuit (`loop.py:463-479`), so from the next turn the stub removes bytes the model never used. On a mixed or errored round K=1 still keeps the verbatim copy for the continuation call that needs it. A 4,889-tok money envelope sitting above *"now the same for MTF"* is exactly the distractor mass. |
| **Narrated — KB → provenance-preserving stub at K=1** | `search_knowledge_base` | keep the matched `question` strings; drop `answer` / `tat` / `score` | The assistant's own reply (verbatim forever) is the distillation. Real corpus: question mean 42.9 chars → 10 questions ≈ 430 chars ≈ **~120 tok vs ~940 verbatim (7.8×)**, and a "tell me more about that" follow-up can see *what was found* and reformulate its search instead of abstaining. |
| **Narrated — columns → stub at K=1, labels dropped** | `get_report_columns` | count only | The opposite case to KB: the REPORT COLUMNS RULE (`prompt.py:186-192`) mandates answering only from a fresh result, so a stub retaining labels invites describing a column from its label alone. |
| **Id-bearing → id-preserving stub at K=1** | `list_contract_notes` | every `id ↔ date/segment` pair (40 newest + omission line), expiry stated; drop `month`, `badge`, JSON framing | `download_contract_note`'s schema says the id "MUST be a note id returned by `list_contract_notes` earlier in this conversation — never invent or guess" (`tools.py:258-270`). Dropping ids either breaks downloads or invites fabricated ids. 642 → ~240 tok for 20 notes. |

**K = 1, pinned per class in code.** Pinning per class (rather than one global K) means raising
narration K later can never leak a stale data envelope forward.

### Rejected alternatives, and why

- **K=2 for narrated KB results.** The honest lever, and wrong. Under K=2 the deepest permanently
  frozen position moves back to the *second*-newest user turn (turn N−1's results are still verbatim
  inside the prefix ending at `U_N`), so the per-turn write delta roughly doubles and the cross-turn
  block gap doubles — pushing far more turns past the 20-block cache lookback. It buys grounding by
  paying with the exact property the whole scheme rests on. **Replaced by the provenance-preserving
  KB stub** (keep `question`, drop `answer`/`tat`/`score`), which buys the same grounding for ~120
  tok and no boundary movement. If the pronoun-follow-up eval still fails, add `topic` to the stub —
  never raise K.
- **`AGENT_CURATION_KEEP_TURNS` env knob (dropped).** Read from `os.environ` per call, so flipping it
  mid-thread moves the curation boundary and therefore the readable cache anchor depth; worse,
  `thread.curated` memoises by `seq` only, so a K change would serve stale stubs. **One flag only:
  `AGENT_CONTEXT_CURATION`.** K lives in code.
- **K=0 (stub immediately).** Strips the envelope from the continuation call of a mixed round,
  breaking the mixed-artifact-and-KB narration semantics the loop tests pin.
- **"Stub-from-birth" for short-circuited rounds (a `meta["round_short_circuited"]` field + a
  dispatch-loop refactor).** A **no-op** under K=1: `U[-1]` is appended *before* the loop
  (`loop.py:274-279`), so a short-circuited round's results already satisfy `seq < W` at the first
  call of the next turn — such a result is never sent verbatim to any model call. The wire array
  would be byte-identical, and no cache entry ever covers those bytes either way (the entry written
  by round *r*'s call ends at round *r−1*'s results). It is also undecidable at the one moment it
  would matter: during a mixed round's continuation call the assistant turn has not been appended yet
  (`loop.py:354` runs *after* the call), so the code cannot distinguish "will continue" from
  "short-circuited". Rejected: no meta field, no loop refactor.
- **`list_contract_notes` verbatim until a download happens.** The trigger can fire *mid-turn*,
  changing prefix bytes between rounds of one turn. Violates within-turn stability.
- **Summarize instead of stub.** See evidence (c): 0/3 numeric-cell fidelity is disqualifying here.
- **A ₹/decimal regex guard over stub output.** Wrong as specified: real KB questions legitimately
  contain `₹` (FAQ rows about charges), so a blanket "no currency symbol in any stub" assertion is
  either flaky or forces a worse stub. Replaced by a **per-renderer key whitelist** — each renderer
  may read only count / length / customer-facing-label / ISO-date / id keys — plus a test asserting
  no amount-bearing key appears in any whitelist.
- **Curating assistant `tool_use` inputs.** ~12–30 tok each and they are the routing exemplars.
  Keeping them also lets the KB and notes stubs say "the query/range in the call above" instead of
  restating it.

## Stub templates

Frame mirrors the shipped app-event memo (`events.py:25`) with a distinct noun, so a curation note is
never confused with an app *event* (something the user did):

```python
_FRAME = "[App note — generated by the app, not typed by the user]"
```

Every string is a pure function of the stored `content` JSON plus `meta["tool_name"]`. **No clock, no
model call, no request state.** Counts, labels, ISO dates and ids only.

```
get_holdings           ok    {F} get_holdings result cleared. The holdings card rendered in the chat
                             with {totals.count} holdings (value, invested, P&L and day change shown
                             to the user). The figures are no longer in this transcript — call
                             get_holdings again if you need them.
                       empty {F} get_holdings result cleared. The user has no holdings; the
                             empty-state card rendered in the chat.

get_money_transactions ok    {F} get_money_transactions result cleared. The money-movements card
                             rendered in the chat with {len(txns)} pay-in/pay-out transactions for
                             the current financial year. The figures are no longer in this
                             transcript — call get_money_transactions again if you need them.
                             [ One direction was unavailable for that card.]   <- iff partial
                       empty {F} … The user has no money movements this financial year; the
                             empty-state card rendered in the chat.

get_brokerage_rates    ok    {F} get_brokerage_rates result cleared. The brokerage rate card
                             rendered in the chat with {len(groups)} rate groups. The rates are no
                             longer in this transcript — call get_brokerage_rates again if you need
                             them.

file envelopes         dl    {F} {tool} result cleared. The file {file.name} was delivered in the
(pnl / ledger / tax /        chat as a download card. The download link is no longer in this
 download_contract_note)     transcript — run the report again if the user wants it re-sent.
                       email {F} {tool} result cleared. The report was sent to the user's registered
                             email, as confirmed in the chat.      <- never echo emailMasked

search_knowledge_base  ok    {F} search_knowledge_base result cleared, matched questions kept. The
                             search above returned {len(results)} support answers, which you already
                             used in your reply — {question}; {question}; … The answer text is no
                             longer in this transcript — search again if the user follows up on any
                             of them.

get_report_columns           {F} get_report_columns result cleared. The column list for the {report}
                             report ({len(columns)} columns) was returned and you already used it.
                             The labels are no longer in this transcript — call get_report_columns
                             again before describing any report column.

list_contract_notes    n>0   {F} list_contract_notes result cleared, ids kept. {n} contract notes
                             were returned for the range in the call above and offered to the user.
                             Ids for download_contract_note — {id} = {date} {segment}; … These ids
                             expire about 10 minutes after they were issued; if a download bounces,
                             call list_contract_notes again.
                             [ Older ids were dropped — call list_contract_notes again with a
                             narrower range if the user asks for one of those.]   <- iff n > 40
                                                              (keep the 40 newest; list is ascending)
                       n==0  {F} list_contract_notes result cleared. No contract notes exist for the
                             range in the call above.

fallback (registered tool, unparseable / legacy content such as "{}" or missing meta):
                             {F} {tool} result cleared. Its result was already delivered to the
                             user; the data is no longer in this transcript — call {tool} again if
                             you need it.
```

Worked example — holdings, 12 rows, **730 tok → 65 tok**:

> `[App note — generated by the app, not typed by the user] get_holdings result cleared. The holdings
> card rendered in the chat with 12 holdings (value, invested, P&L and day change shown to the user).
> The figures are no longer in this transcript — call get_holdings again if you need them.`

Only the `content` **string** is replaced; `type`, `tool_use_id` and `is_error` are copied through
unchanged, so the `tool_use`/`tool_result` pairing invariant and the `store.py:186-188` partition both
hold untouched. Every template ends with a recovery clause on purpose: the failure mode being fixed is
abstention, so the model must be told what to *do*, not merely that data is gone.

## Boundary: the watermark

- `U` = `seq`s of `user_text` turns in order. `U[-1]` is the current message, appended at
  `loop.py:274-279` **before** the loop, so it is present for every round.
- **Watermark** `W = seq(U[-1])`. A `tool_result` turn is curated iff `turn.seq < W` **and** its tool
  is registered **and** `meta["is_error"] is not True`.

Three properties, each load-bearing:

1. **Within-turn stable.** `W` depends only on `user_text` turns. Mid-turn appends are `tool_result`
   and `flow_event` (widget completions, ticket memos) — neither is `user_text` — so `W` cannot move
   between rounds of a turn.
2. **Monotone.** `W` only increases; once `seq < W`, always `seq < W`. A turn is stubbed once and
   stays stubbed.
3. **Byte-deterministic.** Stub text is a pure function of stored bytes, so two requests at the same
   watermark produce identical bytes.

**Why curation and CHO-264 compound rather than fight.** Tool results are appended *after* their user
message, so with K=1 the deepest position that can never change again is the end of the newest
`user_text` content block: everything before it is stubbed-or-final, everything after it is this
turn's still-verbatim results, which flip to stubs next turn. A stub rewrite therefore never touches
bytes at or before that anchor, and the cache entry written there survives every future watermark
advance. It is **not** true that curation invalidates nothing (the recall design claimed this and it is
wrong): the entries written *inside* turn N, at rounds 2..k, carry turn N's verbatim results in their
prefix and die the moment the watermark advances — see the note below.

**Two pieces of proposed cross-track machinery are rejected as redundant:**

- **A dedicated "deep anchor" 4th cache breakpoint plus a `curation.breakpoint_anchor()` API.** At
  round 1 of every turn the last block of the last *stored* message already **is** the newest
  `user_text` block — turn N−1's trailing `tool_result` turns merge with `U_N` and the partition puts
  results first, so `U_N` is last (and if a `flow_event` memo landed, the last block is that memo,
  equally frozen). CHO-264's per-round rolling tip marker therefore writes an entry at the frozen
  anchor **for free, every turn**. A separate anchor breakpoint buys nothing and spends a breakpoint
  slot CHO-264 needs for its conditional insurance marker.
- **A formal cross-track contract with CHO-264.** Unnecessary for the same reason. What is worth
  recording instead is the honest cache consequence: every **intra-turn** cache entry of turn N
  (rounds 2..k) has turn N's verbatim results in its prefix and dies when the watermark advances.
  That is CHO-264's cross-turn lookback problem to solve (measured 20–37 blocks for 3–5 round
  multi-parallel turns), and it is a property of curation being *correct*, not a defect.

Note also that the minimum cacheable prefix is a **prefix** rule, not a delta rule: the ~6,559-tok
frozen system+primed prefix is always included, so a small curated history is still cacheable on
`claude-sonnet-4-6` (1,024) and `claude-haiku-4-5` (4,096). "Stubbing makes history too small to
cache" is a wrong intuition.

## Integration

**`store.py` — one optional parameter; the default path stays byte-identical:**

```python
@dataclass
class Thread:
    ...
    # CHO-271: read-time curation cache (seq -> stubbed content blocks).
    # Transient like first_name/name_fetched — derived, never persisted.
    curated: dict[int, list[dict[str, Any]]] = field(default_factory=dict)

    def messages(
        self,
        *,
        transform: Callable[[Turn], list[dict[str, Any]] | None] | None = None,
    ) -> list[dict[str, Any]]:
        """`transform` (CHO-271) may return replacement content for one turn;
        None keeps the stored bytes. Callers that pass no transform get the
        lossless array, byte-for-byte as before."""
        for turn in self.turns:
            content = (transform(turn) if transform is not None else None) or turn.content
            ...  # existing merge + tool_result-first partition, unchanged
```

Merge/partition logic stays in exactly one place, and every existing `messages()` test is untouched
because the default is `None`.

**New `backend/app/agent/curation.py`** (pure; imports `Thread` / `Turn` for typing only):

```python
_FRAME = "[App note — generated by the app, not typed by the user]"
_KEEP_VERBATIM = frozenset({"open_report_form", "raise_support_ticket"})
_RENDERERS: dict[str, Callable[[dict], str]] = {...}   # tool name -> envelope -> text
_ALLOWED_KEYS: dict[str, frozenset[str]] = {...}       # per-renderer key whitelist
_MAX_NOTE_IDS = 40

def watermark(thread: Thread) -> int: ...          # seq of the newest user_text turn, else 0
def stub_blocks(turn: Turn) -> list[dict] | None:  # None = keep verbatim; never raises
def curate(thread: Thread) -> Callable[[Turn], list[dict] | None]:   # memoises in thread.curated
def messages_for_model(thread: Thread) -> list[dict]:
    return thread.messages(transform=curate(thread))
```

**`loop.py:298-304`** — the single call site:

```python
        messages = (
            agent_prompt.primed_messages(...)
            + (
                agent_curation.messages_for_model(thread)
                if config.agent_context_curation()
                else thread.messages()
            )
        )
```

**`config.py`** mirrors `tracing_enabled()` (`:330-336`) — one flag, **default off at merge**:

```python
def agent_context_curation() -> bool:
    """Curated messages_for_model view (AGENT_CONTEXT_CURATION env, default off
    until the CHO-276 routing evals pass on prod)."""
    return os.environ.get("AGENT_CONTEXT_CURATION", "0").strip().lower() in {
        "1", "true", "yes", "on",
    }
```

Playground (CHO-272) inherits the flag, which is correct — drafts should see the production view.

## Observability

Traces persist `redact(user_input)`, output and usage (`tracing.py:339-375`) but **not** the messages
array, so a curation bug is invisible in the trace viewer today. Add two counts to the `llm` span
metadata — `curated_turns` and `history_tokens_est` — passed in from the loop through an optional
`extra: dict | None = None` on `observe_model_round` and merged into `span.metadata`. Counts only, no
text: ~5 lines, and the flag's effect becomes visible without a special eval run.

## Cost, for completeness

Weights: cache read 0.1×, ephemeral write 1.25×, uncached 1.0×; prices from `trace_cost.py:17-22`,
INR ×96.46 (`config.py:383`). Representative 15-turn session:

| Scenario | INR | final history |
|---|---:|---:|
| today (frozen prefix cached, history re-billed every call) | ₹42.35 | 12,628 tok |
| CHO-264 only (rolling breakpoint + relocated live tail) | ₹14.31 | 12,628 tok |
| **CHO-264 + CHO-271 (curated)** | **₹9.89** | **~2,323 tok** |

Marginal turn-15 cost ₹3.86 → ₹0.61 → **₹0.31**. `tool_result` content falls from 91.3% of history;
the human-readable share (user + assistant prose + memos) rises from ~10% to ~45%. Again: the table
exists to prove curation does not *cost* anything, not to justify it.

## Merge protocol (state this prominently in review)

1. Merge with **`AGENT_CONTEXT_CURATION=0`** — unit tests green, wire bytes identical to today with
   the flag off.
2. Run the **CHO-276 routing evals** with the flag off and on, 3 attempts each. Gate: mid-thread
   seeded form / no-stale-figures / turn-2-fact-at-turn-14 / columns / KB pronoun follow-up each ≥2/3
   with **no regression vs off**; note-id survival and the ticket affirmation guard **3/3** (the note
   run must finish inside 10 minutes, or the id expiry makes it a false green); **zero**
   abstention-regex matches.
3. Flip the env var on prod; confirm `history_tokens_est` drops and `cost_inr` falls again on
   ≥5-turn threads.
4. A **follow-up commit** changes the default to on.

Behavioural risk earns a gate the cache work does not need — hence the flag and the separate default
flip. **Blocked by CHO-276**, which owns the eval harness.

## Residual risks, named

1. **KB grounding on pronoun follow-ups at K=1.** Mitigated by the provenance-preserving stub; the
   pronoun-follow-up eval is the detector. If it fails, enrich the stub (add `topic`), never raise K.
2. **`list_contract_notes` id expiry (600 s)** makes any id-based recovery brittle and the note eval
   time-sensitive. Pre-existing: today's verbatim history already offers dead ids silently; the stub
   at least states the expiry and the recovery.
3. **Cross-turn cache lookback misses** after a multi-parallel or wrapup turn once intra-turn entries
   die at the watermark advance. CHO-264's problem, bounded and self-healing, not a curation defect.
4. **Token figures for the stub sizes are estimates** from exact key sets; the audit's `count_tokens`
   figures are the quotable ones. Verify `history_tokens_est` against `agent_traces.input_tokens`
   after the flag flip.
5. **KB answer-length variance**: long answers push a `top_k=10` envelope past 2,000 tok, which
   strengthens the case (and is the same lever as a `top_k` reduction — deliberately out of scope).
6. **Anthropic's +29% / 84% figures do not transfer** to a 15-turn / 19k-token session. Our own cost
   and eval numbers are what this design should be held to.

## Non-goals

- Any mutation of the lossless store, and any change to replay, ticket transcripts, caps, feedback
  anchors or the training corpus.
- Summarization or compaction of tool results (permanently out — numeric fidelity).
- The server-side `context_management` beta path.
- The key-facts recitation block — CHO-263, conditional on the eval outcome after this ships.
- Tool-result size reduction at the source (row caps, `top_k` tuning, model-vs-UI field splits).
