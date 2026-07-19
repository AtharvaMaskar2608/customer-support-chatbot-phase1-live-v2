# Deploying Choice Jini

Two Docker images — the FastAPI backend and an nginx frontend (chat page +
`widget.js`, `/api` proxied same-origin) — pushed to ECR and run on the server
with `docker-compose.yml`. The public reverse proxy for
`https://jini-chatbot.quanthm.com` forwards to the frontend container (`:8080`);
everything else is internal.

```
FinX website ──(2 script tags)──▶ widget.js  ─iframe─▶  chat page ─/api/*─▶ nginx ─▶ backend ─▶ FinX APIs
                                     └──────────── one origin: jini-chatbot.quanthm.com ────────┘   Anthropic
                                                                                                    Postgres
                                                                                                    Freshdesk
```

## 0. Prerequisites

- Docker + AWS CLI on the build machine.
- AWS credentials that can push to ECR repo `customer-support-chatbot`
  (ap-south-1, account 829433345651). Minimum: `ecr:GetAuthorizationToken`,
  `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`,
  `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage` — the
  managed policy `AmazonEC2ContainerRegistryPowerUser` covers all of it.
  (As of 2026-07-19 the local `atharva_maskar` user can log in but gets
  **403 on push** — an AWS admin must attach the policy.)

## 1. Build (from the repo root, on main)

Version scheme: bump the component's tag by one and mirror the new tag in
`docker-compose.yml` (`backendvX.Y.Z` / `frontendvX.Y.Z` in the single
`customer-support-chatbot` repo).

```bash
docker build -t 829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:backendv1.0.3  backend/
docker build -t 829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:frontendv1.0.2 frontend/
```

The frontend build runs `tsc` + both Vite entries inside the image — a type
error fails the build, which is intended.

## 2. Smoke-test locally (optional but recommended)

```bash
docker compose -p jini-smoke up -d       # uses the tags in docker-compose.yml
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/            # 200 chat page
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/widget.js   # 200 embed script
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/greeting # 400 = proxy OK (missing creds is correct)
docker compose -p jini-smoke down
```

Note: with the dev database behind the SSH tunnel on `localhost:5433`, the
backend container cannot reach `localhost` — the conversation store degrades
gracefully (chat still works). For a full local test, point `DATABASE_URL` at
`host.docker.internal:5433` and add `extra_hosts: ["host.docker.internal:host-gateway"]`.
On the real server, use a DSN reachable from the server itself.

## 3. Push to ECR

```bash
aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin 829433345651.dkr.ecr.ap-south-1.amazonaws.com
docker push 829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:backendv1.0.3
docker push 829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:frontendv1.0.2
```

## 4. Run on the server

Copy `docker-compose.yml` to the server with a production `.env` next to it:

```
DATABASE_URL=...          # Postgres reachable FROM THE SERVER (conversation store + KB)
ANTHROPIC_API_KEY=...     # agent loop
OPENAI_API_KEY=...        # KB query embeddings
FRESHDESK_DOMAIN=...      # or FRESHDESK_API_ROOT
FRESHDESK_API_KEY=...     # ticket escalation
# optional: AGENT_MODEL / AGENT_THINKING / cap overrides / FRESHDESK_GROUP_ID
```

FinX credentials are NOT in the env — they arrive per-request from the widget
(userId / sessionId / accessToken headers).

```bash
aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin 829433345651.dkr.ecr.ap-south-1.amazonaws.com
docker compose pull
docker compose up -d
docker compose ps          # both services Up
```

Point the TLS reverse proxy for `jini-chatbot.quanthm.com` at `:8080`. If that
proxy is nginx, disable buffering for `/api/` there too (`proxy_buffering off;`)
— the chat endpoint is an SSE stream and any buffering hop kills the typing
effect. `:8000` is exposed only for direct debugging and can be firewalled.

## 5. Verify the deployment

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://jini-chatbot.quanthm.com/            # 200
curl -s -o /dev/null -w "%{http_code}\n" https://jini-chatbot.quanthm.com/widget.js   # 200
curl -s -o /dev/null -w "%{http_code}\n" https://jini-chatbot.quanthm.com/api/greeting # 400 (= alive, wants creds)
```

Then open a page with the embed snippet below and run a real conversation
(the SSE stream through every proxy hop is the thing worth eyeballing).

## 6. The embed — what the FinX website adds

This is the deliverable host sites integrate. Two tags, nothing else:

```html
<script src="https://jini-chatbot.quanthm.com/widget.js"></script>
<script>
  ChoiceJini.init({
    chatUrl: 'https://jini-chatbot.quanthm.com/',
    userId:      '<client code>',        // injected by the host site's auth
    sessionId:   '<FinX session id>',
    accessToken: '<SSO JWT>',
    isDarkTheme: false,
    // optional: obStatus, screenName
  })
</script>
```

`widget.js` renders the corner bubble + panel in a shadow root (host CSS cannot
leak in) and mounts the chat page in an iframe with those values as query
params. The panel survives open/close within a page visit; the chat's back
arrow posts an origin-checked close message to the host page.

## 7. Releasing a new version

1. Merge to main.
2. Bump the tag (`backendv1.0.3` → `backendv1.0.4` etc.) in the build command
   AND in `docker-compose.yml`; commit the compose bump.
3. Build → push → on the server: `docker compose pull && docker compose up -d`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `403 Forbidden` on `docker push` | IAM user lacks ECR push rights — attach `AmazonEC2ContainerRegistryPowerUser` |
| Chat text appears all at once | A proxy hop is buffering — `proxy_buffering off` on every nginx in the path |
| `AGENT_UNAVAILABLE` on chat | `ANTHROPIC_API_KEY` missing/invalid in the server `.env` |
| KB answers degrade / no memory | `DATABASE_URL` unreachable from the server (store logs dropped writes; chat keeps working by design) |
| `AUTH_EXPIRED` in the widget | The host page passed a stale SSO JWT / session — re-login on the host site |
