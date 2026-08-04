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
docker build --build-arg VITE_APP_VERSION=frontendv1.0.3 \
  -t 829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:frontendv1.0.3 frontend/
```

The frontend build runs `tsc` + both Vite entries inside the image — a type
error fails the build, which is intended.

**The frontend tag is typed twice on purpose** — `--build-arg VITE_APP_VERSION`
must equal the `-t` tag. Vite bakes it into the bundle at build time (a static
nginx image has no runtime env), and it becomes `frontend_version` on every
trace. Get them out of step and traces name a build that isn't what's serving.
The backend equivalent is `BOT_VERSION` in `docker-compose.yml`, which must
likewise equal the backend image tag.

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
docker push 829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:frontendv1.0.3
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
# optional: LANGFUSE_* — the trace mirror, off unless set. See §8.
```

FinX credentials are NOT in the env — they arrive per-request from the widget
(userId / sessionId / accessToken headers). So do **not** copy a dev `.env` to
the server wholesale: `FINX_SSO_JWT` / `FINX_SESSION` / `FINX_TEST_CLIENT_ID`
are local testing values (the JWT expires in 8h and is useless there),
`DATABASE_URL` points at a local tunnel that does not resolve from the server,
and `TRACES_ADMIN_TOKEN` should be a *different* secret in prod — it unlocks a
dashboard showing real client codes and conversation text. Add the keys the
server needs to the server's own `.env` instead of replacing it.

```bash
aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin 829433345651.dkr.ecr.ap-south-1.amazonaws.com
docker compose pull
docker compose up -d
docker compose ps          # both services Up
```

**As deployed 2026-07-19** (compose unavailable on the server — apt mirror blocked
by the corporate proxy — and ECR pull blocked pending the IAM grant): images were
transferred as `docker save` tarballs and started with plain `docker run` from
`/home/harsh/jini/`, equivalent to the compose file:

```bash
docker load < jini-backend-v1.0.3.tar.gz
docker load < jini-frontend-v1.0.2.tar.gz
docker network create jini-net
docker run -d --name jini-backend  --network jini-net --network-alias backend \
  --env-file /home/harsh/jini/.env --restart unless-stopped -p 8000:8000 \
  -e BOT_VERSION=backendv1.0.3 \
  829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:backendv1.0.3
docker run -d --name jini-frontend --network jini-net --restart unless-stopped -p 8080:80 \
  829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:frontendv1.0.3
```

The pre-existing nginx vhost `/etc/nginx/conf.d/jini-chatbot.quanthm.com.conf`
(wildcard-cert TLS, `/`→8080, `/api/`→8000 with SSE buffering already off)
required no changes. The domain is reachable from the corporate network only
(firewall at the public IP). Switch back to the compose flow once apt/ECR
access exists: `docker rm -f jini-backend jini-frontend`, then §4 as written.

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
2. Bump the tag (`backendv1.0.3` → `backendv1.0.5` etc.) in the build command
   AND in `docker-compose.yml`; commit the compose bump. The tag appears in
   **three** places per release — miss one and the version stamped on traces
   stops matching the code that produced them:
   - backend: the `-t` tag **and** `BOT_VERSION` in `docker-compose.yml`
   - frontend: the `-t` tag **and** `--build-arg VITE_APP_VERSION`
3. Build → push → on the server: `docker compose pull && docker compose up -d`.

## 8. Langfuse trace mirror (optional — CHO-286/287/288)

Postgres `agent_traces` is the system of record. Langfuse is a **second sink**
for the same span tree, bought purely for its UI. The backend has shipped the
mirror code since `backendv1.0.12`, but it is **off unless configured** — with
no `LANGFUSE_*` env it logs one line and no-ops, and chat is unaffected. That
is deliberate: a Langfuse outage must never touch a conversation.

The stack is six containers (web, worker, Postgres, ClickHouse, Redis, MinIO)
on a box that otherwise runs two. It is a separate compose project in
`/home/harsh/langfuse/`; `jini-backend` and `jini-frontend` keep running from
`/home/harsh/jini/` untouched. Artifacts live in **`deploy/langfuse/`** —
a prod-trimmed compose file, an `.env.example`, and `gen-secrets.sh`. The
header of that compose file lists every deviation from upstream and why.

**Step 0 — two prerequisites the box may not meet.** Both are cheap to check
and both change the plan, so answer them before touching anything else.

```bash
docker compose version              # on 10.132.147.130
docker pull langfuse/langfuse:3
```

*No compose.* As of the 2026-07-19 deploy the server had **no compose plugin**
— the apt mirror is blocked by the corporate proxy, which is why §4 runs the
two Jini containers with plain `docker run`. Six interdependent containers with
healthcheck ordering is not something to hand-translate into `docker run`, so
install the plugin instead: it is a single static binary and needs no apt.

```bash
# from a machine with internet, then scp to the server:
curl -fsSLO https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64
scp docker-compose-linux-x86_64 harsh@10.132.147.130:/tmp/
# on the server:
mkdir -p ~/.docker/cli-plugins
install -m 755 /tmp/docker-compose-linux-x86_64 ~/.docker/cli-plugins/docker-compose
docker compose version
```

*No registry access.* ECR is IAM-blocked; Docker Hub may be too. If the pull
fails, every one of the six images joins the tarball path (`docker save | gzip`,
scp, `docker load`) — roughly 2–3 GB hand-carried on install and on every
upgrade. Weigh that recurring cost against the benefit before committing.

**Step 1 — stand up the stack.**

```bash
scp -r deploy/langfuse harsh@10.132.147.130:/home/harsh/langfuse
# then on the server, in /home/harsh/langfuse:
bash gen-secrets.sh > .env     # random values for every secret
vi .env                        # fill LANGFUSE_INIT_USER_EMAIL (the only blank)
docker compose up -d
docker compose ps              # six services, postgres/redis/clickhouse/minio healthy
```

`gen-secrets.sh` exists because upstream's compose ships working defaults
(`mysalt`, `miniosecret`) that are published in a public repo — a stack with a
missing `.env` would start happily with known credentials. Our compose declares
every secret `${VAR:?...}`, so it refuses to start instead.

First boot also creates the org, project, admin login **and** the `pk-lf`/`sk-lf`
pair from the `LANGFUSE_INIT_*` vars, so the keys exist before anyone opens the
UI. Later boots ignore them.

**Step 2 — point the backend at it.** Add to `/home/harsh/jini/.env` (the keys
are the two `LANGFUSE_INIT_PROJECT_*_KEY` values from step 1):

```
LANGFUSE_TRACING=1
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://langfuse-web:3000
```

**Container name, not `localhost:3000`** — inside `jini-backend`, localhost is
the backend. `langfuse-web` resolves because the compose file attaches that one
service to `jini-net`; the other five stay on Langfuse's private network.

**Step 3 — recreate the backend.** Nothing to rebuild: `.env` is read at
startup, and the image already carries the code.

```bash
docker rm -f jini-backend
docker run -d --name jini-backend --network jini-net --network-alias backend \
  --env-file /home/harsh/jini/.env --restart unless-stopped -p 8000:8000 \
  -e BOT_VERSION=backendv1.0.12 \
  829433345651.dkr.ecr.ap-south-1.amazonaws.com/customer-support-chatbot:backendv1.0.12
```

**Step 4 — verify.** One log line settles it:

```bash
docker logs jini-backend 2>&1 | grep -i "langfuse mirror"
# langfuse mirror enabled (http://langfuse-web:3000)   → live
# langfuse mirror disabled (LANGFUSE_TRACING off)      → flag not set
# langfuse mirror disabled: credentials or base URL missing
```

Then run one real conversation and confirm the trace lands in the UI.

**Reaching the UI.** The stack binds web to `127.0.0.1` only, so there is no
public route to it — by design. Since CHO-287 the traces carry **raw client
codes** alongside full conversation text, which is not something to put on the
open internet behind a login form. Tunnel instead:

```bash
ssh -L 3000:127.0.0.1:3000 harsh@10.132.147.130   # then http://localhost:3000
```

Self-service signup is disabled; the bootstrap user is the only account until
you invite others from inside the UI.

**Rollback** is `LANGFUSE_TRACING=0` in the Jini `.env` and a backend recreate.
Postgres tracing is untouched throughout, so nothing needs unwinding. The
Langfuse stack itself can be left running or `docker compose down`-ed
independently — `jini-net` is declared `external`, so bringing it down cannot
take the Jini network with it.

Per Langfuse's own docs this compose deployment has no HA, no scaling and no
backups. Accepted deliberately: losing it loses a UI, not data. If Langfuse
ever becomes where people actually look, that promotion is the moment to
revisit the deployment.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `403 Forbidden` on `docker push` | IAM user lacks ECR push rights — attach `AmazonEC2ContainerRegistryPowerUser` |
| Chat fine, but no traces in Langfuse | Mirror is fail-open by design — grep the startup line (§8 step 4). Most often `LANGFUSE_TRACING` unset in the server `.env` |
| `langfuse root failed error=ConnectError` in backend logs | `jini-backend` can't reach `langfuse-web` — check `LANGFUSE_BASE_URL` uses the container name and `docker network inspect jini-net` lists both |
| Langfuse compose exits instantly with `required variable ... is missing` | Working as intended — a secret is blank in `/home/harsh/langfuse/.env`. Never paper over it with upstream's defaults |
| Langfuse `postgres` won't start, port in use | Only if you re-added a host port mapping — the prod trim publishes none for it |
| Traces attributed to the wrong build | `BOT_VERSION` not bumped on the `docker run` (§1) |
| Chat text appears all at once | A proxy hop is buffering — `proxy_buffering off` on every nginx in the path |
| `AGENT_UNAVAILABLE` on chat | `ANTHROPIC_API_KEY` missing/invalid in the server `.env` |
| KB answers degrade / no memory | `DATABASE_URL` unreachable from the server (store logs dropped writes; chat keeps working by design) |
| `AUTH_EXPIRED` in the widget | The host page passed a stale SSO JWT / session — re-login on the host site |
