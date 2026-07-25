# agent-loop

## ADDED Requirements

### Requirement: Deterministic key-facts recitation block
A model request MAY carry a **key-facts recitation block** that SHALL restate the conversation's
established facts so they sit adjacent to the generation point rather than buried in history. The block
SHALL be server-rendered and deterministic — built only from structure already in the thread
(`flow_event` turns' structured slots, the latest report-form seed, and any open request the user has
made that is not yet satisfied) — with **no model call and no summarizer**, so the same thread state
always renders the same bytes.

The block SHALL be positioned **after all conversation history**, in the trailing region already used
by the escalation and wrap-up reminders, so it sits after every prompt-cache breakpoint and can never
invalidate a cached prefix; every message before it SHALL be byte-identical to the request that would
have been sent without it. The block SHALL be framed as app-generated data rather than user prose, and
SHALL never be stored on the thread.

Its content SHALL be limited to flow names, customer-facing slot labels, ISO dates and short
open-request summaries — never currency amounts, credentials, file tokens, masked contact values or
upstream fields. The block SHALL be omitted entirely when there is nothing to recite.

#### Scenario: Block lists a prior completed form's slots
- **WHEN** the user completed a ledger form earlier in the thread and several turns have followed
- **THEN** the request carries a trailing recitation block naming the ledger flow with its slot labels and ISO dates, and the model can act on those values without re-asking for them

#### Scenario: Block is absent on a fresh thread
- **WHEN** a thread's first message is sent and there are no flow events and no open request
- **THEN** no recitation block is added and the request is byte-identical to the request that would be sent without this feature

#### Scenario: Placement does not alter the cached prefix
- **WHEN** a request is assembled with the recitation block present
- **THEN** every message before the trailing block is byte-identical to the same request assembled without it, so the cached prefix is unchanged

#### Scenario: Recitation is app data, never model-authored
- **WHEN** the block is rendered twice for the same thread state
- **THEN** the bytes are identical, no model call was made to produce them, and the block is framed as app-generated context rather than as something the user typed
