# CHO-230: webview-file-bridge — tasks

## 1. Backend — token expiry in the download envelope

- [ ] 1.1 Add a shared helper (e.g. `download_delivery(file, token)` in `app/finx/delivery.py` or `app/report.py`) that returns `{delivery:"download", file, fileToken, ttlSeconds, expiresAt}` — `ttlSeconds = config.report_file_ttl_seconds()`, `expiresAt = datetime.now(timezone.utc) + timedelta(seconds=ttlSeconds)` (ISO-8601, seconds precision). NEVER derive the timestamp from the store's `monotonic()` `expires_at`.
- [ ] 1.2 Route all four download cores through it — P&L (`run_pnl`), ledger, capital gains (tax), contract-notes download — so the fields never drift per flow.
- [ ] 1.3 Confirm the fields are additive: the download endpoint still 404s for unknown-or-expired tokens (unchanged), and no upstream URL is exposed.
- [ ] 1.4 `uv run pytest` — extend the report tests to assert `ttlSeconds`/`expiresAt` are present and consistent with config; existing download/email tests still pass.

## 2. Frontend — the bridge module (`frontend/src/bridge.ts`)

- [ ] 2.1 `androidBridge()` — return `window.Android` only when `postMessage` is a function, else null (capability detection, not the `platform` string).
- [ ] 2.2 `correlationId(prefix)` — `crypto.randomUUID()` when available, else time+seq fallback; `sendFileToHost(fileToken, file, extras)` builds the `file.ready` `transport:"url"` envelope (absolute URL from `window.location.origin`, `auth:"none"`, `ttlSeconds`/`tokenExpiresAt` from `extras`) and posts it; returns false when no bridge.
- [ ] 2.3 `sendInlineFileToHost(filename, text, mimeType)` — `file.ready` `transport:"inline"` with UTF-8-safe base64 (`btoa(unescape(encodeURIComponent(text)))`), `source:"holdings-csv"`; returns false when no bridge.
- [ ] 2.4 `window.JiniBridge.onNativeEvent(json)` receiver — parse safely, dispatch `file.downloaded` / `file.expired` to a small subscriber registry keyed by `id`; ignore unknown/malformed without throwing.

## 3. Frontend — wire report downloads through the bridge

- [ ] 3.1 `ChatShell.tsx` `handleDownload` takes the full `FileInfo` (not just the name); try `sendFileToHost(fileToken, file, {source, ttlSeconds, expiresAt})`, fall back to `downloadReportFile` when it returns false.
- [ ] 3.2 Update the call site (`onDownload={() => onDownload(m.fileToken, m.file)}`) and the `onDownload` prop type to `(fileToken, file: FileInfo) => void`.
- [ ] 3.3 Thread `ttlSeconds`/`expiresAt` from the download envelope (api.ts / notes.ts result types) into the handler so the `url` payload carries honest expiry.
- [ ] 3.4 On a `file.downloaded` callback, flip the matching download card to its success/failed state via the `id` correlation.

## 4. Frontend — wire the holdings CSV (inline)

- [ ] 4.1 In `downloadHoldingsCsv`, build the CSV text, try `sendInlineFileToHost(holdingsCsvFilename(userCode), csv)` first; keep the existing `Blob` + `createObjectURL` download as the web fallback.

## 5. Docs — handoff contract

- [ ] 5.1 `docs/webview_bridge.md` is the Android-team contract (envelope, `url`/`inline` variants, expiry + 404 semantics, completion callback, security notes). Keep it in sync if payload fields change during implementation.

## 6. Verification

- [ ] 6.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes.
- [ ] 6.2 Web (no bridge): report + holdings downloads behave exactly as before (fallback path).
- [ ] 6.3 Bridge present (stub `window.Android.postMessage` in the demo): a report emits `file.ready` `transport:"url"` with an absolute URL + expiry; holdings emits `transport:"inline"` with base64; a stubbed `onNativeEvent('file.downloaded')` updates the card.
- [ ] 6.4 `uv run pytest` green (backend envelope fields).

## 7. Ship & sync

- [ ] 7.1 `git-sync` with issue key CHO-230.
- [ ] 7.2 New frontend image + backend image (bump tags), deploy via the SCP/save-load path, verify on prod.
- [ ] 7.3 `linear-connector` — summary comment + state on merge; share `docs/webview_bridge.md` with the Android team.
