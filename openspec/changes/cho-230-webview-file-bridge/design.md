# CHO-230 — design decisions

## D1 — one `file.ready` type with a `transport` discriminator (not two event types)

A single versioned `file.ready` event carries a `transport` field (`url` | `inline`).
The native side branches on `transport`; the envelope, versioning, correlation id, and
completion callback are shared. Two separate event types (`file.url` / `file.inline`)
would duplicate the envelope and double the version surface for what is one concept —
"a file is ready for the host."

## D2 — `url` for tokened files, `inline` (base64) for holdings CSV

All server-generated files already resolve to an opaque, session-scoped, short-TTL
token served at `/api/report/file/{token}` — hand the native side that absolute URL and
let `DownloadManager` fetch it. The **holdings CSV is the one exception**: it is built in
the browser from data already on screen (`holdingsCsv.ts`, `new Blob` + `createObjectURL`),
so there is no server token, and `DownloadManager` cannot fetch a `blob:`/`data:` URL.
For that one case the bytes ride in the payload as UTF-8 base64; native decodes and writes
them. The CSV is small and the data is already client-side, so this adds no server
round-trip and no new PII surface.

## D3 — detect the bridge by capability, not by the `platform` string

Gate on `typeof window.Android?.postMessage === 'function'`, not
`session.platform === 'android'`. Web has no `window.Android`, so the bridge path cannot
misfire there, and the native app is not forced to commit to an exact `platform` token.
The `platform` param stays available for belt-and-suspenders if the team wants it.

## D4 — absolute URL from the page origin; token is the sole credential

The web layer resolves `fileToken` → `${window.location.origin}/api/report/file/{token}`.
That origin is the public host the WebView loaded the app from, so the native
`DownloadManager` (outside the WebView) can reach it, and `/api/...` is same-origin with
the page. The endpoint is token-only (no session header), so no auth header is attached —
`auth: "none"` says so explicitly.

## D5 — backend reports expiry from the wall clock, not the store's monotonic value

`FileTokenStore` tracks `expires_at` using `time.monotonic()` (correct for internal
pruning, meaningless as a timestamp). The download envelope must instead compute
`ttlSeconds = config.report_file_ttl_seconds()` and
`expiresAt = datetime.now(UTC) + timedelta(seconds=ttlSeconds)` at build time. A shared
helper builds the `{delivery, file, fileToken, ttlSeconds, expiresAt}` envelope for all
four report cores so the fields can't drift per flow. Additive only — existing consumers
ignore unknown fields.

## D6 — completion is native → web via `window.JiniBridge.onNativeEvent`, correlated by `id`

The web layer exposes a small receiver `window.JiniBridge.onNativeEvent(json)`. The host
calls it with `file.downloaded` (or `file.expired`) echoing the `file.ready` `id`; the web
layer maps `id` → the download card and updates it. Unknown/malformed callbacks are
ignored without throwing. Native correlates `DownloadManager`'s `downloadId` to our `id`.

## D7 — `postMessage` for structured events, `webBridgeLogEvent` stays analytics-only

Actionable, versioned events (file delivery, session-end) go through the type-dispatched
`postMessage(json)`. `webBridgeLogEvent` remains a fire-and-forget analytics sink — no
file bytes, URLs, or tokens ever routed through it.

## D8 — web behavior is unchanged when no bridge is present

Every sender returns `false` when the bridge is absent, and the caller falls back to the
existing browser download. Plain-web users see no change; the bridge is purely additive.

## Expiry / failure contract (summary)

- `url` valid until `tokenExpiresAt` (~5 min). Native downloads immediately.
- Expired or unknown token → HTTP 404 `{"error":"NOT_FOUND"}`, indistinguishable by design.
  Native treats 404 as "expired," offers regenerate, may call back `file.expired`.
- Backend restart / second instance also invalidates tokens → same 404 path.
- Full URL is never logged or cached on the native side (token is the sole credential).
