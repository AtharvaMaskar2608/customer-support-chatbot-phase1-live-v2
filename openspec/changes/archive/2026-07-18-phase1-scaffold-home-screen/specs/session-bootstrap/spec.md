# session-bootstrap

## ADDED Requirements

### Requirement: Ingest FinX handoff parameters
The chat page SHALL read the query parameters provided by the FinX host (`userId`, `sessionId`, `accessToken`, `isDarkTheme`, `platform`, `obStatus`, and optional screen name) exactly once at boot and store them in an in-memory session context (USER_ID, session_id, SSO token, theme, platform, page, onboarding status).

#### Scenario: Normal handoff
- **WHEN** the page is opened with all handoff query parameters present
- **THEN** the session context is populated and the app renders the home screen

#### Scenario: obStatus has no behavioral effect
- **WHEN** the page is opened with any `obStatus` value
- **THEN** the value is stored but no feature is gated or altered by it

### Requirement: Strip credentials from the address bar
After reading the query parameters, the frontend SHALL remove them from the visible URL via history replacement so tokens do not persist in webview history or screenshots.

#### Scenario: URL cleaned after boot
- **WHEN** the session context has been populated
- **THEN** the address bar no longer contains `accessToken`, `sessionId`, or `userId` values

### Requirement: Degrade when credentials are missing
The page SHALL still render when credentials are absent or incomplete, in a non-personalized state, rather than failing to load.

#### Scenario: Opened without credentials
- **WHEN** the page is opened with no query parameters (e.g., direct visit)
- **THEN** the home screen renders with the generic greeting and no client code in the header
