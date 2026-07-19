-- Conversation store schema (CHO-213 · design D6).
--
-- Target DDL for the wire-faithful transcript store: one thread per widget
-- session, strictly seq-ordered turns whose `content` is the exact Anthropic
-- content-block array, and prompt snapshots that make every thread a
-- self-contained {system, tools, messages} training example.
--
-- The whole file is idempotent — safe to re-run against a DB in any of the
-- known states. Apply from backend/ with:
--
--   uv run python -c "
--   import asyncio, asyncpg, pathlib
--   from app import config
--   async def main():
--       conn = await asyncpg.connect(config.database_url(), timeout=8)
--       await conn.execute(pathlib.Path('app/agent/schema.sql').read_text())
--       await conn.close()
--   asyncio.run(main())"
--
-- ---------------------------------------------------------------------------
-- MIGRATION NOTE (verified live 2026-07-19, task 3.1)
--
-- The dev DB already had `threads`/`turns` — but NOT the empty design-shaped
-- tables the proposal assumed. They were an earlier prototype's store
-- (schema_migrations rows 0001_conversation_store.sql +
-- 0002_turns_idempotency_guard.sql, applied 2026-07-18) with a different,
-- lossy shape — threads(thread_id uuid, user_id, platform, page,
-- entry_surface, model_version, status, …) and turns(turn_id uuid,
-- turn_number, user_message text, assistant_message text, detected_intent,
-- extracted_params/tool_calls/retrieval_context/render_blocks jsonb, token
-- counts, …) — and they contained data (28 threads / 47 turns from
-- 2026-07-18 testing). Because they were NOT empty, the drop-and-recreate
-- option was ruled out: the guarded block below RENAMES them to
-- `threads_legacy_v0` / `turns_legacy_v0` (rows, constraints and indexes
-- preserved, names suffixed to free the canonical names) and the design
-- tables are created fresh. The legacy tables are inert; drop them once the
-- old prototype's data is confirmed disposable.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    -- Legacy prototype shape is identified by its `thread_id` PK column
    -- (the design table uses `id`). Runs at most once.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'threads'
          AND column_name = 'thread_id'
    ) THEN
        ALTER TABLE public.turns RENAME TO turns_legacy_v0;
        ALTER TABLE public.threads RENAME TO threads_legacy_v0;
        -- Free the constraint/index names the new tables will use.
        ALTER TABLE public.threads_legacy_v0
            RENAME CONSTRAINT threads_pkey TO threads_legacy_v0_pkey;
        ALTER TABLE public.turns_legacy_v0
            RENAME CONSTRAINT turns_pkey TO turns_legacy_v0_pkey;
        ALTER TABLE public.turns_legacy_v0
            RENAME CONSTRAINT turns_thread_id_fkey TO turns_legacy_v0_thread_id_fkey;
        ALTER INDEX public.idx_turns_thread_id
            RENAME TO idx_turns_legacy_v0_thread_id;
        ALTER INDEX public.idx_turns_thread_id_turn_number
            RENAME TO idx_turns_legacy_v0_thread_id_turn_number;
        ALTER INDEX public.uq_turns_thread_id_turn_number
            RENAME TO uq_turns_legacy_v0_thread_id_turn_number;
    END IF;
END $$;

-- --- Target DDL -------------------------------------------------------------

-- Prompt snapshots: hash of (system text + canonical tool schema JSON) →
-- full content, so threads stay replayable across prompt deploys.
CREATE TABLE IF NOT EXISTS prompt_snapshots (
    hash       TEXT PRIMARY KEY,
    system     TEXT NOT NULL,
    tools      JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Threads of a widget session. `id` is app-generated (uuid4) so thread
-- creation never needs a DB round-trip on the chat path. A session id maps
-- to MANY thread rows over time (CHO-216: Restart closes the current thread
-- and starts a fresh one); the session's live thread is its newest row.
CREATE TABLE IF NOT EXISTS threads (
    id             UUID PRIMARY KEY,
    session_id     TEXT NOT NULL,
    client_code    TEXT,
    status         TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'resolved', 'escalated', 'expired')),
    prompt_hash    TEXT REFERENCES prompt_snapshots(hash),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- CHO-216 migration for databases created before restart support: the
-- original DDL declared session_id UNIQUE (one thread per session).
ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_session_id_key;
-- Latest-thread rehydration path: WHERE session_id ORDER BY created_at DESC.
CREATE INDEX IF NOT EXISTS threads_session_latest_idx
    ON threads (session_id, created_at DESC);

-- One row per step boundary. `role` is wire-faithful (tool results ride in
-- user-role turns); `kind` disambiguates. `content` is the exact Anthropic
-- content-block array (canonical key order); `meta` carries per-kind
-- telemetry (model/stop_reason/usage/latency for assistant turns; tool name/
-- is_error/duration for tool results; flow/action/slots for flow events).
-- Counters (clarify/task/session) are derived from turns — never columns.
CREATE TABLE IF NOT EXISTS turns (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    thread_id  UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    seq        INTEGER NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    kind       TEXT NOT NULL CHECK (kind IN (
                   'user_text', 'assistant_text', 'assistant_tool_use',
                   'tool_result', 'flow_event')),
    content    JSONB NOT NULL,
    meta       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (thread_id, seq)
);
