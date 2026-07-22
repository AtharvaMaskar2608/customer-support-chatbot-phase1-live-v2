# CHO-242: rename-askfinx — tasks

## 1. Prompt identity (backend)

- [ ] 1.1 In `backend/app/agent/prompt.py`, change the identity lines "You are Choice Jini …" and "continue as Choice Jini" → "AskFinX" (SYSTEM_PROMPT)

## 2. Customer-facing display strings (frontend)

- [ ] 2.1 `frontend/index.html` `<title>` → "AskFinX"
- [ ] 2.2 `frontend/src/WhatsNewModal.tsx` — "What's new in Jini" → "What's new in AskFinX" (title + aria)
- [ ] 2.3 `frontend/src/chat/ChatShell.tsx` — composer aria-label "Ask Choice Jini" → "Ask AskFinX"
- [ ] 2.4 `frontend/src/App.tsx` — parked header title "Choice Jini" → "AskFinX" (kept consistent even though parked)
- [ ] 2.5 `frontend/src/widget/widget.ts` — launcher bubble aria + iframe title "Choice Jini support chat" → "AskFinX support chat"; the `[choice-jini]` log tag optional

## 3. Keep programmatic identifiers (do NOT change)

- [ ] 3.1 Leave `window.ChoiceJini` / `ChoiceJini.init` and its warning log as-is (public embed API)
- [ ] 3.2 Leave the `choiceJini.whatsNew.seenVersion` localStorage key as-is
- [ ] 3.3 Leave the Freshdesk `choice-jini` tag + `cf_*` custom-field values as-is; ticket subject `[Choice Jini]` unchanged unless the subject-rename decision flips (then coordinate with CHO-245)

## 4. Verification

- [ ] 4.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes; `cd backend && uv run pytest` green (prompt snapshot updated — hash change expected)
- [ ] 4.2 Grep confirms no stray customer-facing "Choice Jini"/"Jini" remains (excluding the intentionally-kept programmatic identifiers)
- [ ] 4.3 Screenshot the renamed surfaces (What's new modal, browser tab)

## 5. Ship & sync

- [ ] 5.1 `git-sync` with issue key CHO-242
- [ ] 5.2 `linear-connector` — summary comment + state on merge
