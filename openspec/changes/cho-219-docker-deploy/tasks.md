# CHO-219 · Docker Deploy — Tasks

- [x] 1.1 backend/Dockerfile (uv, uvicorn :8000, env-only secrets) + .dockerignore
- [x] 1.2 frontend/Dockerfile (node build → nginx) + nginx.conf (/api same-origin proxy, proxy_buffering off for SSE) + .dockerignore
- [x] 1.3 docker-compose.yml into the repo: tags backendv1.0.3 / frontendv1.0.2; dead API_PREFIX/API_BASE env vars removed
- [x] 1.4 Build both images; compose smoke on alt ports: chat page 200, widget.js 200, /api proxied (400 = creds wanted), SSE deltas stream progressively through nginx (KB answer), brokerage data card end-to-end through the containers, Postgres via host-gateway
- [x] 1.5 docs/deployment.md run-book: build → push → server .env → run → verify → embed snippet → release loop → troubleshooting
- [ ] 1.6 Push backendv1.0.3 + frontendv1.0.2 to ECR — BLOCKED: 403 for IAM user atharva_maskar; needs admin-granted ECR push rights (AmazonEC2ContainerRegistryPowerUser or repo-scoped). Images are built and ready locally.
- [x] 1.7 Server rollout DONE (2026-07-19, tarball route): images loaded on the prod box, containers up via docker run (compose blocked by corp apt proxy — documented in run-book §4), pre-existing TLS vhost verified; end-to-end HTTPS check passed from the server (chat page + widget.js 200, real KB exchange streamed through the vhost with progressive deltas, zero dropped store writes, prod DB confirmed = the dev-tunnel DB)
