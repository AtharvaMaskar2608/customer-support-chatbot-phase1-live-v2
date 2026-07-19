"""Conversation store (CHO-213 · design D6/D7).

In-memory authoritative thread cache + wire-faithful Postgres persistence
through a bounded queue and ONE long-lived writer task. The chat path never
awaits a database write: `append_turn` assigns `seq` synchronously and
`put_nowait`s the row; the DB is read only on a cache miss (rehydrate after
restart). With no pool (no DATABASE_URL) the store runs memory-only.

Public API consumed by the agent loop (wave B):

    store = ThreadStore(pool=app.state.pg_pool)   # built in lifespan
    await store.start()                           # after pool creation
    h = store.register_prompt(system_text, tools_json)  # sha256, lazy upsert
    thread = await store.get_thread(session_id, client_code=...)
    store.append_turn(thread, role=..., kind=..., content=[...], meta={...})
    thread.messages()                             # wire-faithful messages array
    store.set_status(thread, "escalated")
    store.dropped_writes                          # degraded-persistence metric
    await store.close()                           # drain, before pool close

Content hygiene: `content`/`meta` must never carry credentials or raw
upstream bodies (tool results are the normalized envelopes); logs from this
module carry counts and exception type names only — never turn content.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

ROLES = ("user", "assistant")
KINDS = (
    "user_text",
    "assistant_text",
    "assistant_tool_use",
    "tool_result",
    "flow_event",
)
THREAD_STATUSES = ("active", "resolved", "escalated", "expired")

QUEUE_MAX = 1000  # bounded: a wedged tunnel degrades persistence, not chat
_BATCH_MAX = 50  # jobs drained per writer wake-up over one connection
_DRAIN_TIMEOUT_SECONDS = 10.0
_SHUTDOWN = object()

_SNAPSHOT_SQL = """
INSERT INTO prompt_snapshots (hash, system, tools)
VALUES ($1, $2, $3::jsonb)
ON CONFLICT (hash) DO NOTHING
"""

# Threads are upserted (not inserted once) so every turn write refreshes
# last_active_at/status and self-heals a thread row lost while the DB was down.
_THREAD_SQL = """
INSERT INTO threads
    (id, session_id, client_code, status, prompt_hash, created_at, last_active_at)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (id) DO UPDATE
    SET status = EXCLUDED.status, last_active_at = EXCLUDED.last_active_at
"""

_TURN_SQL = """
INSERT INTO turns (thread_id, seq, role, kind, content, meta, created_at)
VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
ON CONFLICT (thread_id, seq) DO NOTHING
"""

_SELECT_THREAD_SQL = """
SELECT id, session_id, client_code, status, prompt_hash, created_at, last_active_at
FROM threads
WHERE session_id = $1
"""

_SELECT_TURNS_SQL = """
SELECT seq, role, kind, content, meta, created_at
FROM turns
WHERE thread_id = $1
ORDER BY seq
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(obj: Any) -> Any:
    """Recursively sort dict keys. jsonb does not preserve key order, so the
    store canonicalizes at BOTH write and read time — memory, wire, and DB
    then agree byte-for-byte, which keeps replay byte-identical across
    restarts (and Anthropic prompt caching warm)."""
    if isinstance(obj, dict):
        return {key: _canonical(obj[key]) for key in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [_canonical(item) for item in obj]
    return obj


def _loads(value: Any) -> Any:
    """asyncpg returns jsonb as text unless a codec is registered."""
    return json.loads(value) if isinstance(value, str) else value


def compute_prompt_hash(system_text: str, tools_json: Any) -> str:
    """sha256 over the system text + canonical tool-schema JSON."""
    tools_str = json.dumps(
        _canonical(tools_json), sort_keys=True, separators=(",", ":")
    )
    payload = system_text + "\x00" + tools_str
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class Turn:
    """One step boundary; `content` is the exact Anthropic content-block
    array (canonical key order), `meta` per-kind telemetry (design D6)."""

    seq: int
    role: str
    kind: str
    content: list[dict[str, Any]]
    meta: dict[str, Any]
    created_at: datetime


@dataclass
class Thread:
    """One widget session. Turns are authoritative; the messages array and
    all counters are derived from them — never stored."""

    id: str  # app-generated uuid4 (no DB round-trip on the chat path)
    session_id: str
    client_code: str | None = None
    prompt_hash: str | None = None
    status: str = "active"
    created_at: datetime = field(default_factory=_now)
    last_active_at: datetime = field(default_factory=_now)
    turns: list[Turn] = field(default_factory=list)

    @property
    def next_seq(self) -> int:
        return self.turns[-1].seq + 1 if self.turns else 1

    def messages(self) -> list[dict[str, Any]]:
        """Rebuild the wire-faithful Anthropic messages array. Consecutive
        tool_result turns merge into ONE user-role message (that is how they
        went over the wire after a parallel-tool assistant turn); flow_event
        turns are store-only and never enter the model transcript."""
        messages: list[dict[str, Any]] = []
        last_kind: str | None = None
        for turn in self.turns:
            if turn.kind == "flow_event":
                continue
            if turn.kind == "tool_result" and last_kind == "tool_result":
                messages[-1]["content"].extend(turn.content)
            else:
                messages.append({"role": turn.role, "content": list(turn.content)})
            last_kind = turn.kind
        return messages


class ThreadStore:
    """In-memory thread cache (keyed by session_id) + single-writer async
    persistence over the shared asyncpg pool (design D7)."""

    def __init__(self, pool: Any | None = None, *, queue_max: int = QUEUE_MAX):
        self._pool = pool
        self._threads: dict[str, Thread] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_max)
        self._task: asyncio.Task | None = None
        self._prompts: dict[str, tuple[str, str]] = {}  # hash -> (system, tools)
        self._current_prompt_hash: str | None = None
        self.dropped_writes = 0

    # --- lifecycle (called from app lifespan) --------------------------------

    async def start(self) -> None:
        """Start the single writer task. No-op memory-only when there is no
        pool (no DATABASE_URL) — chat works, persistence is off."""
        if self._pool is None:
            logger.info("conversation store: no DB pool, running memory-only")
            return
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(
                self._writer_loop(), name="conversation-store-writer"
            )

    async def close(self) -> None:
        """Graceful drain: everything enqueued before close() is written
        (FIFO ahead of the sentinel), then the writer exits. Call BEFORE
        closing the pool."""
        if self._task is None:
            return
        await self._queue.put(_SHUTDOWN)
        try:
            await asyncio.wait_for(self._task, timeout=_DRAIN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            self._task.cancel()
            logger.warning(
                "conversation store: drain timed out with %d writes queued",
                self._queue.qsize(),
            )
        self._task = None

    # --- prompt snapshots (task 3.4) -----------------------------------------

    def register_prompt(self, system_text: str, tools_json: Any) -> str:
        """Hash the active prompt (system + tool schemas), lazily upsert the
        snapshot row, and make new threads record this hash. Idempotent and
        lifespan-safe: callable before start() (the queue holds the upsert)
        and re-callable per request at no cost."""
        prompt_hash = compute_prompt_hash(system_text, tools_json)
        if prompt_hash not in self._prompts:
            tools_str = json.dumps(
                _canonical(tools_json), sort_keys=True, separators=(",", ":")
            )
            self._prompts[prompt_hash] = (system_text, tools_str)
            self._enqueue(("snapshot", prompt_hash))
        self._current_prompt_hash = prompt_hash
        return prompt_hash

    # --- hot path -------------------------------------------------------------

    async def get_thread(
        self, session_id: str, *, client_code: str | None = None
    ) -> Thread:
        """Cache hit → return; miss → rehydrate from DB; nothing persisted →
        new thread recording the current prompt hash."""
        thread = self._threads.get(session_id)
        if thread is not None:
            return thread
        thread = await self._rehydrate(session_id)
        # A concurrent request may have won the miss race during the await.
        existing = self._threads.get(session_id)
        if existing is not None:
            return existing
        if thread is None:
            thread = Thread(
                id=str(uuid.uuid4()),
                session_id=session_id,
                client_code=client_code,
                prompt_hash=self._current_prompt_hash,
            )
            self._enqueue(("thread", self._thread_row(thread)))
        self._threads[session_id] = thread
        return thread

    def append_turn(
        self,
        thread: Thread,
        *,
        role: str,
        kind: str,
        content: list[dict[str, Any]],
        meta: dict[str, Any] | None = None,
    ) -> Turn:
        """Synchronous: seq is assigned and the write enqueued with no await
        point in between, so wire order IS persistence order."""
        if role not in ROLES:
            raise ValueError(f"invalid role: {role!r}")
        if kind not in KINDS:
            raise ValueError(f"invalid kind: {kind!r}")
        turn = Turn(
            seq=thread.next_seq,
            role=role,
            kind=kind,
            content=_canonical(content),
            meta=_canonical(meta or {}),
            created_at=_now(),
        )
        thread.turns.append(turn)
        thread.last_active_at = turn.created_at
        self._enqueue(("turn", self._thread_row(thread), self._turn_row(thread, turn)))
        return turn

    def set_status(self, thread: Thread, status: str) -> None:
        if status not in THREAD_STATUSES:
            raise ValueError(f"invalid thread status: {status!r}")
        thread.status = status
        thread.last_active_at = _now()
        self._enqueue(("thread", self._thread_row(thread)))

    # --- enqueue (never blocks, never raises into chat) ------------------------

    def _enqueue(self, job: tuple) -> None:
        if self._pool is None:
            return  # memory-only mode (logged once at start)
        try:
            self._queue.put_nowait(job)
        except asyncio.QueueFull:
            self.dropped_writes += 1
            # Length-only: never log turn content or user text.
            logger.warning(
                "conversation store: queue full (size=%d), write dropped (total=%d)",
                self._queue.qsize(),
                self.dropped_writes,
            )

    # --- rehydration (DB read, cache miss only) --------------------------------

    async def _rehydrate(self, session_id: str) -> Thread | None:
        if self._pool is None:
            return None
        try:
            row = await self._pool.fetchrow(_SELECT_THREAD_SQL, session_id)
            if row is None:
                return None
            turn_rows = await self._pool.fetch(_SELECT_TURNS_SQL, row["id"])
        except Exception as exc:
            logger.warning(
                "conversation store: rehydrate failed (%s), starting fresh thread",
                type(exc).__name__,
            )
            return None
        thread = Thread(
            id=str(row["id"]),
            session_id=row["session_id"],
            client_code=row["client_code"],
            prompt_hash=row["prompt_hash"],
            status=row["status"],
            created_at=row["created_at"],
            last_active_at=row["last_active_at"],
        )
        for turn_row in turn_rows:
            thread.turns.append(
                Turn(
                    seq=turn_row["seq"],
                    role=turn_row["role"],
                    kind=turn_row["kind"],
                    content=_canonical(_loads(turn_row["content"])),
                    meta=_canonical(_loads(turn_row["meta"])),
                    created_at=turn_row["created_at"],
                )
            )
        return thread

    # --- single writer ----------------------------------------------------------

    async def _writer_loop(self) -> None:
        while True:
            job = await self._queue.get()
            jobs = [job]
            while len(jobs) < _BATCH_MAX:
                try:
                    jobs.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            stop = any(j is _SHUTDOWN for j in jobs)
            jobs = [j for j in jobs if j is not _SHUTDOWN]
            if jobs:
                await self._write_batch(jobs)
            if stop:
                return

    async def _write_batch(self, jobs: list[tuple]) -> None:
        try:
            async with self._pool.acquire() as conn:
                for job in jobs:
                    try:
                        await self._apply(conn, job)
                    except Exception as exc:
                        self.dropped_writes += 1
                        logger.warning(
                            "conversation store: %s write failed (%s), dropped (total=%d)",
                            job[0],
                            type(exc).__name__,
                            self.dropped_writes,
                        )
        except Exception as exc:
            # acquire() failed — DB/tunnel down; the whole batch is dropped.
            self.dropped_writes += len(jobs)
            logger.warning(
                "conversation store: batch of %d dropped (%s, total=%d)",
                len(jobs),
                type(exc).__name__,
                self.dropped_writes,
            )

    async def _apply(self, conn: Any, job: tuple) -> None:
        kind = job[0]
        if kind == "snapshot":
            prompt_hash = job[1]
            system_text, tools_str = self._prompts[prompt_hash]
            await conn.execute(_SNAPSHOT_SQL, prompt_hash, system_text, tools_str)
        elif kind == "thread":
            await self._upsert_thread(conn, job[1])
        elif kind == "turn":
            _, thread_row, turn_row = job
            await self._upsert_thread(conn, thread_row)
            await conn.execute(
                _TURN_SQL,
                turn_row["thread_id"],
                turn_row["seq"],
                turn_row["role"],
                turn_row["kind"],
                turn_row["content"],
                turn_row["meta"],
                turn_row["created_at"],
            )
        else:  # pragma: no cover — enqueue only produces the kinds above
            raise ValueError(f"unknown store job kind: {kind!r}")

    async def _upsert_thread(self, conn: Any, row: dict[str, Any]) -> None:
        args = (
            row["id"],
            row["session_id"],
            row["client_code"],
            row["status"],
            row["prompt_hash"],
            row["created_at"],
            row["last_active_at"],
        )
        try:
            await conn.execute(_THREAD_SQL, *args)
        except asyncpg.ForeignKeyViolationError:
            # The snapshot row this thread references was lost (e.g. dropped
            # while the DB was down). Re-upsert it from memory and retry once.
            prompt = self._prompts.get(row["prompt_hash"])
            if prompt is None:
                raise
            await conn.execute(_SNAPSHOT_SQL, row["prompt_hash"], prompt[0], prompt[1])
            await conn.execute(_THREAD_SQL, *args)

    # --- row snapshots (taken at enqueue time; immune to later mutation) --------

    @staticmethod
    def _thread_row(thread: Thread) -> dict[str, Any]:
        return {
            "id": thread.id,
            "session_id": thread.session_id,
            "client_code": thread.client_code,
            "status": thread.status,
            "prompt_hash": thread.prompt_hash,
            "created_at": thread.created_at,
            "last_active_at": thread.last_active_at,
        }

    @staticmethod
    def _turn_row(thread: Thread, turn: Turn) -> dict[str, Any]:
        return {
            "thread_id": thread.id,
            "seq": turn.seq,
            "role": turn.role,
            "kind": turn.kind,
            "content": json.dumps(turn.content, separators=(",", ":")),
            "meta": json.dumps(turn.meta, separators=(",", ":")),
            "created_at": turn.created_at,
        }
