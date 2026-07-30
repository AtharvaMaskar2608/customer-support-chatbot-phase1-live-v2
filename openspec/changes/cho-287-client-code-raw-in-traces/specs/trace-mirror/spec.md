## MODIFIED Requirements

### Requirement: Identity mapping keeps the two stores joinable
The Langfuse `session_id` SHALL be the conversation-store `Thread.id` and the Langfuse `user_id` SHALL be the client code — in both cases the identical value the Postgres row stores, which is what keeps the two stores joinable on either key. The client code is an internal account identifier, not personal data, and is carried raw so a Langfuse trace can be found by customer. The FinX SSO session id is a different matter: it is a live credential (the report endpoints authenticate with it) and SHALL NOT be sent to Langfuse in any form; where correlation to an SSO session is required, a salted HMAC of it MAY be carried in metadata, never the value itself.

#### Scenario: A Langfuse trace can be pivoted to its Postgres row
- **WHEN** an operator opens a trace in Langfuse and reads its session and user identifiers
- **THEN** those identifiers match the `thread_id` and `user_id` of the corresponding `agent_traces` row exactly, so the same query finds it in either store

#### Scenario: A trace is findable by client code
- **WHEN** an operator has a customer's client code and searches Langfuse by user
- **THEN** that customer's traces are returned directly, with no hash to resolve first

#### Scenario: Main Menu starts a new Langfuse session
- **WHEN** the user returns to Main Menu and `reset_thread` mints a new conversation thread
- **THEN** subsequent turns carry the new thread id as the Langfuse session id, so a session never rolls up across a reset

#### Scenario: The SSO session token never reaches Langfuse
- **WHEN** any span is exported to Langfuse
- **THEN** the raw SSO session id appears nowhere in it — not in the session field, not in inputs or outputs, not in metadata (the client code, by contrast, is carried deliberately as `user_id`)
