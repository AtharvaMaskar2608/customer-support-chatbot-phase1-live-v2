# observability-dashboard

## ADDED Requirements

### Requirement: Admin-gated access, disabled by default
The trace dashboard API SHALL be gated by a single shared admin token
(`TRACES_ADMIN_TOKEN`), read via the backend's secret helper — NOT the per-user
FinX session auth. When the token is unset the dashboard SHALL be fully
disabled: every endpoint SHALL respond 404, exposing nothing by default. When
the token is set, a request SHALL be accepted only if its `X-Traces-Token`
header matches (compared in constant time), otherwise 401. The token and the
query text SHALL never be logged.

#### Scenario: Disabled when no token is configured
- **WHEN** a request hits any trace endpoint and `TRACES_ADMIN_TOKEN` is unset
- **THEN** the response is 404, so the dashboard is invisible by default

#### Scenario: Wrong or missing token is rejected
- **WHEN** the token is configured but the request has no `X-Traces-Token` header or a non-matching one
- **THEN** the response is 401 and no trace data is returned

#### Scenario: Matching token is served
- **WHEN** the token is configured and the request's `X-Traces-Token` header matches
- **THEN** the endpoint returns the requested trace data with 200

### Requirement: Searchable, paginated trace and thread listings
The API SHALL expose a recent-first trace list filterable by thread id, model,
error flag, tool name and a created-at date range, paginated by limit (default
50, max 200) and offset, returning the rollup fields and a total match count but
NOT the span tree (the list stays light). It SHALL also expose threads rolled up
from their turns (turn count, last activity, total input tokens, whether any
turn errored), recent-first and paginated.

#### Scenario: Filtered, paginated traces newest-first
- **WHEN** the trace list is requested with a `had_error=true` and `model` filter
- **THEN** only matching traces are returned, newest first, with a total count for paging, and without spans

#### Scenario: Threads rolled up from their turns
- **WHEN** the threads list is requested
- **THEN** each entry rolls up its turns — count, last-activity time, total input tokens, and an error flag — most-recently-active first

### Requirement: Full execution graph for a single trace or thread
The API SHALL return one trace by id including its parsed span tree, and all of
one thread's turns in chronological (ascending) order each including its spans,
so the UI can render the nested `agent → llm / tool → retriever` graph and a
per-turn token trend. A request for an unknown trace id SHALL return 404.

#### Scenario: Trace detail carries the parsed span tree
- **WHEN** a single trace is requested by id
- **THEN** the response includes its rollup fields plus the decoded `spans` array (agent/llm/tool/retriever nodes with type, name, duration and metadata)

#### Scenario: Thread turns are chronological with spans
- **WHEN** a thread's turns are requested
- **THEN** they are returned oldest-first, each with its spans, so the turn sequence and token trend can be reconstructed

### Requirement: Read-only exposure of already-safe data
The dashboard SHALL only read the `agent_traces` table; it SHALL NOT write, and
SHALL NOT re-derive or expose any value beyond what CHO-261 already stored —
i.e. only the pre-masked inputs/outputs and the HMAC-hashed thread/user ids.
When the database pool is unavailable, endpoints SHALL respond 503 rather than
error, mirroring the KB route's degraded posture.

#### Scenario: Only masked, hashed fields are served
- **WHEN** any endpoint returns trace data
- **THEN** the values are exactly the stored (already PII-masked) inputs/outputs and (already hashed) thread/user ids — no raw credential or personal data is reconstructed

#### Scenario: No database pool available
- **WHEN** a valid-token request arrives but no DB pool is configured
- **THEN** the endpoint responds 503 (trace store unavailable), not a 500

### Requirement: Isolated operator web page
The dashboard UI SHALL be a Vite entry separate from the chat app and the corner
widget (`traces.html` with its own React root), so it shares no runtime state
with the customer-facing surfaces. It SHALL gate on the admin token (prompted,
stored in localStorage, sent as `X-Traces-Token` on every fetch) and show a
clear disabled/unauthorized state on 404/401. It SHALL render the nested span
tree with per-span type, name, duration and key metadata (llm: model + token
split; tool: error flag; retriever: chunk count + embedder) and a hand-rolled
token-trend gauge for a selected thread, without adding a chart or router
dependency. The production build SHALL emit `dist/traces.html`.

#### Scenario: Token gate drives every request
- **WHEN** the operator enters the admin token
- **THEN** it is stored in localStorage and sent as `X-Traces-Token` on every API call, and a later 401/404 returns the page to the gate with a clear message

#### Scenario: Nested graph and token trend render
- **WHEN** the operator opens a trace and a thread
- **THEN** the trace shows the nested agent/llm/tool/retriever span tree with per-span metadata and masked input/output, and the thread shows a per-turn input-token trend with the cache-read split
