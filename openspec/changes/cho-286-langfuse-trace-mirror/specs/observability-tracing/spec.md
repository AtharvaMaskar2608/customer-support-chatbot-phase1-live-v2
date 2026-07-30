## MODIFIED Requirements

### Requirement: No PII or secrets in stored traces
Span inputs/outputs SHALL never contain credentials or personal data (SSO JWT,
session id, client code, PAN, DOB, bank details, email, phone) nor raw upstream
bodies. Credentialed context SHALL never be an observed argument (it rides in a
closure), and a mask SHALL redact credential- and PII-shaped values and
denylisted keys before persistence. The `user_id` SHALL be an HMAC hash of the
client code, and the `thread_id` SHALL be the internal conversation-store
`Thread.id` (see "Trace thread_id matches conversation store"); the raw session
token and the raw client code SHALL never be stored.

These guarantees bind **every sink the assembled span tree is written to**, not
only the Postgres row — including the Langfuse mirror (see the `trace-mirror`
capability) and any future exporter. A sink SHALL apply the same mask, from the
same single definition, before any span leaves the process; masking SHALL happen
client-side, so unredacted values never cross the network even to
self-hosted infrastructure. Adding a sink SHALL NOT widen what is stored: if a
value may not appear in `agent_traces`, it may not appear in any mirror of it.

#### Scenario: The raw session token is never stored
- **WHEN** a trace row is written
- **THEN** grouping uses the internal conversation `Thread.id` and the hashed client code — the raw session token (a live auth credential) never appears in the table

#### Scenario: Credential- and PII-shaped values are masked
- **WHEN** a span input would contain a JWT, PAN, email, phone, opaque token, or a denylisted key
- **THEN** the mask replaces it with a redaction marker before the row is written

#### Scenario: A second sink inherits the same mask
- **WHEN** the span tree is exported to a mirror as well as to Postgres
- **THEN** the same mask definition governs both, and a value forbidden in the table is equally absent from the mirror

#### Scenario: Masking precedes egress
- **WHEN** a span is exported to an external observability instance
- **THEN** redaction has already been applied in-process, so the unredacted value is never transmitted
