# finx-report-backend Specification

## Purpose
TBD - created by archiving change cho-207-report-flows. Update Purpose after archive.
## Requirements
### Requirement: Per-endpoint credential routing
The backend SHALL select the upstream credential by endpoint, not by app: the SessionId in `authorization` for the .NET/Go report endpoints (P&L, Ledger, Tax, Contract Notes list/download), and the SSO JWT for the MIS/CML endpoint. The `from` header is a non-authenticating build tag.

#### Scenario: Report endpoint uses SessionId
- **WHEN** the backend calls a .NET report endpoint
- **THEN** it sends the SessionId as `authorization`, not the SSO JWT

#### Scenario: MIS endpoint uses SSO JWT
- **WHEN** the backend calls the MIS/CML endpoint
- **THEN** it sends the SSO JWT as `authorization` plus the MIS-specific headers

### Requirement: Two-layer error model
The backend SHALL detect auth failures by HTTP status (real 401 → `AUTH_EXPIRED`), the contract-notes empty case by HTTP 204, and business failures by the body status field (`Status`/`StatusCode` != success → `NO_DATA`). It MUST NOT string-match the `Reason` text (wording differs across endpoints). Other failures → `UPSTREAM_ERROR`.

#### Scenario: Business failure is HTTP 200
- **WHEN** upstream returns HTTP 200 with a failure status in the body
- **THEN** the backend returns `NO_DATA`, distinct from `AUTH_EXPIRED`

#### Scenario: Expired session
- **WHEN** upstream returns HTTP 401
- **THEN** the backend returns `AUTH_EXPIRED`

### Requirement: Delivery/PII layer
For download requests the backend SHALL fetch the artifact server-side and stream it to the client as a file, never returning the upstream report URL, signed link, or `file_id`. For email requests it SHALL mask the echoed address before returning it. The backend MUST NOT store or log upstream response bodies, report URLs, or credentials — status code and timing only.

#### Scenario: Download never exposes the upstream URL
- **WHEN** a download report is requested
- **THEN** the client receives the file bytes/stream and the raw upstream URL never reaches the browser or logs

#### Scenario: Email address masked
- **WHEN** an email delivery confirmation is returned
- **THEN** the registered email is masked (e.g. `san***@gmail.com`)

### Requirement: Session-bound requests (IDOR defense)
Every upstream call SHALL be bound to the authenticated widget session's client code; the backend MUST NOT accept a client code supplied by the client. This defends the unauthenticated contract-note chain.

#### Scenario: Client code comes from session
- **WHEN** any report is requested
- **THEN** the client code sent upstream is derived from the authenticated session, never from request input

### Requirement: Download envelope reports token expiry
The report download envelope SHALL additionally report the download token's time-to-live as `ttlSeconds` and its absolute expiry as `expiresAt` (UTC ISO-8601), so a consumer — the native host bridge — knows when the token-only download URL stops working without hardcoding the TTL. Both values SHALL be computed at envelope-build time from the configured TTL on the wall clock (`datetime.now(UTC) + ttlSeconds`), NOT derived from the token store's internal `monotonic()` expiry. The fields SHALL be additive (existing consumers ignore them), the download endpoint SHALL continue to return HTTP 404 for an unknown or expired token without distinguishing the two, and no upstream URL SHALL be exposed.

#### Scenario: Download envelope includes expiry
- **WHEN** a download report is generated
- **THEN** the envelope includes `ttlSeconds` and an `expiresAt` UTC timestamp consistent with the configured token TTL, alongside the existing `delivery`, `file`, and `fileToken`

#### Scenario: Expired token still 404s indistinguishably
- **WHEN** the download URL is fetched after `expiresAt` (or for an unknown token)
- **THEN** the endpoint returns HTTP 404 `{"error":"NOT_FOUND"}`, not revealing whether the token was unknown or merely expired

