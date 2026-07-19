# CHO-218 · Freshdesk Escalation — Design

## D1 · The parameter contract is cloned, not invented

Live tickets #7539459/#7529083 in the chatbot-testing group (created by the earlier prototype) define the contract; we reproduce it byte-for-byte so every bot ticket looks identical in the support queue:

```json
POST {FRESHDESK_API_ROOT}/tickets       (basic auth: API key + "X")
{
  "subject": "[Choice Jini] <reason> — Client <code>",
  "description": "<html: metadata block + transcript>",
  "unique_external_id": "<client code>", "name": "<client code>",
  "status": 2, "priority": 2, "source": 7, "type": "GENERAL QUERY",
  "group_id": 22000168676,
  "tags": ["choice-jini", "chatbot-testing", "lang:en"],
  "custom_fields": {
    "cf_client_id": "<code>", "cf_source": "chat box", "cf_product": "finx",
    "cf_query_type149508": "finx-bot", "cf_query_sub_type": "finx-bot-test"
  }
}
```

Requester identity: client code via `unique_external_id` + `name` — matching the existing tickets (requester shows the code, email `None`). No email/phone leaves our system. If the live test ticket reveals the instance rejects external-id-only contacts, fallback is the prototype's placeholder-phone pattern — decided by the one sanctioned test ticket, never silently.

The group id and field values live as code constants beside a single `FRESHDESK_GROUP_ID`-style env override set (switching to a production group later = config, not code).

## D2 · Transcript rendering

From `thread.turns`, include only `user_text`, `assistant_text` (text blocks joined), and `flow_event` memos — never `assistant_tool_use`/`tool_result` (tool internals are noise to a support agent and the envelope JSON is not for humans). Rendered as simple HTML: a metadata table (client id, reason, raised at, "Turns included: N of M"), then alternating `<b>Client:</b>` / `<b>Jini:</b>` paragraphs, app events italicized. Hard cap ~100 turns / ~60KB, truncating oldest-first with the note. Store content is credential-clean by construction (CHO-213 invariant), so no extra redaction pass is needed — asserted by a test that scans rendered output for header values anyway.

## D3 · Two entry points, one core

- **Agent tool `raise_support_ticket`**: schema exposes only `reason` (short string, required). The model calls it when the user asks for a human or accepts the escalation offer. Success envelope `{kind:"ticket", ticketId, status:"Open"}` → the loop emits `artifact {kind:"ticket", ticketId, status}` — an artifact-producing tool, so the CHO-215 short-circuit applies (card is the answer, no narration call). The tool's success is a resolution event (caps reset) by construction.
- **`POST /api/ticket`**: same auth headers; body `{reason?}` (defaults to "General Query" — the help-card path has no free text). Returns `{ticketId, status}`; the shell's help-card action calls it and renders the existing TicketCard with the real id. `makeTicketId` is deleted.

Both paths append a flow-event memo ("[App event] Support ticket #N raised — <reason>.") so follow-ups like "did you raise that ticket?" answer correctly, and double-raising is visible to the model.

## D4 · Failure posture

Freshdesk timeout/4xx/5xx → `ToolError(UPSTREAM_ERROR, "couldn't reach support system — suggest the app's Help section")` for the tool path (the model narrates and offers alternatives; errored rounds still narrate per CHO-215) and a plain error JSON for the endpoint path (shell shows the graceful line, help card stays actionable). Never a stub id, never a fake success. Timeout 10s. Rate limits are irrelevant at our volume but 429 maps to the same error.

## D5 · What deliberately stays out

Status lookup ("where's my ticket #N") — separate change with its own tool; attachments; requester enrichment (email/phone from Get Profile) — revisit when support asks for callback data; production group routing — env flip when the team is ready.
