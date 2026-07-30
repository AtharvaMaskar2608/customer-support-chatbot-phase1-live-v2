## MODIFIED Requirements

### Requirement: No PII or secrets in stored traces
Span inputs/outputs SHALL never contain credentials or personal data (SSO JWT,
session id, PAN, DOB, bank details, email, phone) nor raw upstream
bodies. Credentialed context SHALL never be an observed argument (it rides in a
closure), and a mask SHALL redact credential- and PII-shaped values and
denylisted keys before persistence. The `thread_id` SHALL be the internal
conversation-store `Thread.id` (see "Trace thread_id matches conversation
store"); the raw session token SHALL never be stored.

The client code is an internal account identifier and is NOT personal data. The
`user_id` SHALL therefore be stored raw, in both the Postgres row and any
mirror of it, so a trace can be found by the identifier an operator actually
holds. This reverses the earlier pseudonymisation, which bought no compliance
benefit and cost the lookup.

That relaxation is scoped to the dedicated identity field and to nothing else.
The SSO session id remains excluded on separate grounds — it authenticates the
report endpoints, so keeping it out of an observability store is a security
constraint rather than a privacy one — and the denylist SHALL continue to mask
client-code-shaped values appearing incidentally inside tool inputs or upstream
payloads, where they are unstructured and adjacent to other data.

These guarantees bind **every sink the assembled span tree is written to**, not
only the Postgres row — including the Langfuse mirror (see the `trace-mirror`
capability) and any future exporter. A sink SHALL apply the same mask, from the
same single definition, before any span leaves the process; masking SHALL happen
client-side, so unredacted values never cross the network even to
self-hosted infrastructure. Adding a sink SHALL NOT widen what is stored: if a
value may not appear in `agent_traces`, it may not appear in any mirror of it.

#### Scenario: The raw session token is never stored
- **WHEN** a trace row is written
- **THEN** grouping uses the internal conversation `Thread.id` — the raw session token (a live auth credential) never appears in the table

#### Scenario: The client code is stored raw and is searchable
- **WHEN** a trace row is written for a turn
- **THEN** `user_id` is the client code itself, so a trace can be found by customer without resolving a hash

#### Scenario: A client code inside a payload is still masked
- **WHEN** a client-code-shaped value appears under a denylisted key inside a tool input or upstream payload
- **THEN** the mask still replaces it — only the dedicated `user_id` identity field carries it in the clear

#### Scenario: Credential- and PII-shaped values are masked
- **WHEN** a span input would contain a JWT, PAN, email, phone, opaque token, or a denylisted key
- **THEN** the mask replaces it with a redaction marker before the row is written

#### Scenario: A second sink inherits the same mask
- **WHEN** the span tree is exported to a mirror as well as to Postgres
- **THEN** the same mask definition governs both, and a value forbidden in the table is equally absent from the mirror

#### Scenario: Masking precedes egress
- **WHEN** a span is exported to an external observability instance
- **THEN** redaction has already been applied in-process, so the unredacted value is never transmitted

### Requirement: Trace thread_id matches conversation store
Each persisted agent turn SHALL set `agent_traces.thread_id` to the active
conversation-store `Thread.id` (bound after `store.get_thread` during the
turn), not an HMAC of the FinX/session key. A Main Menu or cold-load
`reset_thread` that mints a new store thread SHALL therefore start a new
trace/cost bucket. `user_id` SHALL be the raw client code — an internal account
identifier, not personal data — so traces remain searchable by customer.

#### Scenario: Reset starts a new trace thread bucket
- **WHEN** the conversation store resets the session and the next chat turn
  loads a new `Thread.id`
- **THEN** the persisted trace for that turn carries the new id, separate from
  prior turns under the old id

#### Scenario: Client code is stored as-is
- **WHEN** a turn is persisted
- **THEN** `user_id` is the client code verbatim, not a hash of it
