# Choice Jini backend

FastAPI service for the Choice Jini support chatbot (phase 1). Exposes a
health check and the profile-greeting proxy; the browser never talks to
`mf.choiceindia.com` directly.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (recommended) or plain `venv` + `pip`

## Run

From the repo root:

```bash
cd backend
uv sync                                    # installs runtime + dev deps into .venv
uv run uvicorn app.main:app --port 8000
```

Without `uv`:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install fastapi "uvicorn[standard]" httpx pytest respx
uvicorn app.main:app --port 8000
```

Smoke test: `curl http://127.0.0.1:8000/api/health` → `{"status":"ok"}`

## Tests

```bash
cd backend
uv run pytest
```

Tests mock the upstream API with `respx` — no live network calls.

## Endpoints

| Route | Description |
|---|---|
| `GET /api/health` | Liveness check, returns `{"status": "ok"}` |
| `GET /api/greeting` | Proxies upstream Get Profile; returns `{"firstName": "Pritam"}` or `{"firstName": null}` (degraded). Requires headers `Authorization` (raw SSO JWT, no `Bearer`), `X-Session-Id`, `X-User-Id`. Errors: 400 `MISSING_CREDENTIALS`, 401 `AUTH_EXPIRED`, 502 `UPSTREAM_ERROR`. |
| `GET /api/whats-new` | "What's new" announcements: `{"version": "...", "items": [{"emoji", "tint", "title", "description"}, ...]}`. No credentials required. |

## Editing "What's new" content

Content is remote config: edit `backend/content/whats_new.json` and bump
`version` (date-based, e.g. `2026-07-18.1` → `2026-07-18.2`) whenever items
change — the version drives the frontend's unseen-dot indicator. The file is
read per request, so edits go live without a restart and without any
frontend/app release.

## Configuration (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `UPSTREAM_PROFILE_URL` | `https://mf.choiceindia.com/api/v2/investor/profile/extended` | Upstream Get Profile endpoint; point at a mock for local testing |
| `UPSTREAM_TIMEOUT_SECONDS` | `10` | Timeout for upstream calls |

## PII rules

The upstream profile response contains PAN, DOB, address, and bank details.
This service never stores, logs, or forwards any of it — only the derived
first name is returned, and logs carry at most the upstream status code and
request timing. See `openspec/changes/phase1-scaffold-home-screen/specs/profile-greeting/spec.md`.
