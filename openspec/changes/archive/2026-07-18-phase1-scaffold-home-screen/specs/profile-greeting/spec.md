# profile-greeting

## ADDED Requirements

### Requirement: Backend proxies Get Profile
The backend SHALL expose an endpoint that calls the upstream Get Profile API (`POST https://mf.choiceindia.com/api/v2/investor/profile/extended`) using the caller's session credentials — raw SSO JWT in `authorization`, session token in `from`, body `{"InvCode": "<USER_ID>"}` — and SHALL return only the derived first name to the client.

#### Scenario: Successful profile fetch
- **WHEN** the frontend requests the greeting with valid credentials
- **THEN** the backend responds with `{"firstName": "<name>"}` and nothing else from the upstream payload

### Requirement: First name derived from FirstHolderName
The backend SHALL derive the first name as the first whitespace-separated token of `Response.FirstHolderName`, title-cased (e.g., `"PRITAM NITIN WAVHAL"` → `"Pritam"`). No dedicated first-name field exists upstream.

#### Scenario: Multi-part name
- **WHEN** upstream returns `FirstHolderName` = "PRITAM NITIN WAVHAL"
- **THEN** the endpoint returns firstName "Pritam"

#### Scenario: Empty name
- **WHEN** upstream returns an empty or missing `FirstHolderName`
- **THEN** the endpoint responds as a degraded case (no first name) and the UI shows the generic greeting

### Requirement: PII minimization
The backend MUST NOT store, log, or forward the upstream profile response body. Only status codes and derived non-PII values may be logged. The upstream response contains PAN, DOB, address, email, mobile, and bank account details.

#### Scenario: Logging on success
- **WHEN** a profile fetch succeeds
- **THEN** logs contain at most the upstream status code and request timing — no response body, no name, no URL with credentials

### Requirement: Auth failure degrades gracefully
The backend SHALL map upstream 401 (expired/invalid SSO token, 8-hour lifetime) to a typed auth-expired response, and the frontend SHALL fall back to a non-personalized greeting.

#### Scenario: Expired token
- **WHEN** the upstream call returns 401
- **THEN** the backend returns an `AUTH_EXPIRED` error payload and the home screen renders "Hey there — what do you need?" without a client code
