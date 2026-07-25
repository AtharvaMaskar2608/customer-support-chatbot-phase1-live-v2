# support-escalation

## MODIFIED Requirements

### Requirement: Tickets clone the established chatbot-testing contract
Every bot-raised Freshdesk ticket SHALL be created in the chatbot-testing group with the parameter set established by the existing prototype tickets: subject `[Choice Jini] <reason> — Client <code>`; status Open (2); priority Medium (2); source Chat (7); type `GENERAL QUERY`; tags `choice-jini`, `chatbot-testing`, `lang:en`; custom fields `cf_client_id` (the client code), `cf_source` `"chat box"`, `cf_product` `"finx"`, `cf_query_type149508` `"finx-bot"`, `cf_query_sub_type` `"finx-bot-test"`. The requester SHALL be identified by client code (`unique_external_id` + `name`) AND, so support can contact the client, by the client's email and phone number — fetched server-side from the Profile API and sent in the ticket's `email` and `phone` fields. The profile fetch SHALL be best-effort: if the profile or a field is unavailable, the ticket is still created with whatever identity fields are present (client code always). Profile email/phone SHALL be used only for the ticket requester fields — never logged, never stored in the conversation. Credentials (domain, API key) SHALL come from server-side config only, never logged, never in tool schemas, never stored in the conversation.

#### Scenario: Ticket parameters match the contract
- **WHEN** any bot ticket is created for client X008593 with reason "General Query" and the profile provides email and phone
- **THEN** the Freshdesk payload carries exactly the group id, status/priority/source/type, tags, and custom-field values above, with the client code as requester identity plus the client's email and phone in the requester `email` and `phone` fields

#### Scenario: Profile unavailable still raises the ticket
- **WHEN** the Profile API is unreachable or returns no email/phone while a ticket is raised
- **THEN** the ticket is still created, identified by client code, without the email/phone fields, and the failure is not surfaced to the user
