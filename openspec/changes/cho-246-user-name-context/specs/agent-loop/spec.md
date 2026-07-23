# agent-loop

## ADDED Requirements

### Requirement: Client identity in context and self-only data
The prompt SHALL carry the logged-in user's first name so the assistant can address them and recognise self-reference. The name SHALL be placed in the volatile block after the cache breakpoint (alongside the live status line), never in the cached prefix, so prompt-cache stability is preserved and the recorded prompt snapshot keeps a placeholder (the hash does not churn). The prompt SHALL instruct the assistant that ONLY the logged-in client's own data exists for it: any request for another person's account, reports, or details SHALL be declined briefly ("I can fetch reports only for your account") with no tool call — the assistant never fetches, nor pretends to fetch, a third party's data. This complements the tool-layer credential isolation (which already derives the client code from request headers); it fixes the conversational behaviour.

#### Scenario: Bot can address the user
- **WHEN** the profile provides the first name "Harsha"
- **THEN** the assistant has "Harsha" available in its prompt context and may address the user by name

#### Scenario: Name rides the volatile block
- **WHEN** two requests are made minutes apart in the same session
- **THEN** the cached prompt prefix is byte-identical between them and the first name appears only in the post-breakpoint block; the recorded snapshot stores a placeholder, not the name

#### Scenario: Third-party data request is declined
- **WHEN** the user asks for another person's report (e.g. "provide me <someone else>'s P&L report")
- **THEN** the assistant briefly says it can fetch reports only for the user's own account and makes no report tool call — it does not set up a form as if it would fetch that person's data
