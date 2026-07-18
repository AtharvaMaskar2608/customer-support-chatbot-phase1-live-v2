# Tasks — Phase 1 Scaffold + Home Screen

## 1. Monorepo scaffold

- [x] 1.1 Create `backend/` FastAPI project (pyproject, app entrypoint, health route, run instructions)
- [x] 1.2 Create `frontend/` React + Vite + TypeScript project with Tailwind CSS configured (theme tokens from the mock: purple accent, greens, grays)
- [x] 1.3 Add root `.gitignore` (env files, node_modules, __pycache__, dist) and untracked `.env.example` documenting `FINX_SSO_JWT`, `FINX_SESSION`, `FINX_TEST_CLIENT_ID`
- [x] 1.4 Wire frontend dev proxy → backend so the SPA calls `/api/*` without CORS config

## 2. Session bootstrap (frontend)

- [x] 2.1 Parse handoff query params (`userId`, `sessionId`, `accessToken`, `isDarkTheme`, `platform`, `obStatus`, screen name) into an in-memory session context at boot
- [x] 2.2 Strip credential params from the address bar via `history.replaceState` after parsing
- [x] 2.3 Apply theme from `isDarkTheme` before first paint (no light-flash in dark mode)
- [x] 2.4 Render in degraded (non-personalized) state when params are missing

## 3. Profile greeting (backend)

- [x] 3.1 Implement `POST` proxy route calling upstream Get Profile with `authorization` (raw JWT), `from` (session token), and `{"InvCode": USER_ID}` per docs/api_doc/api_documentation.md
- [x] 3.2 Derive first name from `FirstHolderName` (first token, title-cased); return `{"firstName": ...}` only
- [x] 3.3 Map upstream 401 → typed `AUTH_EXPIRED` response; other failures → generic degraded response
- [x] 3.4 Enforce PII rules: no logging of request URLs with credentials or upstream bodies; log status + timing only
- [x] 3.5 Unit-test name derivation (multi-part name, single name, empty/missing) and 401 mapping

## 4. Home screen (frontend)

- [x] 4.1 Header: back button, logo, "Choice Jini", online dot + client code, "What's new" pill with red dot (static for now)
- [x] 4.2 Hero greeting wired to greeting endpoint: "Hey <FirstName> —" (accent color) with "Hey there" fallback
- [x] 4.3 Subtitle lines with green-highlighted "no email verification" phrase
- [x] 4.4 "POPULAR RIGHT NOW" section with the four quick-action chips (icons per mock)
- [x] 4.5 Divider + chat composer (rounded input, purple send button); chips submit their label through the composer; submitted queries no-op for now (chat lands in a later change)
- [x] 4.6 Compliance footer "Factual answers only — never investment advice"
- [x] 4.7 Dark theme pass over all sections

## 5. What's new (backend + frontend)

- [x] 5.1 Backend: `GET /api/whats-new` serving `{version, items[{emoji, tint, title, description}]}` from server-side content (initial content: Capital Gain report 📄 indigo, Live ticket status 🎫 green); no credentials required; unit test the shape
- [x] 5.2 Frontend: modal per mock — "✨ What's new in Jini" header with ✕, emoji tile rows, purple "Got it" button, "Content updated remotely — no app release needed" footer; opens from the header pill
- [x] 5.3 Frontend: red dot on the pill only when fetched `version` ≠ locally seen version; dismissal persists seen version (localStorage); fetch failure → no dot, no breakage
- [x] 5.4 Frontend: tint-matched item icons per mock — glyph rendered in the tile's tint colour (blue doc on indigo, green ticket on green), not native emoji colours; neutral fallback for unknown tints

## 6. Verification

- [x] 6.1 Run both halves together; load with mock handoff params (fresh SSO token) and verify personalized greeting end-to-end
- [x] 6.2 Verify degraded flows: no params, expired token (401)
- [x] 6.3 Visual check against the approved mocks (home + What's new modal) in light and dark, narrow (mobile webview) width

## 7. Corner widget embed (frontend)

- [x] 7.1 `widget.js` embed: separate framework-free Vite build entry exposing `ChoiceJini.init(params)`; renders the floating bottom-right bubble over host content
- [x] 7.2 Panel: bubble click toggles a ~380×640 rounded corner panel (full-screen overlay on narrow viewports) containing the chat page iframe (init params → query string, `platform=web`); iframe stays mounted across close/reopen
- [x] 7.3 Chat page: when `platform=web`, header back arrow posts `{type: "choice-jini:close"}` to parent; embed listens (origin-checked) and hides the panel
- [x] 7.4 Theme pass-through (`isDarkTheme` → iframe params) and bubble/panel chrome sane over light and dark host pages
- [x] 7.5 Demo host page simulating the FinX site: loads `widget.js`, forwards its own query-string session values into `ChoiceJini.init`
- [x] 7.6 Playwright verification: bubble renders, open → personalized chat, close/reopen without reload, back-arrow close, dark pass-through

## 8. Container + contrast polish (frontend)

- [x] 8.1 Chat page full-bleed: remove the page's own backdrop/card chrome so content reaches the viewport edges; panel/webview owns rounding + shadow (no more card-within-card)
- [x] 8.2 "What's new" pill dark-mode variant: light/elevated surface with clear contrast against the dark header (keep black pill in light mode)
- [x] 8.3 Re-verify: both Playwright suites + screenshots light/dark, standalone and inside the corner panel
