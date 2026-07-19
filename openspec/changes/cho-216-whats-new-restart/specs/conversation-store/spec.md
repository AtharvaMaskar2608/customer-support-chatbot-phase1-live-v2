# conversation-store (delta)

## ADDED Requirements

### Requirement: Per-session thread reset with retention
The store SHALL support resetting a session's conversation: the active thread is closed with status `resolved` (the status write persisted through the existing single-writer queue; every turn row retained for the training corpus) and a fresh thread (new id, same session id, current prompt hash, empty turns) becomes the session's active thread — so derived counters, clarify state, and flow-event memory all restart naturally. A session id therefore maps to its LATEST thread: in-memory lookups return the fresh thread immediately, and rehydration on cache miss SHALL select the session's most recent thread by creation time. Flow events recorded after a reset SHALL attach to the fresh thread.

#### Scenario: Reset preserves history and clears memory
- **WHEN** a session with 30 turns is reset
- **THEN** the old thread's rows remain in Postgres with status `resolved`, and the session's next message lands in a new empty thread with counters at zero

#### Scenario: Rehydration picks the latest thread
- **WHEN** the backend restarts after a session was reset and chatted again
- **THEN** a cache-miss lookup for that session rehydrates the newest thread, not the closed one
