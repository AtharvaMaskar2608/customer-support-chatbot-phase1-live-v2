## MODIFIED Requirements

### Requirement: Isolated operator web page
The dashboard UI SHALL be a Vite entry separate from the chat app and the corner
widget (`traces.html` with its own React root), so it shares no runtime state
with the customer-facing surfaces. It SHALL gate on the admin token (prompted,
stored in localStorage, sent as `X-Traces-Token` on every fetch) and show a
clear disabled/unauthorized state on 404/401. It SHALL render the nested span
tree with per-span type, name, duration and key metadata (llm: model + token
split; tool: error flag; retriever: chunk count + embedder) and, when a
retriever span is expanded, the stored `metadata.retrieval_context` chunk
texts. It SHALL also render a hand-rolled token-trend gauge for a selected
thread, without adding a chart or router dependency. The production build
SHALL emit `dist/traces.html`.

#### Scenario: Nested graph and token trend render
- **WHEN** the operator opens a trace and a thread
- **THEN** the trace shows the nested agent/llm/tool/retriever span tree with per-span metadata and masked input/output, and the thread shows a per-turn input-token trend with the cache-read split

#### Scenario: Retriever chunks visible on expand
- **WHEN** the operator expands a retriever span that has `metadata.retrieval_context`
- **THEN** the UI lists those chunk strings under the span (in addition to masked input/output)
