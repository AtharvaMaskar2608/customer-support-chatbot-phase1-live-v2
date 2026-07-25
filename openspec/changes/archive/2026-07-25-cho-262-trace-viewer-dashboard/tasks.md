# CHO-262: trace-viewer-dashboard — tasks

## 1. Backend read API + auth

- [x] 1.1 `config.py`: `traces_admin_token()` (TRACES_ADMIN_TOKEN via `_secret`)
- [x] 1.2 `traces_router.py`: token gate — unset ⇒ 404, bad `X-Traces-Token` ⇒ 401 (constant-time), never logged
- [x] 1.3 `GET /api/traces` — recent-first, filters (thread/model/error/tool/since/until), paginated, `{traces, total}`, no spans
- [x] 1.4 `GET /api/traces/{id}` — one row incl. parsed `spans`; 404 when missing
- [x] 1.5 `GET /api/threads` — turns rolled up per thread, recent-first, paginated
- [x] 1.6 `GET /api/threads/{thread_id}` — that thread's turns asc, each with spans
- [x] 1.7 `main.py`: register the router; pool=None ⇒ 503

## 2. Frontend — isolated third Vite entry

- [x] 2.1 `vite.config.ts`: add the `traces` HTML entry (app + traces; widget config untouched)
- [x] 2.2 `traces.html` + `src/traces/main.tsx` (own React root) + Tailwind (dark+light)
- [x] 2.3 Token gate: prompt, store in localStorage, send `X-Traces-Token`; clear 401/404 state
- [x] 2.4 Search/filter bar + threads list + traces list (paginated)
- [x] 2.5 Trace detail: nested span tree (agent → llm/tool/retriever) + per-span metadata + masked input/output
- [x] 2.6 Token-trend panel: hand-rolled CSS bars — input tokens + cache-read per turn
- [x] 2.7 `nginx.conf`: `/traces` location (keep `/api` proxying intact)

## 3. Verification

- [x] 3.1 `tests/test_traces_router.py`: 404 unset, 401 bad token, 200 + shape, filters, 503 no pool
- [x] 3.2 Full backend suite green (`uv run pytest`) — 479 passed, 2 skipped
- [x] 3.3 Frontend `tsc --noEmit` clean, `oxlint` clean, `npm run build` emits `dist/traces.html`

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-262 (user opens the PR)
- [ ] 4.2 `linear-connector` — In Progress at start, summary + In Review at PR, Done at merge
