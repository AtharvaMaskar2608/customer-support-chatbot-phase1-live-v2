# CHO-270: ticket-card-affirmation — tasks

## 1. Guard recovery (`tickets.py`)

- [x] 1.1 Expand escalation-invite markers to include gerund / announce forms (`raising a ticket`, `raising a support ticket`, `let me raise`, …) while keeping existing offer phrases
- [x] 1.2 Affirmative path: match markers across consecutive assistant turns since the previous user message (not only the immediately preceding bubble)

## 2. Prompt

- [x] 2.1 Harden TICKET POLICY: never claim a ticket is being/was raised unless `raise_support_ticket` just ran; card is the confirmation

## 3. Spec + tests

- [x] 3.1 OpenSpec `agent-loop` delta: affirmative recovery after announce/raise narration
- [x] 3.2 Unit tests: screenshot path (announce → “I’m raising…” → `Ok` → allowed); plain `yes` with no escalate context still blocked; proper offer still allowed

## 4. Verify & ship

- [x] 4.1 `cd backend && uv run pytest tests/test_agent_tickets.py -q`
- [ ] 4.2 Push branch + draft PR (`Fixes CHO-270`)
