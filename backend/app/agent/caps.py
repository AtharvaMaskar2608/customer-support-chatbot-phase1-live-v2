"""Conversation caps (CHO-213 · task 4.4, design D5).

Counters are DERIVED from the thread's turns on every evaluation — never
stored. Definitions:

  resolution event    a tool_result turn with meta.is_error == False (the
                      assistant turn it answers "ended with ≥1 successful
                      tool call"). It resets the per-task counters.
  task window         all turns after the last resolution event.
  clarifying question an assistant_text turn (an exchange with no tool use —
                      tool exchanges are kind assistant_tool_use) whose last
                      text contains a question mark (see _asks_question).

Caps (env-configurable, read at call time via app.config):
  clarify_cap()       max clarifying questions per task window
  task_turn_cap()     max user turns per task window
  session_turn_cap()  max user turns per session (the dumb backstop that
                      catches the KB-rephrase loop, where every "successful"
                      answer resets the task window)

On any trip the LOOP appends an escalation instruction to the END of the
messages array for the model call (prompt-cache-safe: the system prompt is
never edited) so the reply offers escalation to a human naturally.
"""

from dataclasses import dataclass

from app import config
from app.agent.store import Thread, Turn

CAP_CLARIFY = "clarify"
CAP_TASK_TURNS = "task_turns"
CAP_SESSION_TURNS = "session_turns"


@dataclass
class CapCounters:
    clarify_questions: int
    task_user_turns: int
    session_user_turns: int
    tripped: tuple[str, ...]


def _is_resolution(turn: Turn) -> bool:
    return turn.kind == "tool_result" and turn.meta.get("is_error") is False


def _asks_question(turn: Turn) -> bool:
    """A clarifying reply contains a question anywhere in its text — live
    models routinely END such replies with a reassurance statement ("Once you
    let me know, I'll generate it right away."), so an endswith("?") check
    undercounts. Tool-bearing exchanges never reach here (kind filter), so a
    mid-text "?" is a reliable clarify signal."""
    return any(
        "?" in str(block.get("text", ""))
        for block in turn.content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def evaluate(thread: Thread) -> CapCounters:
    """Derive the counters and which caps are tripped, per design D5.

    Called once per incoming user message, AFTER the user_text turn is
    appended — so the current message counts toward the turn caps.
    """
    turns = thread.turns
    boundary = 0
    for index, turn in enumerate(turns):
        if _is_resolution(turn):
            boundary = index + 1
    window = turns[boundary:]

    clarify = sum(
        1
        for turn in window
        if turn.kind == "assistant_text" and _asks_question(turn)
    )
    task_user = sum(1 for turn in window if turn.kind == "user_text")
    session_user = sum(1 for turn in turns if turn.kind == "user_text")

    tripped: list[str] = []
    if clarify >= config.clarify_cap():
        tripped.append(CAP_CLARIFY)
    if task_user >= config.task_turn_cap():
        tripped.append(CAP_TASK_TURNS)
    if session_user >= config.session_turn_cap():
        tripped.append(CAP_SESSION_TURNS)
    return CapCounters(
        clarify_questions=clarify,
        task_user_turns=task_user,
        session_user_turns=session_user,
        tripped=tuple(tripped),
    )
