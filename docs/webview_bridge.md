# Choice Jini — WebView ⇄ Native host bridge (file delivery)

**Status:** contract draft · CHO-230 (file delivery) + CHO-231 (session expiry) · v1 of the payload schema
**Audience:** the FinX Android team (native side) + the Jini web team (web side)

The Choice Jini chat widget runs inside an Android `WebView`. This document is the
contract for how the **web UI hands generated files to the native host** so the app
can save them with `DownloadManager` / MediaStore, show a system notification, and
report completion back to the chat.

Today (web-only) every download is a browser `<a download>` click. Inside a WebView
that gives the app no download entry, no notification, and no completion signal — so
for the native host we route through this bridge instead. On plain web (no bridge),
the existing browser download stays exactly as-is.

---

## 1. Transport

| Direction | Channel | Use for |
|---|---|---|
| Web → Native | `window.Android.postMessage(jsonString)` | Structured, versioned, actionable events (file delivery, session-end) |
| Web → Native | `window.Android.webBridgeLogEvent(jsonString)` | Analytics only — fire-and-forget, no reply |
| Native → Web | `webView.evaluateJavascript("window.JiniBridge.onNativeEvent(" + json + ")", null)` | Completion / result callbacks |

The web side detects the bridge by **capability** — `typeof window.Android?.postMessage === 'function'` — **not** by the `platform` handoff param. On web there is no `window.Android`, so the bridge path cannot misfire, and the native app does not have to pin down an exact `platform` string.

### Native setup (reference)

```java
webView.addJavascriptInterface(new JiniHostBridge(), "Android");

class JiniHostBridge {
    @JavascriptInterface public void postMessage(String json) { /* dispatch on type */ }
    @JavascriptInterface public void webBridgeLogEvent(String json) { /* analytics sink */ }
}
```

---

## 2. Common envelope

Every `postMessage` event shares one envelope:

```json
{
  "type": "file.ready",
  "v": 1,
  "id": "f_3nK9xQ2p",
  "ts": "2026-07-21T09:12:33Z",
  "payload": { }
}
```

| Field | Type | Meaning |
|---|---|---|
| `type` | string | Dot-namespaced event name (`file.ready`, `session.ended`, …). Dispatch on this. |
| `v` | int | Schema version. Branch on it; unknown major versions should be ignored gracefully. |
| `id` | string | Web-generated correlation id, unique per event. Echoed back in completion callbacks. |
| `ts` | string | ISO-8601 UTC emit time. |
| `payload` | object | Type-specific (below). |

---

## 3. `file.ready` — file delivery

One event type, a **`transport` discriminator** decides how the bytes arrive:

- `transport: "url"` — server holds the bytes behind a token-only URL. Used for **P&L, ledger, capital-gains (tax), contract notes, and any agent-emitted file artifact**.
- `transport: "inline"` — bytes are built in the browser and carried in the payload. Used for the **holdings CSV only** (it has no server token — see §3.3).

### 3.1 `transport: "url"` (reports, contract notes, agent artifacts)

```json
{
  "type": "file.ready",
  "v": 1,
  "id": "f_3nK9xQ2p",
  "ts": "2026-07-21T09:12:33Z",
  "payload": {
    "transport": "url",
    "url": "https://<jini-host>/api/report/file/AbC...opaqueToken",
    "filename": "PnL_Equity_2025-04-01_to_2026-07-21.pdf",
    "mimeType": "application/pdf",
    "format": "PDF",
    "sizeLabel": "128 KB",
    "passwordProtected": false,
    "auth": "none",
    "tokenExpiresAt": "2026-07-21T09:17:33Z",
    "ttlSeconds": 300,
    "source": "report"
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `transport` | `"url"` | Fetch `url` with `DownloadManager`. |
| `url` | string | **Absolute** download URL, token-only. The token is the *sole* credential — no headers. |
| `filename` | string | Server-set; matches the endpoint's `Content-Disposition: attachment`. |
| `mimeType` | string | `application/pdf` for reports. |
| `format` / `sizeLabel` | string | Display hints for the native UI (`"PDF"`, `"128 KB"`). |
| `passwordProtected` | bool | `false` today (tester-verified); kept so it can change without a schema bump. |
| `auth` | `"none"` | Explicit: no auth header required. |
| `tokenExpiresAt` | string | UTC ISO-8601 — the URL 404s after this. |
| `ttlSeconds` | int | Token lifetime in seconds (currently `300`). **Read this — never hardcode it.** |
| `source` | enum | `report` \| `contract-note` — lets native label / route. |

**Native handling:** enqueue a `DownloadManager.Request(Uri.parse(url))`, set the title to `filename`, mime to `mimeType`, destination to app-scoped Downloads. No headers.

### 3.2 Expiry & failure semantics (the part to get right)

- **Download immediately** on receipt. The URL is live for `ttlSeconds` (5 min) from generation. `DownloadManager` enqueues in milliseconds, so this is easy to honor. Do **not** stash the URL to download "later."
- **After expiry → HTTP 404** with body `{"error":"NOT_FOUND"}`. Unknown and expired tokens are **deliberately indistinguishable**. Treat 404 as "link expired": surface a "tap to regenerate" affordance, and optionally call back `file.expired` (see §5) so the web layer can offer a fresh generation.
- **A backend restart also invalidates tokens** (the store is in-memory, single-process). Same 404 path, same handling.
- **Never log, disk-cache, or share the full URL.** Within the TTL window, the token alone grants the file. This mirrors the backend's own no-log posture (it logs status + timing only — never the URL, body, or credentials).
- No range/resume guarantees — treat as a single GET. Files are small (tens–hundreds of KB).

### 3.3 `transport: "inline"` (holdings CSV only)

The holdings "overall report" CSV is built **in the browser** from the data already on screen — there is no server token to hand `DownloadManager`, and `DownloadManager` cannot fetch a `blob:`/`data:` URL. So the bytes ride in the payload:

```json
{
  "type": "file.ready",
  "v": 1,
  "id": "f_7bQ2mreT",
  "ts": "2026-07-21T09:20:01Z",
  "payload": {
    "transport": "inline",
    "filename": "X008593_Holding_Overall_Report_20260721142001.csv",
    "mimeType": "text/csv",
    "format": "CSV",
    "passwordProtected": false,
    "contentBase64": "<UTF-8 CSV, base64-encoded>",
    "source": "holdings-csv"
  }
}
```

**Native handling:** base64-decode `contentBase64` → write the bytes to app-scoped Downloads (MediaStore / `FileOutputStream`) under `filename`, then show a notification if desired. No network call.

This is cheap and safe: the holdings CSV is a small data table, and the rows are already client-side, so inlining adds **no new server round-trip and no new PII surface** — it is the same data the card already shows.

---

## 4. Which downloads use which transport

| Download | Backend token? | `transport` | `source` |
|---|---|---|---|
| P&L report | yes | `url` | `report` |
| Ledger report | yes | `url` | `report` |
| Capital-gains (tax) report | yes | `url` | `report` |
| Contract note (per note) | yes | `url` | `contract-note` |
| Agent-emitted file artifact | yes | `url` | `report` |
| Holdings overall CSV | **no** (client-built) | `inline` | `holdings-csv` |

Everything except holdings goes through the token URL; holdings is the one inline case.

---

## 5. Completion callback (native → web)

After the download finishes (or fails), the native host calls back so the chat can flip the download card from "downloading…" to "Saved to device" / "Download failed":

```js
window.JiniBridge.onNativeEvent(JSON.stringify({
  type: "file.downloaded",
  v: 1,
  id: "f_3nK9xQ2p",          // echoes the originating file.ready id
  ts: "2026-07-21T09:12:41Z",
  payload: { status: "success", reason: null }
}))
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Must echo the `file.ready` `id` so the web layer updates the right card. |
| `payload.status` | `"success"` \| `"failed"` | |
| `payload.reason` | string \| null | On failure: `"expired"` \| `"network"` \| `"storage"`. |

The web receiver matches on `id` and **ignores unknown or malformed callbacks without error**. Correlate `DownloadManager`'s `downloadId` to the `file.ready` `id` on the native side so the `ACTION_DOWNLOAD_COMPLETE` broadcast can be reported back.

An optional `file.expired` callback (same shape, `type: "file.expired"`) can be sent when a `url` download 404s, so the web layer can offer to regenerate.

---

## 6. `session.expired` — session lifecycle (CHO-231)

FinX session validity is only known **reactively**: a dead session surfaces as HTTP 401
(`AUTH_EXPIRED`) on the first authenticated call after expiry — the profile hit at boot, an
agent call, or a report/data call. When the web layer observes it, it emits `session.expired`
(**same envelope** as `file.ready`) so the native host can re-authenticate instead of the user
reopening the app by hand:

```json
{ "type": "session.expired", "v": 1, "id": "s_a1b2c3", "ts": "2026-07-21T09:30:00Z",
  "payload": { "trigger": "profile" } }
```

| Field | Type | Notes |
|---|---|---|
| `payload.trigger` | enum | Where expiry was first observed: `profile` \| `agent` \| `report` \| `data`. Diagnostic only. |

**Native handling:** re-mint the SSO JWT / session, then reload the WebView with fresh handoff
query params (the same params the web app reads and scrubs at boot). The web layer emits this
**at most once per expiry** (guarded against parallel or repeated 401s). On plain web (no
bridge) there is no app to re-auth, so the user simply sees "reopen Jini from FinX."

### `session.ended` (sibling — deliberate close, same envelope)

A separate concept for an intentional close (not expiry):

```json
{ "type": "session.ended", "v": 1, "id": "s_a1b2c3", "ts": "...",
  "payload": { "reason": "user-restart" | "closed" } }
```

---

## 7. Security notes (must hold)

- **Token-only URLs are unguessable and short-lived** (`secrets.token_urlsafe(24)`, 5-min TTL). Do not persist or log the full URL on the native side.
- **No credentials in the bridge.** The download URL needs none; the SSO/session tokens never leave via the bridge. (They arrive to the web app as one-time query params and are scrubbed from the URL at boot.)
- **`webBridgeLogEvent` is analytics only** — never route file bytes, URLs, or tokens through it.

---

## 8. Backend addition this depends on

The report download envelope **today** returns:

```json
{ "delivery": "download",
  "file": { "name": "...", "sizeLabel": "...", "format": "PDF", "passwordProtected": false },
  "fileToken": "AbC...opaque" }
```

It does **not** carry expiry. For the `url` variant to report `tokenExpiresAt` / `ttlSeconds` honestly, the backend adds them to that envelope, computed from the configured TTL at build time on the **wall clock** (`datetime.now(UTC) + ttlSeconds`) — the store's internal `expires_at` is a `monotonic()` value and must not be used for a timestamp. The web layer resolves `fileToken` → an absolute `url` from its own page origin. Small, contained change; no native change once the fields are present.
