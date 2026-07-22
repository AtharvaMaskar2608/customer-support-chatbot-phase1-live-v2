# deployment Specification

## Purpose
TBD - created by archiving change cho-219-docker-deploy. Update Purpose after archive.
## Requirements
### Requirement: Containerized same-origin serving
Production SHALL run as two containers from the team ECR repo: the backend (uvicorn on :8000, all secrets via environment only — never baked into the image) and the frontend (nginx serving the built chat page and `widget.js`, proxying `/api` to the backend service on the same origin). The `/api` proxy SHALL disable response buffering so the chat SSE stream reaches the browser as it generates; every additional proxy hop in front (TLS terminator) MUST preserve this. The public origin serves both the chat page and the embed script, so host sites integrate with exactly the two-tag `ChoiceJini.init` snippet and no CORS configuration exists anywhere.

#### Scenario: SSE survives the proxy chain
- **WHEN** a user chats through the deployed widget
- **THEN** text deltas render progressively (not as one final block), through nginx and any fronting proxy

#### Scenario: Secrets stay out of images
- **WHEN** either image is inspected
- **THEN** it contains no `.env`, credentials, or DSNs — the server's env file supplies them at run time

#### Scenario: Release by tag bump
- **WHEN** a new version ships
- **THEN** the image tags are incremented in both the build commands and `docker-compose.yml`, and the server updates with `docker compose pull && docker compose up -d`

