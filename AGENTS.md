# AGENTS.md

Project overview, workflow, and standard run/build/test commands live in `CLAUDE.md`, `backend/README.md`, and `frontend/README.md`. Prefer those; the notes below only cover non-obvious cloud-environment caveats.

## Cursor Cloud specific instructions

Two services make up the product (see `CLAUDE.md` "Running locally" for the canonical commands):

- Backend (FastAPI): `cd backend && uv run uvicorn app.main:app --port 8000` — tests `uv run pytest`, no separate lint config.
- Frontend (React + Vite): `cd frontend && npm run dev` (:5173, proxies `/api` → :8000) — lint `npm run lint` (oxlint), build `npm run build`.

Non-obvious caveats:

- `uv` is not preinstalled; the startup update script installs it to `~/.local/bin` (already on PATH for login shells). If `uv` isn't found in a fresh shell, run `export PATH="$HOME/.local/bin:$PATH"`.
- The Vite dev server binds IPv6 only (`::1:5173`). Reach it via `http://localhost:5173` or `http://[::1]:5173`; plain `http://127.0.0.1:5173` will not connect. The backend listens on IPv4 `127.0.0.1:8000` normally.
- The backend boots and serves fully without Postgres — it degrades gracefully. `DATABASE_URL` (KB retrieval, conversation persistence, agent tracing) is optional; without it KB endpoints return 503 and chat is memory-only.
- The core agentic chat (`POST /api/chat`) requires `ANTHROPIC_API_KEY` **and** live FinX SSO credentials. Secrets are read from an untracked repo-root `.env` (template: `.env.example`). Without `ANTHROPIC_API_KEY` the stream emits `AGENT_UNAVAILABLE`; without valid FinX SSO the greeting degrades to `firstName: null` and data/report tools fail. `GET /api/health` and `GET /api/whats-new` work with no secrets.
- To exercise the chat UI locally, open `http://localhost:5173/?userId=<code>&sessionId=<sid>&accessToken=<jwt>&isDarkTheme=false` (handoff params are read once then stripped from the URL). The widget demo host page is `http://localhost:5173/demo/index.html?...`.
