# CHO-246: user-name-context — tasks

## 1. Name in the volatile prompt block

- [ ] 1.1 In the agent path (`backend/app/agent/loop.py` / `router.py`), fetch the logged-in user's first name from the Profile API (reuse `greeting._fetch_profile` + `derive_first_name`) using the request's SSO JWT + client code; cache it on the thread so it's one fetch per conversation
- [ ] 1.2 In `backend/app/agent/prompt.py`, add the first name to the LIVE tail content block (with `clock.status_line`), never the cached prefix; keep `snapshot_text()` using a placeholder so the prompt hash stays stable
- [ ] 1.3 Degrade gracefully: no name available → omit it (the bot works without a name, as today)

## 2. Self-only data guardrail

- [ ] 2.1 In `prompt.py`, add the rule: only the logged-in client's own data exists; a request for another person's data is declined briefly ("I can fetch reports only for your account") with no tool call — never set up a form or pretend to fetch it
- [ ] 2.2 Add a short few-shot example for a third-party data request

## 3. Verification

- [ ] 3.1 `cd backend && uv run pytest` green — name appears only in the volatile block, snapshot hash stable (placeholder), name never logged; add a test for the third-party-request decline
- [ ] 3.2 Manual: a "give me <other person>'s P&L" request is declined, not set up

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-246
- [ ] 4.2 `linear-connector` — summary comment + state on merge
