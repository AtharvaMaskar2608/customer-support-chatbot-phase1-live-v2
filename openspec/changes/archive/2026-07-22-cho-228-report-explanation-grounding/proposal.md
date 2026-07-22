# CHO-228: report-explanation-grounding

## Why

On 21 July testers found the bot's **P&L report explanation describing columns the report does not have**. Asked what its P&L report contains, the bot searched the KB and answered:

> *"Your Equity P&L Report … breaks down: Short-term capital gains/losses · Long-term capital gains/losses · Trading P&L · Realized P&L · Unrealized P&L · Charges & fees."*

None of `Short-term`, `Long-term`, `Trading P&L`, or `Charges & fees` are in the P&L report — the bot **bled in tax-report columns** (`Short Term` / `Long Term` belong to the *tax* report) and invented the rest. A **grounding failure** distinct from CHO-227's authority overreach: the bot did the procedurally-correct thing (searched the KB, which lists "Reports" as a covered topic) but produced a specific, wrong description of a specific document it cannot read.

## What Changes

The data this was blocked on arrived: the product owner supplied the **authoritative column layout for every report**. So rather than the weak fallback ("describe purpose, defer contents"), the bot now describes the **real** columns — grounded in a locked registry, never invented.

- **Column registry config** — `backend/content/column_registry.json`: per report (`pnl`, `tax`, `ledger`, `contract-note`, `holdings`), the ordered columns with **verbatim labels** and a **locked one-line gloss** each. Remote-updatable like `whats_new.json`. Static config — no client data, no credentials.
- **`get_report_columns(report)` tool** — `backend/app/columns.py`: returns the grounded columns + glosses for a report, plus an **ambiguity index** (labels shared across reports, e.g. `Net Qty` → P&L / tax / contract-note; light normalization strips a trailing `(…)` grouping so `Net Qty (Qty / Price / Amount)` matches plain `Net Qty`).
- **REPORT COLUMNS RULE** in the prompt (mirrors the **BROKERAGE RULE**): any question about what a report contains, what a field means, or how to read it MUST call `get_report_columns` and answer **only** from its result — labels verbatim, glosses as given; never enumerate, rename, or invent report columns from general knowledge or the KB; ambiguous field → ask which report; report not in the registry → don't list columns, offer to pull it. This **supersedes `search_knowledge_base`** for column questions — the KB path is exactly what produced the invented P&L columns.

Directly kills the bug: the P&L registry is `Security · Open · Buy · Sell · Net Qty · CL. Price · Realized P&L · Unrealized P&L` — the invented `Short-term / Long-term / Trading / Charges` are simply not there.

## Capabilities

### Modified Capabilities

- `agent-loop`: report column/field questions are grounded in the column registry via `get_report_columns` (verbatim labels + locked glosses); the model never enumerates, renames, or invents report columns from general knowledge or the KB, and disambiguates fields shared across reports.

## Impact

- **Backend**: new `backend/content/column_registry.json`; new `backend/app/columns.py` (loader + ambiguity index + `get_report_columns` handler); `tools.py` registers the tool; `prompt.py` adds the tool bullet + the REPORT COLUMNS RULE. Tests in `tests/test_columns.py` including the P&L-invented-columns regression.
- **Additive, no client data, no creds** (static config). `uv run pytest` → 447 passed (the two tool-count guards updated 11 → 12). Cache prefix grew 4972 → **5344** tokens (still ≥ 4096; write→read verified on Haiku).
- Linear: CHO-228 · branch `cho-228-report-explanation-grounding`.

## Superseded

The earlier KB spike (read `qa_chunks` to find where the columns came from) is moot — the product owner supplied the authoritative registry, so we ground on that instead of the KB. Any KB content describing report internals is now superseded for column questions by the REPORT COLUMNS RULE.

## Open follow-up (not this change)

Finer within-report disambiguation (e.g. a bare "WAP" matching both `Buy WAP` and `Sell WAP`) and fuzzy label variants (`Security` / `Security Name` / `Security Name/Symbol`) are refinements on top of the exact-normalized ambiguity index shipped here.
