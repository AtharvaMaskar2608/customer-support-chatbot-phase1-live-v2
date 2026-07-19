"""Conversation store (CHO-213): seq ordering, wire-faithful replay,
degraded persistence, restart rehydration, prompt snapshots.

The suite runs entirely against fakes — no live DB. One end-to-end round
trip runs live when DATABASE_URL is set (skipped otherwise).
"""

import asyncio
import json
import logging
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.agent.store import (
    ThreadStore,
    compute_prompt_hash,
)
from app.main import create_app

# --- fakes -------------------------------------------------------------------


class FakeConn:
    def __init__(self, executed):
        self._executed = executed

    async def execute(self, sql, *args):
        self._executed.append((sql, args))


class _Acquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    """Records writer executes; serves canned rows for rehydration."""

    def __init__(self, thread_row=None, turn_rows=None):
        self.executed = []
        self.thread_row = thread_row
        self.turn_rows = turn_rows or []

    def acquire(self):
        return _Acquire(FakeConn(self.executed))

    async def fetchrow(self, sql, *args):
        return self.thread_row

    async def fetch(self, sql, *args):
        return self.turn_rows


class FailingPool:
    """DB/tunnel down: every operation raises."""

    def acquire(self):
        raise ConnectionError("tunnel down")

    async def fetchrow(self, sql, *args):
        raise ConnectionError("tunnel down")

    async def fetch(self, sql, *args):
        raise ConnectionError("tunnel down")


def _text(text):
    return [{"type": "text", "text": text}]


def _turn_writes(pool):
    return [args for sql, args in pool.executed if "INSERT INTO turns" in sql]


def _scramble(obj):
    """Reverse-sort dict keys recursively — stands in for jsonb's key
    reordering so tests prove read-side canonicalization."""
    if isinstance(obj, dict):
        return {k: _scramble(obj[k]) for k in sorted(obj, reverse=True)}
    if isinstance(obj, list):
        return [_scramble(v) for v in obj]
    return obj


def _rows_from_writes(pool, thread_id):
    """Turn the captured INSERT INTO turns args back into fetch rows, with
    content/meta scrambled the way jsonb would."""
    rows = []
    for args in _turn_writes(pool):
        rows.append(
            {
                "seq": args[1],
                "role": args[2],
                "kind": args[3],
                "content": json.dumps(_scramble(json.loads(args[4]))),
                "meta": json.dumps(_scramble(json.loads(args[5]))),
                "created_at": args[6],
            }
        )
    return rows


def _thread_row_from_writes(pool):
    for sql, args in pool.executed:
        if "INSERT INTO threads" in sql:
            return {
                "id": args[0],
                "session_id": args[1],
                "client_code": args[2],
                "status": args[3],
                "prompt_hash": args[4],
                "created_at": args[5],
                "last_active_at": args[6],
            }
    return None


# --- a canonical four-message exchange used by several tests -----------------


async def _build_exchange(store, session_id):
    """user → assistant(parallel tool_use) → 2 tool_results → assistant."""
    thread = await store.get_thread(session_id, client_code="X008593")
    store.append_turn(
        thread, role="user", kind="user_text", content=_text("show my pnl")
    )
    store.append_turn(
        thread,
        role="assistant",
        kind="assistant_tool_use",
        content=[
            {"type": "text", "text": "Fetching both."},
            {"type": "tool_use", "id": "tu_1", "name": "get_pnl",
             "input": {"segment": "EQ", "fromDate": "2026-01-01"}},
            {"type": "tool_use", "id": "tu_2", "name": "kb_search",
             "input": {"query": "pnl charges"}},
        ],
        meta={"model": "m", "stop_reason": "tool_use", "usage": {"input_tokens": 9}},
    )
    store.append_turn(
        thread,
        role="user",
        kind="tool_result",
        content=[{"type": "tool_result", "tool_use_id": "tu_1",
                  "content": [{"type": "text", "text": "{\"kind\":\"ok\"}"}]}],
        meta={"tool_name": "get_pnl", "is_error": False, "duration_ms": 40},
    )
    store.append_turn(
        thread,
        role="user",
        kind="tool_result",
        content=[{"type": "tool_result", "tool_use_id": "tu_2",
                  "content": [{"type": "text", "text": "answer ₹20"}]}],
        meta={"tool_name": "kb_search", "is_error": False, "duration_ms": 12},
    )
    store.append_turn(
        thread, role="assistant", kind="assistant_text",
        content=_text("Here is your P&L."),
        meta={"model": "m", "stop_reason": "end_turn"},
    )
    return thread


# --- seq ordering (3.3) ------------------------------------------------------


def test_seq_ordering_under_interleaved_enqueues():
    """Interleaved appends across two threads: per-thread seq is strictly
    1..n and persisted writes preserve enqueue (FIFO) order."""

    async def scenario():
        pool = FakePool()
        store = ThreadStore(pool=pool)
        await store.start()
        thread_a = await store.get_thread("sess-a")
        thread_b = await store.get_thread("sess-b")
        for i in range(3):
            store.append_turn(
                thread_a, role="user", kind="user_text", content=_text(f"a{i}")
            )
            store.append_turn(
                thread_b, role="user", kind="user_text", content=_text(f"b{i}")
            )
        await store.close()  # graceful drain writes everything
        return pool, thread_a, thread_b

    pool, thread_a, thread_b = asyncio.run(scenario())
    assert [t.seq for t in thread_a.turns] == [1, 2, 3]
    assert [t.seq for t in thread_b.turns] == [1, 2, 3]
    writes = _turn_writes(pool)
    assert len(writes) == 6
    # FIFO: the interleaved global order survives into the writer
    order = [(args[0], args[1]) for args in writes]  # (thread_id, seq)
    assert order == [
        (thread_a.id, 1), (thread_b.id, 1),
        (thread_a.id, 2), (thread_b.id, 2),
        (thread_a.id, 3), (thread_b.id, 3),
    ]
    per_thread = {}
    for thread_id, seq in order:
        assert seq == per_thread.get(thread_id, 0) + 1  # strictly increasing
        per_thread[thread_id] = seq


def test_append_turn_is_synchronous_and_validates():
    async def scenario():
        store = ThreadStore(pool=FakePool())
        thread = await store.get_thread("sess-v")
        turn = store.append_turn(  # plain call — no await: chat never blocks
            thread, role="user", kind="user_text", content=_text("hi")
        )
        assert turn.seq == 1
        with pytest.raises(ValueError):
            store.append_turn(thread, role="tool", kind="user_text", content=[])
        with pytest.raises(ValueError):
            store.append_turn(thread, role="user", kind="banana", content=[])
        with pytest.raises(ValueError):
            store.set_status(thread, "closed")

    asyncio.run(scenario())


# --- wire-faithful replay (3.2) ----------------------------------------------


def test_replay_round_trip_is_byte_identical():
    """messages → turns → (scrambled jsonb) rows → rehydrate → messages must
    be byte-equal, with both tool_results merged into ONE user message."""

    async def scenario():
        pool = FakePool()
        store = ThreadStore(pool=pool)
        await store.start()
        thread = await _build_exchange(store, "sess-r")
        wire = thread.messages()
        await store.close()

        rehydrate_pool = FakePool(
            thread_row=_thread_row_from_writes(pool),
            turn_rows=_rows_from_writes(pool, thread.id),
        )
        store2 = ThreadStore(pool=rehydrate_pool)
        thread2 = await store2.get_thread("sess-r")
        return thread, wire, thread2

    thread, wire, thread2 = asyncio.run(scenario())
    # wire shape: 4 messages, tool_results merged into one user message
    assert [m["role"] for m in wire] == ["user", "assistant", "user", "assistant"]
    assert [b["tool_use_id"] for b in wire[2]["content"]] == ["tu_1", "tu_2"]
    # replay is byte-identical (canonical key order on both sides)
    assert json.dumps(wire) == json.dumps(thread2.messages())
    assert len(thread2.turns) == len(thread.turns)
    assert thread2.id == thread.id
    assert thread2.client_code == "X008593"


def test_assistant_tool_use_stored_as_own_turn_unmodified():
    async def scenario():
        pool = FakePool()
        store = ThreadStore(pool=pool)
        await store.start()
        thread = await _build_exchange(store, "sess-t")
        await store.close()
        return pool, thread

    pool, thread = asyncio.run(scenario())
    tool_use_turns = [t for t in thread.turns if t.kind == "assistant_tool_use"]
    assert len(tool_use_turns) == 1
    blocks = tool_use_turns[0].content
    assert [b["type"] for b in blocks] == ["text", "tool_use", "tool_use"]
    assert blocks[1]["input"] == {"fromDate": "2026-01-01", "segment": "EQ"}
    # its persisted row carries the same blocks and kind
    row = _turn_writes(pool)[1]
    assert row[3] == "assistant_tool_use"
    assert json.loads(row[4]) == blocks


def test_flow_event_persists_but_never_enters_the_transcript():
    async def scenario():
        pool = FakePool()
        store = ThreadStore(pool=pool)
        await store.start()
        thread = await store.get_thread("sess-f")
        store.append_turn(
            thread, role="user", kind="user_text", content=_text("hello")
        )
        store.append_turn(
            thread,
            role="user",
            kind="flow_event",
            content=[{"type": "flow_event"}],
            meta={"flow": "pnl", "action": "opened", "slots": {}},
        )
        await store.close()
        return pool, thread

    pool, thread = asyncio.run(scenario())
    assert len(thread.turns) == 2
    assert len(thread.messages()) == 1  # flow_event excluded from wire
    assert len(_turn_writes(pool)) == 2  # but persisted


# --- degraded persistence (3.3) ----------------------------------------------


def test_failing_pool_chat_unblocked_and_counter_increments(caplog):
    """DB/tunnel down: get_thread falls back to a fresh thread, appends
    succeed from memory, the writer drops the batch and counts it."""

    async def scenario():
        store = ThreadStore(pool=FailingPool())
        await store.start()
        thread = await store.get_thread("sess-down")  # rehydrate fails → fresh
        for i in range(5):
            store.append_turn(
                thread, role="user", kind="user_text",
                content=_text(f"secret message {i}"),
            )
        await store.close()  # writer attempts the batch, drops it
        return store, thread

    with caplog.at_level(logging.WARNING):
        store, thread = asyncio.run(scenario())
    assert len(thread.turns) == 5  # memory authoritative
    assert thread.messages()  # replay still works
    assert store.dropped_writes == 6  # 1 thread job + 5 turn jobs
    assert "secret message" not in caplog.text  # length/type-only logging
    assert "ConnectionError" in caplog.text


def test_full_queue_drops_with_length_only_log(caplog):
    async def scenario():
        store = ThreadStore(pool=FakePool(), queue_max=2)
        # writer intentionally NOT started → the queue can only fill
        thread = await store.get_thread("sess-q")  # job 1
        store.append_turn(
            thread, role="user", kind="user_text", content=_text("fits")
        )  # job 2
        store.append_turn(
            thread, role="user", kind="user_text",
            content=_text("PAN ABCDE1234F overflow"),
        )  # job 3 → dropped
        return store, thread

    with caplog.at_level(logging.WARNING):
        store, thread = asyncio.run(scenario())
    assert store.dropped_writes == 1
    assert len(thread.turns) == 2  # chat path unaffected: memory keeps both
    assert [t.seq for t in thread.turns] == [1, 2]  # seq already assigned
    assert "queue full" in caplog.text
    assert "ABCDE1234F" not in caplog.text


def test_memory_only_without_pool():
    async def scenario():
        store = ThreadStore(pool=None)
        await store.start()  # no writer task
        thread = await store.get_thread("sess-m")
        store.append_turn(
            thread, role="user", kind="user_text", content=_text("hi")
        )
        await store.close()
        return store, thread

    store, thread = asyncio.run(scenario())
    assert store._task is None
    assert store.dropped_writes == 0  # configured-off, not degraded
    assert len(thread.turns) == 1


# --- restart rehydration (3.2/3.5) -------------------------------------------


def test_restart_loses_at_most_the_in_flight_step():
    """Writer persisted all but the last enqueued turn when the process died:
    the rehydrated thread has n-1 turns and the next seq reuses the lost slot
    (no gaps, no collisions)."""

    async def scenario():
        pool = FakePool()
        store = ThreadStore(pool=pool)
        await store.start()
        thread = await _build_exchange(store, "sess-crash")  # 5 turns
        await store.close()
        rows = _rows_from_writes(pool, thread.id)
        assert len(rows) == 5
        crash_rows = rows[:-1]  # final assistant_text was in flight → lost

        store2 = ThreadStore(
            pool=FakePool(
                thread_row=_thread_row_from_writes(pool), turn_rows=crash_rows
            )
        )
        thread2 = await store2.get_thread("sess-crash")
        return thread, thread2, store2

    thread, thread2, store2 = asyncio.run(scenario())
    assert len(thread2.turns) == len(thread.turns) - 1  # lost exactly one
    assert thread2.next_seq == thread.turns[-1].seq  # reuses the lost slot
    # conversation continues: the lost step can simply be regenerated
    turn = store2.append_turn(
        thread2, role="assistant", kind="assistant_text",
        content=_text("regenerated"),
    )
    assert turn.seq == thread.turns[-1].seq
    # replayed prefix matches the original wire prefix byte-for-byte
    assert json.dumps(thread2.messages()[:3]) == json.dumps(thread.messages()[:3])


def test_cache_hit_never_touches_the_db():
    async def scenario():
        store = ThreadStore(pool=FailingPool())
        thread = await store.get_thread("sess-c")  # miss → failed rehydrate
        again = await store.get_thread("sess-c")  # hit → no DB call
        return thread, again

    thread, again = asyncio.run(scenario())
    assert again is thread


# --- prompt snapshots (3.4) --------------------------------------------------


def test_prompt_registration_hash_and_thread_link():
    tools = [{"name": "get_pnl", "input_schema": {"type": "object"}}]

    async def scenario():
        pool = FakePool()
        store = ThreadStore(pool=pool)
        await store.start()
        h1 = store.register_prompt("SYSTEM PROMPT", tools)
        h2 = store.register_prompt("SYSTEM PROMPT", tools)  # idempotent
        thread = await store.get_thread("sess-p")
        store.append_turn(
            thread, role="user", kind="user_text", content=_text("hi")
        )
        await store.close()
        return pool, store, h1, h2, thread

    pool, store, h1, h2, thread = asyncio.run(scenario())
    assert h1 == h2 == compute_prompt_hash("SYSTEM PROMPT", tools)
    assert len(h1) == 64  # sha256 hex
    assert h1 != compute_prompt_hash("OTHER PROMPT", tools)  # version change
    assert thread.prompt_hash == h1  # new threads record the active hash
    snapshot_writes = [
        (i, args) for i, (sql, args) in enumerate(pool.executed)
        if "prompt_snapshots" in sql
    ]
    assert len(snapshot_writes) == 1  # duplicate registration not re-enqueued
    idx, args = snapshot_writes[0]
    assert args[0] == h1 and args[1] == "SYSTEM PROMPT"
    thread_writes = [
        i for i, (sql, _) in enumerate(pool.executed) if "INSERT INTO threads" in sql
    ]
    assert idx < thread_writes[0]  # FIFO: snapshot lands before the thread row


def test_register_prompt_is_safe_before_start():
    async def scenario():
        pool = FakePool()
        store = ThreadStore(pool=pool)
        h = store.register_prompt("S", [])  # before start(): queue holds it
        await store.start()
        await store.close()
        return pool, h

    pool, h = asyncio.run(scenario())
    assert any("prompt_snapshots" in sql for sql, _ in pool.executed)


# --- lifespan wiring ---------------------------------------------------------


def test_app_lifespan_wires_store_memory_only(monkeypatch):
    monkeypatch.setattr("app.config.database_url", lambda: None)
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        store = app.state.conversation_store
        assert isinstance(store, ThreadStore)
        assert store._pool is None  # memory-only degraded mode
    # lifespan exit ran close() without error


# --- live integration (skipped without a reachable store DB) -----------------

LIVE_DSN = os.environ.get("DATABASE_URL")


@pytest.mark.skipif(not LIVE_DSN, reason="DATABASE_URL not set")
def test_live_round_trip_and_cleanup():
    import asyncpg

    from app import config

    session_id = f"pytest-{uuid.uuid4()}"

    async def scenario():
        pool = await asyncpg.create_pool(
            config.database_url(), min_size=0, max_size=2, timeout=8
        )
        try:
            store = ThreadStore(pool=pool)
            await store.start()
            prompt_hash = store.register_prompt(
                "pytest system", [{"name": "kb_search"}]
            )
            thread = await _build_exchange(store, session_id)
            wire = thread.messages()
            await store.close()  # drain to Postgres

            store2 = ThreadStore(pool=pool)  # fresh cache = restart
            thread2 = await store2.get_thread(session_id)
            assert thread2.prompt_hash == prompt_hash
            assert len(thread2.turns) == 5
            assert json.dumps(thread2.messages()) == json.dumps(wire)
            row = await pool.fetchrow(
                "SELECT system FROM prompt_snapshots WHERE hash = $1", prompt_hash
            )
            assert row["system"] == "pytest system"
        finally:
            await pool.execute(
                "DELETE FROM threads WHERE session_id = $1", session_id
            )  # turns cascade
            await pool.execute(
                "DELETE FROM prompt_snapshots WHERE system = 'pytest system'"
            )
            await pool.close()

    asyncio.run(scenario())
