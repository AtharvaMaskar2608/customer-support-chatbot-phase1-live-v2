# CHO-219 · Docker Deploy

## Why

Phase 1 is feature-complete on main but only runs on dev machines. The team already has the deployment shape decided: two images in the existing ECR repo (`customer-support-chatbot`, ap-south-1), pulled and run on a server by `docker-compose.yml` behind `https://jini-chatbot.quanthm.com` — but the referenced image tags came from the earlier prototype repo, and this repo had no Dockerfiles. This change makes the repo self-deploying and documents every step.

## What Changes

- **`backend/Dockerfile`**: uv-based image running uvicorn on :8000; secrets arrive exclusively via env (compose `env_file`) — no `.env` in the image, `.dockerignore` excludes it defensively.
- **`frontend/Dockerfile` + `nginx.conf`**: node build stage (tsc + both Vite entries — a type error fails the build) → nginx serving the chat page and `widget.js`, with `/api` proxied same-origin to the backend service and **proxy buffering off** (the chat endpoint is SSE; any buffering hop destroys streaming).
- **`docker-compose.yml` joins the repo**: tags bumped to `backendv1.0.3` / `frontendv1.0.1` for this codebase; the old images' `API_PREFIX`/`API_BASE` env vars removed (this codebase reads neither — routes are natively under `/api` and the frontend calls relative paths).
- **`docs/deployment.md`**: the complete run-book — build, push, server `.env` requirements, run, verification, the production embed snippet (`widget.js` + `ChoiceJini.init`), the version-bump release loop, and troubleshooting (incl. the SSE-buffering trap and the current IAM push blocker).

## Capabilities

### New Capabilities

- `deployment`: the containerized serving contract — same-origin `/api`, SSE pass-through, env-only secrets, embed served from the chat origin.

## Impact

- New files only (two Dockerfiles, nginx.conf, two .dockerignore, compose, run-book); zero application-code changes.
- Verified locally: both images build; the composed stack served the chat page and widget.js, proxied `/api`, streamed SSE deltas progressively through nginx, and completed live brokerage + KB exchanges through the containers.
- Blocked at handover: ECR push returns 403 for the local IAM user (`atharva_maskar`) — an AWS admin must grant ECR push rights (e.g. `AmazonEC2ContainerRegistryPowerUser`); the push and server rollout commands are in the run-book, ready to execute.
