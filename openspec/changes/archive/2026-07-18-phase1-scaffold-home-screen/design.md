# Design — Phase 1 Scaffold + Home Screen

## Context

Greenfield. FinX (web + Android/iOS webviews) opens our hosted chat page with identity/session in query params (`userId`, `sessionId`, `accessToken` 8h SSO JWT, `isDarkTheme`, `platform`, `obStatus`, later a screen name). `userId` decryption is handled by a Choice service — our system always operates on the decrypted USER_ID (e.g. `X008593`) and treats it as valid; invalid credentials simply fail upstream. The Get Profile upstream API is verified live (see `docs/api_doc/api_documentation.md`): raw JWT in `authorization`, session token in `from`, `{"InvCode": USER_ID}` body; response is PII-heavy (PAN, DOB, bank accounts). Stack decisions already made by the user: React + Vite frontend styled with Tailwind CSS, Python FastAPI backend, monorepo with `frontend/` and `backend/` side by side.

## Goals / Non-Goals

**Goals:**
- Runnable monorepo skeleton both halves can grow in.
- Home screen matching the approved mock, light + dark.
- Personalized greeting via a backend Get Profile proxy that leaks nothing but the first name.
- Graceful degradation when auth is expired/absent.

**Non-Goals:**
- Chat answering/LLM, RAG, the four tool APIs, "What's new" content, file delivery, screen-name-aware behavior.
- `userId` decryption (owned by Choice's service) and USER_ID validation (guaranteed by the host app; bad credentials just make upstream calls fail).
- `obStatus`-based gating — the param is accepted and stored but drives no behavior.

## Decisions

1. **Backend-for-frontend proxy for all upstream Choice calls.** The browser never calls `mf.choiceindia.com` directly. Rationale: (a) PII firewall — the extended-profile response contains PAN/bank/DOB and must never reach the client or logs; the proxy returns `{firstName}` only; (b) upstream CORS is not ours to control; (c) one place to encode Choice's header conventions. Alternative (direct browser call) rejected on all three counts.

2. **Stateless backend; session context travels per request.** Frontend parses query params once at boot and sends credentials to our backend as headers (`Authorization: <JWT>`, `X-Session-Id`, `X-User-Id`) on each call. No server-side session store in phase 1. Alternative (server session + cookie) deferred — adds state for no phase-1 benefit; revisit when chat history arrives.

3. **First-name derivation is server-side.** `FirstHolderName` ("PRITAM NITIN WAVHAL") → first whitespace token, title-cased → "Pritam". Done in the proxy so the full name never leaves the backend. Greeting shows first name; client code stays in the header (user decision).

4. **Param hygiene at boot.** After reading query params into memory, the frontend strips them from the address bar via `history.replaceState` to reduce token exposure in webview history/screenshots. Backend logs status codes only — never URLs with params, never upstream bodies.

5. **Styling with Tailwind CSS.** Utility-first styling per user preference; design tokens (purple accent, greens, grays from the mock) live in the Tailwind theme config. Dark mode uses Tailwind's `data-theme`/class strategy, with the attribute set once at boot from `isDarkTheme`. Alternative (hand-rolled CSS custom properties) workable but slower to iterate on the mock's dense component styling.

6. **USER_ID is trusted as received.** Decryption happens in a Choice service before it reaches us; the host app guarantees validity. We do no format validation beyond non-empty — if credentials are wrong, upstream APIs fail and we degrade per the 401 path.

7. **Quick-action chips prefill and submit into the composer** as plain text queries. They do not call tools directly — keeps the surface uniform for when chat handling lands.

8. **"What's new" is remote config, not baked-in UI.** Per the approved modal mock ("Content updated remotely — no app release needed"), the backend serves `GET /api/whats-new` (`version` + items with `emoji`/`tint`/`title`/`description`) from server-side content — phase 1 keeps it as a simple in-code/JSON structure in the backend, swappable for a CMS later. No credentials required: content is broadcast, non-PII. Seen-state lives client-side (localStorage keyed by `version`) and drives the pill's red dot. Alternative (hardcoding items in the frontend) rejected — it defeats the mock's stated purpose.

9. **Emoji as the icon language, tint-matched where known.** Iconography follows the mocks' emoji glyph language (header ✨, chip glyphs, What's new tiles). What's new item glyphs the frontend recognizes (📄 document, 🎫/🎟️ ticket) render as inline SVGs coloured to the tile's tint (mock-faithful: blue doc on indigo, green ticket on green) — native emoji carry fixed colours that clash with the tiles. Unknown emoji from remote content fall back to the raw emoji on a neutral tile.

10. **We own the corner launcher as a framework-free embed script.** The FinX website includes one `<script>` tag and calls `ChoiceJini.init({...})` with the session values it already holds; the script renders the bubble and mounts the chat page in an iframe panel with the params as query string and `platform=web`. Vanilla TS compiled as a separate Vite entry (IIFE, no React) — the host must not pay our framework cost, and the chat page stays a single artifact reused by web embed and app webviews. Alternative (FinX builds its own launcher) rejected by the user — we control the whole widget experience.

11. **Panel lifecycle: hide, don't unmount.** Closing the panel hides it (CSS) but keeps the iframe mounted so session and future chat state survive reopen; the chat page boots once per host page load. The in-chat back arrow posts `{type: "choice-jini:close"}` to the parent when `platform=web`; the embed script listens and hides the panel. Origin-checked messaging both ways.

## Risks / Trade-offs

- [8h token expiry mid-session] → every backend call maps upstream 401 to a typed `AUTH_EXPIRED` response; UI degrades to non-personalized greeting ("Hey there") and can show a "reopen from FinX" notice later. No refresh path exists on our side.
- [Tokens arrive in URL — host's design] → mitigated by decision 4 (strip + never log); residual risk in intermediary/webview logging is on the host's side.
- [`from` header not enforced upstream today] → we send it anyway; if Choice starts enforcing, nothing breaks.
- [Upstream response shape drift] → proxy validates only the fields it needs (`Status`, `Response.FirstHolderName`); anything else changing is invisible to us by design.
