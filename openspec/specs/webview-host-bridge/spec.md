# webview-host-bridge Specification

## Purpose
TBD - created by archiving change cho-230-webview-file-bridge. Update Purpose after archive.
## Requirements
### Requirement: File delivery to the native host
The web UI SHALL deliver a generated file to the native host through a single versioned bridge event `file.ready`, emitted via `window.Android.postMessage(<json>)`, carrying a `transport` discriminator. For `transport: "url"` (P&L, ledger, capital-gains, contract notes, and agent file artifacts) the payload SHALL carry an absolute token-only download URL (resolved from the page origin) plus `auth: "none"`. For `transport: "inline"` (the holdings CSV, which is built client-side and has no server token) the payload SHALL carry the file bytes as UTF-8 base64 in `contentBase64`. Every event envelope SHALL include a schema version (`v`), a unique correlation id (`id`), an emit timestamp (`ts`), and the file's display metadata (`filename`, `mimeType`, `format`, `passwordProtected`).

#### Scenario: Tokened report delivered as a URL
- **WHEN** a P&L, ledger, capital-gains, contract-note, or agent file artifact is ready and the native bridge is present
- **THEN** a `file.ready` event with `transport: "url"`, an absolute `/api/report/file/{token}` URL, `auth: "none"`, and the file metadata is posted via `window.Android.postMessage`

#### Scenario: Holdings CSV delivered inline
- **WHEN** the holdings CSV export is triggered and the native bridge is present
- **THEN** a `file.ready` event with `transport: "inline"`, `mimeType: "text/csv"`, and the CSV bytes as base64 in `contentBase64` is posted — no download URL

#### Scenario: Envelope carries version and correlation id
- **WHEN** any `file.ready` event is emitted
- **THEN** it includes `v`, a unique `id`, `ts`, and a `payload` — so native can branch on version and correlate a later completion callback

### Requirement: Capability-based detection with a web fallback
The web UI SHALL detect the native host by capability — `window.Android.postMessage` being a function — and SHALL NOT rely on the `platform` handoff parameter. It SHALL emit a bridge event only when the host is present. When it is absent (browser or corner-web embed), the UI SHALL fall back to the existing browser download unchanged — a token anchor for reports, a `Blob` object URL for the holdings CSV.

#### Scenario: Native host present
- **WHEN** `window.Android.postMessage` is a function and a file is ready
- **THEN** the file is handed to the host via the bridge and the browser download does not run

#### Scenario: No native host
- **WHEN** `window.Android` is absent
- **THEN** the sender reports it did not handle the file and the UI performs the existing browser download

### Requirement: Download completion callback
The native host SHALL report file-delivery completion to the web UI by invoking `window.JiniBridge.onNativeEvent(<json>)` with a `file.downloaded` event that echoes the originating `file.ready` correlation `id` and a `status` of `success` or `failed` (with an optional failure `reason`). The web UI SHALL match on the `id` to update the corresponding download card, and SHALL ignore unknown or malformed callbacks without error.

#### Scenario: Success updates the matching card
- **WHEN** the host posts `file.downloaded` with `status: "success"` and a known `id`
- **THEN** the matching download card shows its saved/success state

#### Scenario: Unknown or malformed callback is ignored
- **WHEN** the host posts a callback whose `id` is unknown, or whose JSON is malformed
- **THEN** the web UI ignores it without throwing and leaves cards unchanged

### Requirement: Session expiry is signaled to the host
When the web UI observes FinX session expiry — an `AUTH_EXPIRED` (HTTP 401) result from the profile/greeting hit, an agent call, or a report/data call — it SHALL emit a `session.expired` host event via `window.Android.postMessage`, reusing the common bridge envelope (`type`/`v`/`id`/`ts`/`payload`), carrying a `trigger` in `{ "profile", "agent", "report", "data" }`. The event SHALL be emitted at most once per detected expiry (guarded against parallel or repeated 401s). When no native host is present, the UI SHALL fall back to the existing fixed "reopen from FinX" session-expired copy with no error and no bridge call.

#### Scenario: Expiry at boot signals the host once
- **WHEN** the profile/greeting hit returns `AUTH_EXPIRED` at boot and the native bridge is present
- **THEN** exactly one `session.expired` event with `trigger: "profile"` is posted to the host

#### Scenario: Repeat 401s do not re-fire
- **WHEN** a second `AUTH_EXPIRED` is observed for the same dead session (a parallel tool call or a retry)
- **THEN** no additional `session.expired` event is emitted until the session is reloaded / renewed

#### Scenario: No host falls back to copy
- **WHEN** session expiry is observed and `window.Android` is absent
- **THEN** the UI shows the fixed "reopen from FinX" session-expired copy and posts no bridge event

