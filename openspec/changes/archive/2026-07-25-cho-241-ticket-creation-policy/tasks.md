# CHO-241: ticket-creation-policy — tasks

## 1. Prompt policy

- [ ] 1.1 In `backend/app/agent/prompt.py`, add the ticket-creation policy: offer, never decide; call `raise_support_ticket` only on an explicit escalation request or accepted offer; never announce "let me raise a ticket"; ask "Want me to raise a ticket…?" and stop; offer at most once per issue; never offer while refusing (security / other data / policy); never narrate retrieval
- [ ] 1.2 In `backend/app/agent/tools.py`, tighten the `raise_support_ticket` description to match the policy
- [ ] 1.3 Add a few-shot example: a ticket-worthy situation → the bot OFFERS and stops (no tool call)

## 2. Server-side guard (hardening)

- [ ] 2.1 In the dispatcher (`backend/app/agent/tools.py` dispatch, or `loop.py`), gate `raise_support_ticket`: reject unless the triggering user turn is an explicit escalation request (conservative allowlist) or an affirmative acceptance of the assistant's immediately-preceding escalation offer
- [ ] 2.2 A rejected call returns an error `tool_result` (model offers instead); no ticket is created; the help-card `POST /api/ticket` path is unaffected

## 3. Verification

- [ ] 3.1 `cd backend && uv run pytest` green — a preemptive `raise_support_ticket` is rejected (no ticket); an explicit request goes through; `POST /api/ticket` still raises
- [ ] 3.2 Manual: a factual query never produces a ticket; "connect me to a human" does

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-241
- [ ] 4.2 `linear-connector` — summary comment + state on merge
