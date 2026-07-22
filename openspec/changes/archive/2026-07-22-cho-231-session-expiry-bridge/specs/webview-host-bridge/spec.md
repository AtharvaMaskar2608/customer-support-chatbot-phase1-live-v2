# webview-host-bridge

## ADDED Requirements

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
