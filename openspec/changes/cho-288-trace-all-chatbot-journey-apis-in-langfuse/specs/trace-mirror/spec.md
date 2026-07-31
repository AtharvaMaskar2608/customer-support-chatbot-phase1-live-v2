## MODIFIED Requirements

### Requirement: Identity mapping keeps the two stores joinable
The Langfuse `session_id` SHALL be a salted HMAC of the FinX SessionId (the value carried as `X-Session-Id` / conversation-store `session_id` key) — never the raw token. The conversation-store `Thread.id` SHALL be carried as metadata `thread_id` on every mirrored chat-turn root (and on journey API observations). The Langfuse `user_id` SHALL be the raw client code — the same value Postgres `agent_traces.user_id` holds after CHO-287. The raw FinX SSO session id SHALL NOT be sent to Langfuse in any form; only its HMAC MAY appear as Langfuse `session.id` (or as an equivalent hashed metadata field). Postgres `agent_traces.thread_id` remains the conversation Thread.id so operators join Langfuse → Postgres via metadata `thread_id` + `user.id`, not via Langfuse session alone.

#### Scenario: A Langfuse chat turn can be pivoted to its Postgres row
- **WHEN** an operator opens a `chat_turn` in Langfuse and reads metadata `thread_id` and `user.id`
- **THEN** those values match `agent_traces.thread_id` and `agent_traces.user_id` for that turn

#### Scenario: Main Menu keeps the Langfuse session, changes thread metadata
- **WHEN** the user returns to Main Menu and `reset_thread` mints a new conversation thread under the same FinX SessionId
- **THEN** subsequent observations keep the same Langfuse `session.id` (HMAC of that FinX SessionId) and carry the new Thread.id in metadata `thread_id`

#### Scenario: The raw SSO session token never reaches Langfuse
- **WHEN** any span or journey observation is exported to Langfuse
- **THEN** the raw SSO session id appears nowhere in it — not in the session field, not in inputs or outputs, not in metadata
