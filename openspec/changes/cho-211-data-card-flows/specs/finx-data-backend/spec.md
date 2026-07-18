# finx-data-backend

## ADDED Requirements

### Requirement: Per-endpoint auth routing for data endpoints
The backend SHALL route each data endpoint with its verified credential scheme: Holdings (`finxomne.choiceindia.com/COTI/V1/Holdings`) with `authorization: Session <SessionId>`; Pay-In/Pay-Out (`finx.choiceindia.com/api/middleware/GetPayInTxnRpt` / `GetPayOutTxnRpt`) with the bare SessionId; Brokerage (`api.choiceindia.com/middleware-go/v2/get-brokerage-slab`) with the raw SSO JWT. The web app's additional Holdings credentials (`ssotoken`, body `accessToken`, `fingerprint`) SHALL NOT be required (verified live 2026-07-18).

#### Scenario: Holdings call
- **WHEN** the backend calls Holdings
- **THEN** it sends only `Session <SessionId>` as authorization and succeeds

#### Scenario: Brokerage call
- **WHEN** the backend calls the brokerage slab
- **THEN** it authorizes with the raw SSO JWT (not the SessionId)

### Requirement: Boundary normalization
The backend SHALL normalize upstream inconsistencies before anything reaches the frontend: Holdings `LTP`/`CP` paise → rupees (`ABP` already rupees); statuses matched case-insensitively → canonical `SUCCESS | PENDING | FAILURE | CANCELLED`; both upstream date formats (ISO-`T` and space-separated) → ISO 8601; both empty-sentinels (`"1900-01-01T00:00:00"` and `""`) → null.

#### Scenario: Paise decode
- **WHEN** Holdings returns `LTP: 11579`
- **THEN** the API response carries `ltp: 115.79` (matching FinX's own CSV export)

#### Scenario: Pay-out status casing
- **WHEN** pay-out returns `Status: "Success"` or `"CANCELLED"`
- **THEN** the normalized stream carries `SUCCESS` / `CANCELLED`

### Requirement: Server-side derivation
All displayed metrics SHALL be computed server-side in one tested place: holdings per-row `current`, `invested`, `pnl`, `pnlPct`, `day`, `dayPct`, `allocation` plus portfolio totals and freshness (= max `LUT` across scrips); money status counts and landed-in/landed-out totals (successful transactions only — pending and failed amounts MUST NOT contribute to totals).

#### Scenario: Landed totals exclude noise
- **WHEN** the stream holds a ₹1,01,49,986 pending attempt and ₹860 of successful deposits
- **THEN** the landed-in total is ₹860

### Requirement: Merged money endpoint
`POST /api/data/money` SHALL fetch Pay-In and Pay-Out concurrently, merge them into a single newest-first stream with a `dir` attribute (`in`/`out`), and surface upstream `TotalRecords` for pagination. Pay-out `Reason` SHALL be forwarded verbatim for display and MUST never be used for branching logic.

#### Scenario: One round trip
- **WHEN** the frontend requests the money timeline
- **THEN** one backend call returns both directions merged, sorted newest first

### Requirement: PII forwarding whitelist
Each endpoint SHALL forward only its whitelisted fields. Bank destinations SHALL be masked to bank name + last-4 digits. The backend SHALL drop: `ClientName`, full `ClientBankAccNo`, `JiffyTransactionId`, `AtomReferenceNo`, and pay-out's `Search_All_Levels` (internal branch/employee hierarchy). Logging SHALL remain status + timing only — never response bodies.

#### Scenario: Internal hierarchy never leaves
- **WHEN** pay-out responds with `Search_All_Levels`
- **THEN** that field appears nowhere in the backend response or logs

#### Scenario: Masked destination
- **WHEN** a transaction's account number is `50100218008829`
- **THEN** the response carries a masked form ending in `8829` with no full number

### Requirement: Error model reuse
Data endpoints SHALL reuse the two-layer error model: real HTTP 401 → `AUTH_EXPIRED`; empty payloads (Holdings `{}` dict, empty transaction lists) → `EMPTY`; body-level `Status`/`StatusCode` failure → `NO_DATA` (never string-matching `Reason`); anything else → `UPSTREAM_ERROR`, with the connect-retry and IPv4 transport already in place.

#### Scenario: Empty portfolio
- **WHEN** Holdings returns `Status: Success` with an empty `lDictHoldingData`
- **THEN** the backend returns the EMPTY kind and the card shows the empty-portfolio state
