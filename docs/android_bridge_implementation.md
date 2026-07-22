# Implement the Choice Jini WebView bridge (Android)

**For the FinX Android team.** Paste this whole document into Claude Code (or your AI coding assistant) inside your Android app project. It is a complete, self-contained spec — you do not need any other file. Your job is to implement the **native side** of the Choice Jini WebView bridge: receive events from the web widget, handle downloads and session-expiry, and report completion back.

> The **web side is already shipped and live in production** (v1.0.7 at `jini-chatbot.quanthm.com`). It emits the events below and exposes `window.JiniBridge.onNativeEvent(...)` for your callbacks. Nothing on the web needs changing — implement the native handlers to match this contract.

---

## 0. What you're building (checklist)

- [ ] A `@JavascriptInterface` object exposed to the WebView as **`window.Android`** with two methods: `postMessage(String)` and `webBridgeLogEvent(String)`.
- [ ] A dispatcher that parses the incoming JSON and switches on `type`.
- [ ] **`file.ready` / `transport: "url"`** → download via `DownloadManager` (reports, contract notes).
- [ ] **`file.ready` / `transport: "inline"`** → base64-decode the bytes and save the file yourself (the holdings CSV; `DownloadManager` can't fetch it).
- [ ] **`session.expired`** → re-mint the FinX session and reload the WebView with fresh handoff params.
- [ ] **Completion callback** → after a download finishes/fails, call `window.JiniBridge.onNativeEvent(...)` so the chat updates its download card.

### What to locate in this app first
Have your AI find these in the existing code before wiring anything:
1. **The `WebView` instance** that loads the Choice Jini chat page.
2. **The URL + handoff params** it loads with (`userId`, `sessionId`, `accessToken`, `isDarkTheme`) — the widget reads these from the query string.
3. **The code that mints the SSO JWT / session** at launch — you'll re-run it on `session.expired`.

---

## 1. Transport (how web and native talk)

| Direction | Channel | Use |
|---|---|---|
| Web → Native | `window.Android.postMessage(jsonString)` | Structured events (file delivery, session-expiry) |
| Web → Native | `window.Android.webBridgeLogEvent(jsonString)` | Analytics only — fire-and-forget, no reply |
| Native → Web | `webView.evaluateJavascript("window.JiniBridge.onNativeEvent(<jsonString>)", null)` | Completion callbacks |

**Critical threading note:** `@JavascriptInterface` methods are invoked on a **background binder thread**, not the UI thread. Any WebView call (`evaluateJavascript`, `loadUrl`) or UI work must be posted to the main thread (`webView.post { … }` / `runOnUiThread`).

---

## 2. Event envelope (every `postMessage`)

```json
{ "type": "file.ready", "v": 1, "id": "f_3nK9xQ2p", "ts": "2026-07-22T09:12:33Z", "payload": { } }
```

| Field | Meaning |
|---|---|
| `type` | `file.ready` \| `session.expired` (dispatch on this) |
| `v` | schema version (currently `1`) |
| `id` | correlation id — **echo it back** in completion callbacks |
| `ts` | ISO-8601 UTC emit time |
| `payload` | type-specific (below) |

Unknown `type` or malformed JSON → ignore without crashing.

---

## 3. `file.ready` — a file is ready for the user

A `transport` field decides how the bytes arrive.

### 3a. `transport: "url"` (P&L, ledger, tax, contract notes, agent files)
```json
{ "type": "file.ready", "v": 1, "id": "f_3nK9xQ2p", "ts": "...", "payload": {
    "transport": "url",
    "url": "https://jini-chatbot.quanthm.com/api/report/file/AbC...opaqueToken",
    "filename": "PnL_Equity_2025-04-01_to_2026-07-21.pdf",
    "mimeType": "application/pdf",
    "format": "PDF",
    "sizeLabel": "128 KB",
    "passwordProtected": false,
    "auth": "none",
    "tokenExpiresAt": "2026-07-22T09:17:33Z",
    "ttlSeconds": 300,
    "source": "report"
} }
```
- The `url` is **token-only** — no auth header needed (`auth: "none"`). Fetch it with `DownloadManager`.
- **Start the download immediately.** The token is valid for `ttlSeconds` (~5 min); after `tokenExpiresAt` the URL returns **HTTP 404** (unknown and expired are indistinguishable by design). Treat 404 as "link expired".
- **Never log or persist the full URL** — the token alone grants the file for those 5 minutes.

### 3b. `transport: "inline"` (holdings CSV only)
```json
{ "type": "file.ready", "v": 1, "id": "f_7bQ2mreT", "ts": "...", "payload": {
    "transport": "inline",
    "filename": "X008593_Holding_Overall_Report_20260722.csv",
    "mimeType": "text/csv",
    "format": "CSV",
    "passwordProtected": false,
    "contentBase64": "<UTF-8 CSV, base64>",
    "source": "holdings-csv"
} }
```
- There is **no URL** — the CSV is built in the browser. Base64-decode `contentBase64` and write the file yourself (MediaStore / app Downloads). `DownloadManager` cannot be used here.

---

## 4. `session.expired` — the FinX session died mid-chat
```json
{ "type": "session.expired", "v": 1, "id": "s_a1b2", "ts": "...", "payload": { "trigger": "profile" } }
```
- Fired at most once per expiry. `trigger` is `profile` \| `agent` \| `report` \| `data` (diagnostic only).
- **Your handler:** re-mint the SSO JWT / session (the same way you do at launch), then **reload the WebView** with fresh handoff query params. The widget re-bootstraps from the new params and drops the user back into a working session. No web change needed.

---

## 5. Completion callback (native → web), optional but recommended

After a `file.ready` download finishes or fails, tell the web so the chat flips the download card from "downloading…" to "Saved" / "Failed":
```json
{ "type": "file.downloaded", "v": 1, "id": "f_3nK9xQ2p", "ts": "...",
  "payload": { "status": "success", "reason": null } }
```
- `id` **must** echo the originating `file.ready` `id`.
- `status`: `"success"` | `"failed"`; `reason` on failure: `"expired"` | `"network"` | `"storage"`.
- Deliver it via `webView.evaluateJavascript("window.JiniBridge.onNativeEvent(<jsonString>)", null)` on the main thread. The web receiver is parse-safe and ignores unknown ids.

---

## 6. Reference implementation (Kotlin — adapt to this app's structure)

```kotlin
class JiniHostBridge(
    private val activity: Activity,
    private val webView: WebView,
    /** Re-mint the FinX session, then reload the WebView with fresh handoff params. */
    private val onSessionExpired: (trigger: String) -> Unit,
) {
    private val pendingDownloads = ConcurrentHashMap<Long, String>() // downloadId -> file.ready id

    @JavascriptInterface
    fun postMessage(json: String) {
        // Runs on a binder thread — hop to main for any WebView/UI work.
        activity.runOnUiThread { runCatching { dispatch(json) } }
    }

    @JavascriptInterface
    fun webBridgeLogEvent(json: String) {
        // analytics sink — fire-and-forget; do NOT route files/URLs through this.
    }

    private fun dispatch(json: String) {
        val obj = JSONObject(json)
        when (obj.optString("type")) {
            "file.ready" -> handleFileReady(obj.getJSONObject("payload"), obj.optString("id"))
            "session.expired" -> onSessionExpired(obj.getJSONObject("payload").optString("trigger"))
            else -> { /* unknown type — ignore */ }
        }
    }

    private fun handleFileReady(p: JSONObject, id: String) = when (p.optString("transport")) {
        "url" -> downloadUrl(p, id)
        "inline" -> writeInline(p, id)
        else -> { /* unknown transport — ignore */ }
    }

    private fun downloadUrl(p: JSONObject, id: String) {
        val filename = p.optString("filename", "download")
        val req = DownloadManager.Request(Uri.parse(p.getString("url")))
            .setTitle(filename)
            .setMimeType(p.optString("mimeType", "application/octet-stream"))
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename)
        val dm = activity.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        pendingDownloads[dm.enqueue(req)] = id   // completion receiver reports back
    }

    private fun writeInline(p: JSONObject, id: String) {
        try {
            val filename = p.optString("filename", "download.csv")
            val bytes = Base64.decode(p.getString("contentBase64"), Base64.DEFAULT)
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, filename)
                put(MediaStore.Downloads.MIME_TYPE, p.optString("mimeType", "text/csv"))
            }
            val uri = activity.contentResolver
                .insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)!!
            activity.contentResolver.openOutputStream(uri).use { it!!.write(bytes) }
            sendCompletion(id, "success", null)
        } catch (e: Exception) {
            sendCompletion(id, "failed", "storage")
        }
    }

    /** Call from your DownloadManager ACTION_DOWNLOAD_COMPLETE receiver. */
    fun onDownloadFinished(downloadId: Long, success: Boolean) {
        val id = pendingDownloads.remove(downloadId) ?: return
        sendCompletion(id, if (success) "success" else "failed", if (success) null else "network")
    }

    private fun sendCompletion(id: String, status: String, reason: String?) {
        val event = JSONObject()
            .put("type", "file.downloaded").put("v", 1).put("id", id)
            .put("ts", Instant.now().toString())
            .put("payload", JSONObject().put("status", status).put("reason", reason))
        val call = "window.JiniBridge && window.JiniBridge.onNativeEvent(${JSONObject.quote(event.toString())})"
        webView.post { webView.evaluateJavascript(call, null) }
    }
}
```

**Wire it up (on the Activity/Fragment that owns the WebView):**
```kotlin
webView.settings.javaScriptEnabled = true
webView.settings.domStorageEnabled = true
webView.addJavascriptInterface(
    JiniHostBridge(activity, webView, onSessionExpired = { trigger ->
        // 1) re-mint the SSO JWT / session (your existing launch logic)
        // 2) webView.loadUrl(buildChatUrl(freshUserId, freshSessionId, freshAccessToken, isDark))
    }),
    "Android"   // MUST be exactly "Android" — the web detects window.Android.postMessage
)
webView.loadUrl(buildChatUrl(userId, sessionId, accessToken, isDarkTheme))
```

**`ACTION_DOWNLOAD_COMPLETE` receiver** (register once) to fire `onDownloadFinished`:
```kotlin
val receiver = object : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val downloadId = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1)
        val dm = ctx.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val ok = dm.query(DownloadManager.Query().setFilterById(downloadId)).use { c ->
            c.moveToFirst() &&
              c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) == DownloadManager.STATUS_SUCCESSFUL
        }
        bridge.onDownloadFinished(downloadId, ok)
    }
}
// registerReceiver(receiver, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), Context.RECEIVER_EXPORTED)
```

The chat URL with handoff params (the widget reads these from the query string, scrubs them from history at boot):
```kotlin
fun buildChatUrl(userId: String, sessionId: String, accessToken: String, isDark: Boolean) =
    "https://jini-chatbot.quanthm.com/".toUri().buildUpon()
        .appendQueryParameter("userId", userId)
        .appendQueryParameter("sessionId", sessionId)
        .appendQueryParameter("accessToken", accessToken)
        .appendQueryParameter("isDarkTheme", isDark.toString())
        .appendQueryParameter("platform", "android")
        .build().toString()
```

---

## 7. Acceptance criteria (self-check when done)

1. Tapping a report download in the chat triggers a `DownloadManager` download with a system notification; the PDF lands in Downloads.
2. The holdings CSV export saves a `.csv` to Downloads (inline path — no network fetch).
3. After a download completes, the chat's download card updates to its "saved" state (the completion callback fired).
4. When the SSO session expires, the app re-mints it and the WebView reloads into a working session (verify by letting a token expire, or forcing a 401).
5. A `file.ready` `url` whose token has expired returns HTTP 404 → surfaced as a failed/expired download, not a silent hang.
6. No crash on an unknown `type`, malformed JSON, or an unknown completion `id`.

---

## 8. Security (must hold)
- Token-only download URLs are unguessable + short-lived (5 min). **Do not log, cache, or share the full URL.**
- The bridge carries **no credentials** — the SSO/session tokens travel only as the WebView's launch query params (which the web app scrubs from history at boot). Don't route tokens through `webBridgeLogEvent`.
- Load the widget only from the official host (`https://jini-chatbot.quanthm.com`).

---

## Questions for the Choice Jini (web) team
Only if something here is ambiguous against your app. The web contract is fixed and live; everything above matches what production emits today. If you extend it (new event types), coordinate the `type` name + `payload` shape with the web team so both `v`ersions stay in sync.
