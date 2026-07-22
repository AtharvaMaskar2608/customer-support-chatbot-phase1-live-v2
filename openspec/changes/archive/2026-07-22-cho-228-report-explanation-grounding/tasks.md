# CHO-228: report-explanation-grounding — tasks

## 1. Column registry config
- [x] 1.1 `backend/content/column_registry.json` — per report (`pnl` / `tax` / `ledger` / `contract-note` / `holdings`), ordered columns with verbatim labels + a locked one-line gloss each; remote-updatable (whats_new posture). Tax carries its two tables (A. Transactions, B. Summary) via a per-column `section`.

## 2. Loader + tool
- [x] 2.1 `backend/app/columns.py` — `load_registry()` (per-request read, no restart), `ambiguity_index()` (normalized label → sorted report keys; light normalization drops a trailing `(…)` so grouped labels match plain siblings).
- [x] 2.2 `get_report_columns(report)` handler — returns `{report, title, note, columns, ambiguousLabels}`; unknown report → `ToolError` naming the valid set. No credentials (static config).
- [x] 2.3 Register `get_report_columns` in `tools.py` with a `report` enum schema.

## 3. Grounding rule
- [x] 3.1 `prompt.py` — add `get_report_columns` to the tool list + the REPORT COLUMNS RULE (mirrors BROKERAGE): MUST call `get_report_columns` and answer only from its result — labels verbatim, glosses as given; never enumerate/rename/invent from general knowledge or the KB; ambiguous field → ask which report; report not in registry → offer to pull it. Supersedes `search_knowledge_base` for column questions.

## 4. Verify
- [x] 4.1 `tests/test_columns.py` — registry loads with all 5 report keys; every column has a label + gloss; **regression**: P&L returns only its real columns (no Short-term / Long-term / Trading / Charges; those live in Tax); unknown report → ToolError; ambiguity index (`Net Qty` across pnl/tax/contract-note, `ISIN` across tax/contract-note); result flags `ambiguousLabels`.
- [x] 4.2 `uv run pytest` → 447 passed, 2 skipped (tool-count guards updated 11 → 12).
- [x] 4.3 Cache: cacheable prefix grew to 5344 tokens (≥ 4096), cache write→read confirmed on Haiku.

## 5. Ship & sync
- [ ] 5.1 `git-sync` with issue key CHO-228 (push + PR).
- [ ] 5.2 `linear-connector` — summary comment + state on merge.
- [ ] 5.3 Ships in a backend image (new tool + prompt + config) — fold into the next deploy after v1.0.7.
