# Choice Jini — customer-support chatbot (Phase 1 Live V2)

Embeddable support chatbot for FinX (Choice India). Monorepo: `frontend/` (React + Vite + Tailwind chat page + `widget.js` corner embed), `backend/` (FastAPI proxy to Choice APIs). Spec-driven via OpenSpec (`openspec/`); upstream API contracts in `docs/api_doc/api_documentation.md` (document only the fields we consume).

## Linear ↔ repo identifier sync (mandatory workflow)

Linear project: **Customer Support Chatbot Phase 1 Live V2** · team **Choicetechlab (CHO)**.

One identifier per unit of work, minted in Linear FIRST, then reused everywhere:

| Artifact | Name |
|---|---|
| Linear issue | `CHO-<num>`, title = kebab task name |
| OpenSpec change | `cho-<num>-<kebab-task>` |
| Branch | `cho-<num>-<kebab-task>` |
| Commit subject | `CHO-<num>: <imperative summary>` |
| PR title / body | `CHO-<num>: <title>` / include `Fixes CHO-<num>` |

Lifecycle: mint issue (Todo) → propose change → In Progress at implementation → In Review at PR → summary comment + Done at merge. Never invent issue numbers; never reuse one across changes.

## Project agents (.claude/agents/)

- **linear-connector** — mints/updates the CHO issue, syncs state, and posts the push/merge summary comment (precise, plain-language; format modeled on CHO-206's comment). Use at change start and after every push/merge.
- **git-sync** — branch/stage/commit/push/PR with the naming convention and secret checks. Use when verified work is ready to ship. It refuses to run without an issue key.

Typical shipping sequence after verification: `git-sync` (ship) → `linear-connector` (summarize + state). Run them with the Agent tool; give git-sync the issue key and give linear-connector the git digest from git-sync's report.

## Ground rules

- **Secrets**: real tokens/credentials live only in untracked `.env` (`.env.example` is the committed template). SSO JWTs expire 8h after mint — live-API testing needs a fresh token from the user. Never commit, log, or paste tokens into Linear/PRs.
- **PII**: upstream Choice responses carry PAN/DOB/bank data. Backend proxies must forward only the specific fields specced for consumption; never log upstream bodies or credentialed URLs (status + timing only).
- **Auth routing** (from `docs/finx_android_api_reference.html`): Get Profile + CML authenticate with the raw SSO JWT in `authorization`; the report endpoints (P&L, Ledger, Tax) use the **SessionId** as `authorization`. Business failures return HTTP 200 with `Status: "Fail"` — branch on the field, never string-match `Reason`.
- **Compliance**: factual answers only — the bot must never produce investment advice; keep the footer intact.

## Running locally

- Backend: `cd backend && uv run uvicorn app.main:app --port 8000` (tests: `uv run pytest`)
- Frontend: `cd frontend && npm run dev` → :5173 (proxies `/api` → :8000); build: `npm run build` (app + widget entries)
- Widget demo: `http://localhost:5173/demo/index.html?userId=...&sessionId=...&accessToken=...&isDarkTheme=false` (values from `.env`)

## Deploying

Full runbook: **`docs/deployment.md`**. Two images (`backend` / `frontend`) tagged `…vX.Y.Z`, tracked in `docker-compose.yml`. Bump only the component that changed (frontend-only change → new `frontendvX.Y.Z`, backend stays).

ECR push is IAM-blocked, so prod runs via the **tarball path**, not `docker compose pull`:
1. Build: `docker build -t 829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:frontendvX.Y.Z frontend/` and bump the tag in `docker-compose.yml`.
2. Package: `docker save <image> | gzip > jini-frontend-vX.Y.Z.tar.gz` (gitignored).
3. **Ship (user-only — the prod box takes a password, not our SSH key):** `scp` the tarball to `harsh@10.132.147.130:/home/harsh/jini/`, then on the server `docker load < …tar.gz` → `docker rm -f jini-frontend` → `docker run -d --name jini-frontend --network jini-net --restart unless-stopped -p 8080:80 <image>`. Backend container is left as-is.
4. Verify: `curl https://jini-chatbot.quanthm.com/` (200), `/widget.js` (200), `/api/greeting` (400 = alive).
