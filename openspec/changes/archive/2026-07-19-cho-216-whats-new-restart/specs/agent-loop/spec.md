# agent-loop (delta)

## ADDED Requirements

### Requirement: Conversation reset endpoint
The backend SHALL expose `POST /api/chat/reset`, authenticated by the same headers as `/api/chat` (missing credentials → HTTP 400 `MISSING_CREDENTIALS`, no side effects). On success it SHALL close the session's current thread in the store and start a fresh one (delegated to the conversation store's reset), make no model call, and return `{"ok": true}`. The endpoint SHALL be idempotent.

#### Scenario: Reset starts a blank slate
- **WHEN** the user resets and then sends "now the same for F&O"
- **THEN** the model sees no prior conversation or flow-event memory, and cap counters have restarted from zero

#### Scenario: Missing credentials
- **WHEN** `/api/chat/reset` is called without the auth headers
- **THEN** the response is HTTP 400 `{"error": "MISSING_CREDENTIALS"}` and no thread is touched
