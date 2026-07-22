# CHO-230: webview-file-bridge

## Why

The Choice Jini widget runs inside an Android WebView. Every generated file today
leaves the web UI as a browser `<a download>` click ([downloadReportFile](../../../frontend/src/flow/api.ts),
[holdingsCsv](../../../frontend/src/chat/datacards/holdingsCsv.ts)). Inside a WebView that gives the
native app **no `DownloadManager` entry, no system notification, and no completion
signal** — the file lands (or silently fails) with the app unaware. The native team
needs a defined, versioned way for the web layer to hand files to the host so the app
owns the actual save + notification, and can report completion back to the chat.

## What Changes

- **Add a WebView host bridge (web → native)**: a single versioned `file.ready` event
  emitted via `window.Android.postMessage(json)`, with a `transport` discriminator —
  `url` for server-tokened files (P&L, ledger, capital gains, contract notes, agent file
  artifacts) resolved to the token-only `/api/report/file/{token}` URL, and `inline` for
  the holdings CSV (built client-side; carried as UTF-8 base64 because `DownloadManager`
  cannot fetch a `blob:` URL).
- **Detect the bridge by capability, keep the web fallback**: emit the event only when
  `window.Android.postMessage` exists; on plain web the existing browser download
  (token anchor / Blob) is unchanged — zero regression.
- **Add a completion callback (native → web)**: the host calls
  `window.JiniBridge.onNativeEvent(json)` with a `file.downloaded` event echoing the
  originating correlation `id`; the web layer updates the matching download card and
  ignores unknown/malformed callbacks safely.
- **Backend: report token expiry in the download envelope** — add `ttlSeconds` and
  `expiresAt` (UTC ISO-8601), computed from the configured TTL at envelope-build time on
  the **wall clock** (`datetime.now(UTC) + ttl`), never from the store's `monotonic()`
  `expires_at`. Lets the bridge tell native honestly when the 5-minute URL stops working
  instead of hardcoding 300s.
- **Ship a handoff contract** for the Android team: [`docs/webview_bridge.md`](../../../docs/webview_bridge.md)
  (envelope, `url`/`inline` variants, expiry + 404-on-expiry semantics, completion callback,
  security notes).

The Android-native handlers (DownloadManager for `url`, base64-decode-and-write for
`inline`, the completion broadcast) are the app team's, specified by the doc — out of
this repo's code scope.

## Capabilities

### Added Capabilities

- `webview-host-bridge`: how the web UI delivers files and events to the native host —
  the `file.ready` event (`url` / `inline` transports), capability-based detection with a
  browser fallback, and the native→web completion callback.

### Modified Capabilities

- `finx-report-backend`: the report download envelope additionally reports the token's
  `ttlSeconds` and absolute `expiresAt` so a consumer knows when the token-only URL expires;
  the endpoint still returns 404 for unknown-or-expired tokens, indistinguishably.

## Impact

- **Frontend**: new `frontend/src/bridge.ts` (`sendFileToHost`, `sendInlineFileToHost`,
  capability detection, correlation id, the `onNativeEvent` receiver); wire the report
  download handler ([ChatShell.tsx](../../../frontend/src/chat/ChatShell.tsx) `handleDownload`, pass the
  full `FileInfo`) and the holdings export ([holdingsCsv.ts](../../../frontend/src/chat/datacards/holdingsCsv.ts))
  to try the bridge first, browser download as fallback.
- **Backend**: add `ttlSeconds` + `expiresAt` to the download envelope via a shared helper
  used by all four report cores ([report.py](../../../backend/app/report.py) and the `reports/` cores);
  computed from `config.report_file_ttl_seconds()` + wall-clock now. No contract break —
  purely additive fields.
- **Docs**: `docs/webview_bridge.md` — the Android team's contract.
- No change to what leaves the server (still token-only, no upstream URL); no new PII surface
  (holdings inline is client data already on screen).
- Ships as a new frontend image **and** backend image (envelope fields). Backend tests cover
  the new envelope fields; frontend gates are `tsc` + build (no unit runner).
- Linear: CHO-230 · branch `cho-230-webview-file-bridge`.

## Open follow-up (not this change)

`session.ended` and other host events reuse the same envelope but are separate changes.
Whether the in-memory token store should move to a shared store (so tokens survive a
restart / a second backend instance) is a scaling decision tracked separately — the 404
path already degrades safely.
