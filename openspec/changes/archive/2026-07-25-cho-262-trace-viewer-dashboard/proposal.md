# CHO-262: trace-viewer-dashboard

## Why

CHO-261 persists every `/api/chat` turn as an execution graph in the
`agent_traces` Postgres table, but the only way to read it today is raw SQL —
the CHO-261 proposal explicitly deferred a read UI to a follow-up. Operators
need to actually **see** the data: find a conversation, inspect one turn's
agent → llm → tool → retriever span tree, watch a thread's per-turn input-token
growth (the context-rot gauge, incl. the prompt-cache split), and spot errored
turns. This change adds that **admin-gated read dashboard** — backend endpoints
plus an isolated web page — over the existing table. It reads only; it adds no
new stored data and does not touch the chat path.

## What Changes

- **New read-only trace API** (`app/traces_router.py`, an `APIRouter` registered
  in `main.py`) over `app.state.pg_pool`: list traces (recent-first, filterable
  by thread/model/error/tool/date, paginated, spans omitted to stay light), one
  trace with its parsed span tree, threads rolled up from their turns, and one
  thread's turns in chronological order with spans. No pool ⇒ 503.
- **Admin auth, separate from the FinX per-user session auth.** A single shared
  token `TRACES_ADMIN_TOKEN` (via the existing `config._secret` helper). Unset ⇒
  every endpoint returns **404** (the dashboard is disabled and nothing is
  exposed by default). Set ⇒ the `X-Traces-Token` header must match, else
  **401**. The token and query text are never logged.
- **Isolated frontend entry.** A third Vite entry (`traces.html` +
  `src/traces/`), separate from the chat app and the corner widget: a token
  gate (stored in localStorage, sent as `X-Traces-Token`), a search/filter bar,
  threads + traces lists, a trace detail view rendering the nested span tree
  with per-span metadata, and a hand-rolled CSS token-trend gauge for a thread.
  No chart/router dependency is added. `npm run build` emits `dist/traces.html`.
- **Serving.** An nginx `location = /traces` maps the bare path to the built
  `traces.html`; `/api` proxying is untouched.

## Capabilities

### Added Capabilities

- `observability-dashboard`: an admin-token-gated, read-only dashboard (API +
  isolated web page) over the CHO-261 `agent_traces` store — search/find/view
  traces and threads, inspect the nested execution graph per turn, and see a
  thread's per-turn input-token trend. Disabled by default (404) until the admin
  token is configured; exposes only already-masked, already-hashed data.

## Impact

- New: `backend/app/traces_router.py`, `backend/tests/test_traces_router.py`,
  `frontend/traces.html`, `frontend/src/traces/*`.
- Edited: `backend/app/config.py` (`traces_admin_token()`), `backend/app/main.py`
  (register the router), `frontend/vite.config.ts` (add the `traces` HTML entry),
  `frontend/nginx.conf` (`/traces` location).
- No schema change (reads the existing `agent_traces` table); no chat-path
  change; no new runtime dependency.
- Config: `TRACES_ADMIN_TOKEN` (unset ⇒ dashboard disabled).
- Linear: CHO-262 · branch `cho-262-trace-viewer-dashboard`. Follows CHO-261.
