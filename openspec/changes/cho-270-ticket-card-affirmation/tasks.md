# CHO-270: ticket-card-affirmation — tasks

## 1. Guard recovery (`tickets.py`)

- [x] 1.1 Expand escalation-invite markers to include gerund / announce forms (`raising a ticket`, `raising a support ticket`, `let me raise`, …) while keeping existing offer phrases
- [x] 1.2 Affirmative path: match markers across consecutive assistant turns since the previous user message (not only the immediately preceding bubble)

## 2. Prompt

- [x] 2.1 Harden TICKET POLICY: never claim a ticket is being/was raised unless `raise_support_ticket` just ran; card is the confirmation

## 3. Default model (Sonnet 4.6, thinking off)

- [x] 3.1 Set `AGENT_MODEL_DEFAULT` to `claude-sonnet-4-6`; keep `AGENT_THINKING` default `off`
- [x] 3.2 Update config/loop tests, main `agent-loop` spec, `.env.example`, traces FilterBar model order

## 4. Spec + tests (ticket guard)

- [x] 4.1 OpenSpec `agent-loop` delta: affirmative recovery after announce/raise narration
- [x] 4.2 Unit tests: screenshot path (announce → “I’m raising…” → `Ok` → allowed); plain `yes` with no escalate context still blocked; proper offer still allowed

## 5. Verify & ship

- [x] 5.1 `cd backend && uv run pytest tests/test_agent_tickets.py tests/test_agent_config.py tests/test_agent_loop.py -q`
- [x] 5.2 Push branch + draft PR (`Fixes CHO-270`) — https://github.com/AtharvaMaskar2608/customer-support-chatbot-phase1-live-v2/pull/68
- [ ] 5.3 Linear summary when MCP/API available (blocked in this cloud run)
