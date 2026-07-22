# finx-report-backend

## ADDED Requirements

### Requirement: Download envelope reports token expiry
The report download envelope SHALL additionally report the download token's time-to-live as `ttlSeconds` and its absolute expiry as `expiresAt` (UTC ISO-8601), so a consumer — the native host bridge — knows when the token-only download URL stops working without hardcoding the TTL. Both values SHALL be computed at envelope-build time from the configured TTL on the wall clock (`datetime.now(UTC) + ttlSeconds`), NOT derived from the token store's internal `monotonic()` expiry. The fields SHALL be additive (existing consumers ignore them), the download endpoint SHALL continue to return HTTP 404 for an unknown or expired token without distinguishing the two, and no upstream URL SHALL be exposed.

#### Scenario: Download envelope includes expiry
- **WHEN** a download report is generated
- **THEN** the envelope includes `ttlSeconds` and an `expiresAt` UTC timestamp consistent with the configured token TTL, alongside the existing `delivery`, `file`, and `fileToken`

#### Scenario: Expired token still 404s indistinguishably
- **WHEN** the download URL is fetched after `expiresAt` (or for an unknown token)
- **THEN** the endpoint returns HTTP 404 `{"error":"NOT_FOUND"}`, not revealing whether the token was unknown or merely expired
