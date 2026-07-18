# Phase 1 Scaffold + Home Screen

## Why

The Choice Jini support chatbot currently has documentation only — no code. Phase 1 delivers the embeddable chat page that FinX (web + app webviews) opens for logged-in users. This change lays the monorepo foundation (frontend + backend built side by side) and ships the first visible surface: the approved home screen with a personalized greeting backed by the verified Get Profile API.

## What Changes

- New monorepo structure: `frontend/` (React + Vite chat page) and `backend/` (Python FastAPI).
- Session bootstrap: the page ingests the FinX handoff query params (`userId`, `sessionId`, `accessToken`, `isDarkTheme`, `platform`, `obStatus`, screen name) into an internal session context.
- Backend proxy for Get Profile (`POST https://mf.choiceindia.com/api/v2/investor/profile/extended`) returning only the derived first name — the PII-heavy upstream response is never stored, logged, or forwarded to the client.
- Home screen UI per approved mock: header (back, logo, online status + client code, "What's new" pill), hero greeting "Hey \<FirstName\> — what do you need?", subtitle lines, four quick-action chips, divider, chat composer, compliance footer.
- Light + dark theme, host-controlled via `isDarkTheme`.
- "What's new in Jini" modal: remotely-served announcement content (backend endpoint, no app release needed to update), emoji-tile items, "Got it" dismissal with seen-state driving the header pill's red dot.
- Corner widget embed for the FinX website: a standalone `widget.js` the host includes, rendering a floating bottom-right bubble that toggles the chat page in an iframe panel (mobile apps keep opening the page directly in a webview).

Out of scope (later changes): actual chat/LLM answering, the four tool APIs (P&L, ledger, tickets, brokerage charges), file delivery, screen-name-aware behavior.

## Capabilities

### New Capabilities

- `session-bootstrap`: accept the FinX host handoff (query params) and establish the internal session context (USER_ID, session_id, SSO token, platform, page, theme, onboarding status); handle malformed/missing params.
- `profile-greeting`: backend endpoint that calls upstream Get Profile with the session credentials, derives the first name from `FirstHolderName`, enforces PII minimization, and degrades gracefully on upstream 401/failure.
- `home-screen`: the widget home screen UI — layout, quick-action chips that fire predefined queries into the composer, theming, and compliance footer.
- `whats-new`: the "What's new in Jini" announcements modal — remote content endpoint, emoji-tile item list, dismissal + unseen indicator.
- `widget-launcher`: the embeddable corner widget for the host website — launcher bubble, iframe panel, in-chat close wiring, theme pass-through, demo host page.

### Modified Capabilities

(none — greenfield)

## Impact

- New code: `frontend/` (React + Vite SPA), `backend/` (FastAPI service).
- External dependency: Choice SSO-authenticated Get Profile API (verified live 2026-07-18; contract in `docs/api_doc/api_documentation.md`).
- Secrets handling: mock credentials in untracked `.env`; SSO tokens expire every 8 hours.
- No existing systems modified; FinX integration is consume-only (they open our URL).
