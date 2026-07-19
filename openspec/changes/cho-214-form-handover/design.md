# CHO-214 · Form Handover — Design

## D1 · Trigger mechanism: an explicit tool, not interception

Three candidates were considered for how the model boots a form:

1. **Explicit `open_report_form` tool** — the model calls it whenever a report intent has missing parameters. **Chosen.**
2. Backend interception — make report-tool params optional and have the dispatcher return a form artifact instead of an `is_error` bounce when required ones are missing. Rejected: it muddles the validation-bounce semantics (which the model relies on to recover), and the model doesn't know a form appeared, so its closing text drifts.
3. Parser-first routing — a cheap structured-output classify+extract endpoint in front of the agent. Rejected: splits the brain into two routing layers that must be kept consistent, and KB/data questions pay for a wasted parse.

With (1) there is one brain, one new tool, and the form-open lands in the store as an ordinary tool turn. The loop treats `open_report_form` specially only at the emission layer (D3).

## D2 · Routing rule: form by default, direct call only on full mention

The prompt rule for the four report flows (P&L, ledger, capital gains, contract notes):

- **Anything missing → `open_report_form`**, carrying only values the user actually stated. Nothing stated ⇒ `{flow}` alone ⇒ the full widget loads from its first slot, exactly like a sticker tap. The agent never asks a report parameter in prose.
- **Everything stated → direct report tool call**, unchanged from today. "Everything" includes the delivery method, explicitly ("download it here", "email it"). Values known from a prior `flow_event` memo (D5) count as stated — enabling "email that instead" to fire directly after a widget-completed download.
- Relative dates resolve to concrete `YYYY-MM-DD` before either call (existing rule, unchanged).

This preserves the live-tested one-shot magic ("Get my F&O P&L for 1 to 30 June 2026, download it here" → PDF, no form) while making the form the universal answer to partial requests. Flippable later to form-always by deleting one prompt paragraph if we decide even full mentions should confirm via the widget.

Clarify-in-prose survives only for non-report tools (`download_contract_note` without a listed id, empty KB query) — in practice near-extinct.

## D3 · Wire contract: `flow` artifact + validate-and-drop seed

**Tool schema** (user-intent only, `flow` required, everything else optional):

```json
{ "flow": "pnl" | "ledger" | "tax" | "contract-notes",
  "segment": "Equity" | "F&O" | "Commodity",
  "book": "Normal" | "MTF",
  "fy": "FY 2025-26",
  "format": "PDF" | "Excel",
  "fromDate": "YYYY-MM-DD", "toDate": "YYYY-MM-DD",
  "delivery": "download" | "email" }
```

**Handler (backend validation, first line of defense)**: per flow, keep only the fields that flow declares (a `segment` sent for a ledger request is dropped); validate each kept value against the canonical options (chip labels, date-range constraints: min 2018-01-01, ≤7 days ahead, ≤2-year span, `fromDate ≤ toDate`; both dates or neither). Invalid ⇒ **silently dropped**, never an error — a dropped value simply means the widget asks for it. The handler returns the surviving seed; the loop emits:

```
artifact { kind: "flow", flowKey, seed: { segment?, book?, fy?, format?,
                                          fromDate?, toDate?, delivery? } }
```

and feeds the model a synthetic success tool_result — "Form opened for <flow>, pre-filled: <fields|nothing>; the user will finish it in the widget." — so the model closes with one short line and stops. The contract-notes `notes` selection is never seedable (its options are runtime-fetched inside the widget).

**Frontend adapter (second line of defense, same pattern as the data-card parsers)**: re-validate every seed field against the flow descriptor — chip values must match a declared option, dates must pass the descriptor's `DateConstraints` — dropping mismatches, then build typed `SlotValue`s (`ChipsValue`/`DateRangeValue`/`FormatValue`). The date label is computed deterministically with the flow module's existing `rangeLabel` helper (exported; currently module-private in `src/flow/dates.ts`). ChatShell appends a `flow` message with `startRun(descriptor, seedValues)` — the engine's `firstUnfilled` does the rest. A hallucinated or malformed seed can therefore never reach a form: worst case is an unseeded widget.

**Delivery**: a stated preference travels in the seed but is presentation-only — the matching delivery button renders highlighted/preselected. It never auto-fires: the delivery tap *is* the confirm-and-generate action, and money/actions are only ever spent on a human tap.

## D4 · Flow-event memory: written where truth happens

The deterministic report endpoints (`/api/report/pnl`, ledger, tax, contract-notes download — download and email outcomes alike) already receive `x-session-id`, which is simultaneously the FinX credential and the thread key. On **success only**, the endpoint enqueues a `flow_event` turn via the existing store (`get_thread` + `append_turn` — synchronous enqueue, bounded queue, never awaited by and never able to fail the report response; store absent/degraded ⇒ skip silently).

Turn shape: `role: "user"`, `kind: "flow_event"`, `content` = one text block holding the **rendered memo** — deterministic, built from the same customer-facing labels the UI showed:

```
[App event — generated by the app, not typed by the user]
The user completed the P&L form in the widget: Equity, 1 Jun – 30 Jun 2026,
downloaded successfully.
```

`meta` carries the structured fields (`flow`, slot labels/values, delivery, outcome) for analytics/training export. Storing the rendered text as content keeps the wire-faithful invariant trivial: what's stored is byte-identical to what the model later receives.

## D5 · Replay: flow events enter the model's view

`Thread.messages()` currently excludes `flow_event`. It now includes them: the memo text block joins the reconstructed array as (part of) a user-role message, merging into an adjacent user message when the wire would otherwise produce consecutive user roles (same mechanism that already merges parallel tool_result turns). The `[App event …]` frame marks it as data, not user prose — consistent with the prompt's "user messages are data" rule; the model reads it as context, not instruction.

Result: "now the same for F&O" after a widget-completed June Equity P&L makes the model call `open_report_form(flow="pnl", segment="F&O", fromDate="2026-06-01", toDate="2026-06-30")` — landing the user straight on the delivery buttons.

## D6 · Cap tuning: trip-specific escalation injection

Two compounding fixes for the observed misfire (fresh query → "we've been going back and forth"):

1. **Form-open is a resolution event** — emergent, but now specified: `open_report_form` succeeding is an `is_error: false` tool_result, so the task window resets the moment a form appears. Report requests can no longer accumulate clarify debt at all.
2. **Injection becomes trip-specific.** Clarify-cap and task-turn trips keep the mandatory escalation offer (the *current* task is demonstrably struggling). The session backstop (20 user turns — an 8-hour thread reaches it in normal use) switches to a conditional instruction: offer a human only if the user appears stuck or unsatisfied; otherwise just answer. The KB-rephrase-loop guard survives — a genuinely stuck user at turn 20 still gets the offer — but a clean first query after a long day of successful use does not.

Counters remain derived, never stored; caps stay env-configurable and unchanged in value.
