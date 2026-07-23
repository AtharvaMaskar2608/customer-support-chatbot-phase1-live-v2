# CHO-242: rename-askfinx

## Why

Product wants the assistant rebranded from **"Choice Jini"** to **"AskFinX"** (CHO-242). The name appears in the bot's self-identity (system prompt), the chat/composer, the widget launcher, the What's new modal, the browser tab, and the Freshdesk ticket subject. Some of these are customer-facing (rename); others are **programmatic identifiers that must not change**, or existing embeds / support routing break.

## What Changes

- Rename the **customer-facing** assistant name to **"AskFinX"** everywhere it is shown:
  - System-prompt identity — "You are AskFinX …" and "continue as AskFinX" (`prompt.py`); the bot refers to itself as AskFinX.
  - Frontend display: chat composer aria-label, What's new modal ("What's new in AskFinX"), browser tab title, parked header title, launcher bubble / iframe titles.
- **Keep programmatic identifiers unchanged** for back-compat and support routing:
  - The embed API `window.ChoiceJini` / `ChoiceJini.init` — host sites integrate with this exact snippet; renaming breaks every live embed.
  - The `choiceJini.whatsNew.seenVersion` localStorage key — changing it re-shows What's new to everyone.
  - Freshdesk internal routing constants — the `choice-jini` tag and `cf_*` custom-field values (support filters key off them).
- Backend prompt + frontend display strings. No API/contract change.

## Open decisions

- **Embed API name**: keep `window.ChoiceJini` (recommended — back-compat). A `window.AskFinX` alias can be added later.
- **Freshdesk ticket subject** (`[Choice Jini] …`, seen by support agents): keep it as an internal ops label by default (so this change does NOT touch the support-escalation ticket contract that CHO-245 modifies). If you want the subject rebranded to `[AskFinX]` too, we sequence CHO-242 before CHO-245.

## Capabilities

### Modified Capabilities

- `agent-loop`: the system prompt SHALL identify the assistant as "AskFinX" (self-identity and identity-override resistance use the new name); programmatic identifiers and internal routing constants are unaffected.

## Impact

- Backend: `backend/app/agent/prompt.py` (identity lines) — prompt-hash changes (expected).
- Frontend (display strings only): `index.html` title, `WhatsNewModal.tsx`, `chat/ChatShell.tsx` aria-label, `App.tsx` parked header, `widget/widget.ts` launcher / iframe titles + log tag. Keep `window.ChoiceJini`, `ChoiceJini.init`, and `choiceJini.*` keys.
- Internal, unchanged by default: Freshdesk `choice-jini` tag + `cf_*` values (+ ticket subject unless the decision above flips).
- `tsc`/lint/build (FE) and `uv run pytest` (BE, prompt snapshot) gates. Visible change → screenshot.
- Linear: CHO-242 · branch `cho-242-rename-askfinx`.
