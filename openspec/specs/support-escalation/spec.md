# support-escalation Specification

## Purpose
TBD - created by archiving change cho-218-freshdesk-escalation. Update Purpose after archive.
## Requirements
### Requirement: Tickets clone the established chatbot-testing contract
Every bot-raised Freshdesk ticket SHALL be created in the chatbot-testing group with the parameter set established by the existing prototype tickets: subject `[Choice Jini] <reason> — Client <code>`; status Open (2); priority Medium (2); source Chat (7); type `GENERAL QUERY`; tags `choice-jini`, `chatbot-testing`, `lang:en`; custom fields `cf_client_id` (the client code), `cf_source` `"chat box"`, `cf_product` `"finx"`, `cf_query_type149508` `"finx-bot"`, `cf_query_sub_type` `"finx-bot-test"`. The requester SHALL be identified by client code only — no email or phone number SHALL be sent. Credentials (domain, API key) SHALL come from server-side config only, never logged, never in tool schemas, never stored in the conversation.

#### Scenario: Ticket parameters match the contract
- **WHEN** any bot ticket is created for client X008593 with reason "General Query"
- **THEN** the Freshdesk payload carries exactly the group id, status/priority/source/type, tags, and custom-field values above, with the client code as requester identity and no email/phone fields

### Requirement: The conversation travels in the ticket
The ticket description SHALL contain a metadata block (client id, reason, raised-at timestamp, turns included of total) followed by the conversation transcript rendered as readable HTML — user messages, assistant text replies, and app-event memos only; tool-use blocks and tool-result envelopes SHALL never appear. Transcripts SHALL truncate oldest-first beyond a size cap, stating how many turns are shown. Rendered output SHALL contain no credentials (asserted against the request's header values).

#### Scenario: Transcript contents
- **WHEN** a ticket is raised after a conversation with a KB answer and a completed report form
- **THEN** the description shows the user/bot exchange and the form's app-event note, and contains no tool names, JSON envelopes, session ids, or tokens

### Requirement: Escalation entry points share one core
The backend SHALL expose the ticket core through two entry points that produce identical tickets: (1) a `raise_support_ticket` agent tool whose input schema carries only `reason`, emitted to the shell as a `ticket` artifact (`ticketId`, `status`) on success; and (2) `POST /api/ticket` (same auth-header validation as `/api/chat`; optional `reason` defaulting to "General Query") returning `{ticketId, status}` for the help card. On success both paths SHALL append a flow-event memo recording the ticket id so the conversation remembers the escalation. On Freshdesk failure the tool SHALL return an error tool_result (the model explains and suggests alternatives) and the endpoint a plain error response — never a fabricated ticket id.

#### Scenario: Agent raises a ticket on request
- **WHEN** the user says "just connect me to a person" and the model calls `raise_support_ticket`
- **THEN** a real ticket is created, a `ticket` artifact carries its id, no narration call follows (artifact-only round), and a flow-event memo lands in the thread

#### Scenario: Help card raises a real ticket
- **WHEN** the user taps "Raise a ticket" on a help card
- **THEN** `/api/ticket` creates the ticket and the confirmation card shows the real Freshdesk id — stub ids no longer exist

#### Scenario: Freshdesk down
- **WHEN** the Freshdesk API times out
- **THEN** the user gets a plain-language explanation with alternative support routes, and no ticket id is shown

