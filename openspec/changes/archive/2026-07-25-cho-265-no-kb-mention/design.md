## Context

Jam (CHO-265) shows the model streaming a long reply that discloses the whole retrieval loop:

1. "I'll search our **knowledge base**…"
2. "The **search results** are about… **Let me search more specifically.**"
3. "The **knowledge base results** don't address… This is **likely**… **may involve**…"
4. "**Let me raise a support ticket**…"

Conceptual leaks (tester attachment): retrieval mechanism exists · attempt failed · retry happened · second attempt failed · bot is guessing · step-by-step reasoning.

`prompt.py` already has a thin ban ("Never narrate retrieval… let me search / the results show") and CHO-241 bans "let me raise a ticket". The `search_knowledge_base` tool description still says "Search Choice's support knowledge base… Summarize the results" — priming that leaks into replies. Internal code, comments, and OpenSpec may still say "knowledge base"; only **streamed assistant text** is in scope.

Verified from screenshots: leak is **assistant bubble text**, not ChatShell / `toolCaption` status pills. Frontend stays out of ownership.

## Goals / Non-Goals

**Goals:**

- User-visible replies never expose retrieval mechanics, announce-then-act, retry disclosure, process-tied uncertainty/guessing, or self-narration from the CHO-265 lists.
- Enforcement via expanded **USER-FACING VOICE** in `PRIMED_INSTRUCTIONS` plus softened tool descriptions (prompt-first).
- Empty/miss answers stay honest and actionable without forbidden phrases; ticket offer stays ask-then-stop (CHO-241).
- Spec delta captures Jam-shaped scenarios for manual QA / eval.

**Non-Goals:**

- Post-generation regex filter or reply rewriting (brittle on words like `context` / `probably` in legitimate copy).
- Changing loop orchestration, SSE events, or frontend copy (`toolCaption`, ChatShell narration).
- Renaming internal symbols (`search_knowledge_base`, `run_kb_search`).
- Blanket ban on every conversational hedge in clean factual answers (see Decision 3).
- Deepeval phrase suites (follow-up if prompt-only fails).

## Decisions

### Decision 1 — Prompt-first (no post-filter in this change)

**Choose:** expand system/primed prompt banned patterns + rewrite voice rules; soften tool descriptions.

**Reject for now:** server-side post-filter on streamed `text` events — high false-positive rate on financial copy, fights the model, hard to stream safely.

**Follow-up trigger:** if manual QA after prompt harden still sees Jam-class leaks, open a separate change for a narrow phrase denylist (mechanism/narration phrases only — never the full uncertainty list).

Add a dedicated **USER-FACING VOICE** subsection (consolidate the scattered one-liner) with categories from Linear:

| Category | Banned (full list from CHO-265) | Intent |
|---|---|---|
| Mechanism | `knowledge base` · `KB` · `search results` · `retrieval` · `documents` · `sources` · `index` · `process note` · `vector` · `embedding` · `context` · `chunk` | Hide how answers are produced |
| Process narration | `I'll search` · `let me search` · `searching for` · `let me look` · `let me check` · `let me find` · `I'm looking into` · `let me try` · `let me raise` | Announce-then-act — call the tool, then answer |
| Retry disclosure | `let me search more specifically` · `let me try again` · `that didn't return` · `the first search` · `a different search` · `more relevant results` | Hide multi-step retrieval |
| Process-tied uncertainty | see Decision 3 | Stop guessing after empty/failed lookup |
| Self-narration | `based on what I found` · `according to the information I have` · `from what I can see` · `the results indicate` · `I don't have information on` | Hide the lookup step |

**Allowed miss-phrasing** (nothing usable returned): short factual declines — e.g. "That isn't covered in our support guides", "I can't pull that for your account", "Want me to raise a ticket so the team can take this up?" — without mechanism, retry, or self-narration words. Do not invent facts to avoid sounding uncertain.

Phrase-oriented bans in the prompt (not token-level). Words like `context` in "market context" are fine when not describing retrieval.

### Decision 2 — Soften tool-facing copy; keep internal names

Internal tool name stays `search_knowledge_base` (loop, tests, dispatch). Rewrite the Anthropic-facing **description** to frame fetching support answers for general product/process questions — no "knowledge base", "search results", or "Summarize the results". Prefer "Answer the user directly from what the tool returns" tone.

Also soften cross-references that the model might echo:
- `get_brokerage_rates` description ("prefer search_knowledge_base")
- primed tool list / brokerage fallback line ("fall back to search_knowledge_base, saying the rates shown are general") — keep routing semantics; drop user-leakable "knowledge base" priming where the model is told what to *say*.

### Decision 3 — Narrow the Linear uncertainty ban (do not destroy answer quality)

Linear's uncertainty list (`I'm not sure`, `I think`, `it seems`, `this is likely`, `may involve`, `might be`, `possibly`, `probably`, `I believe`, `it appears`, `as far as I can tell`) is **aggressive** if applied to every reply.

**Narrowed rule for implementers:**

Ban those hedges when they are part of **process narration**, **mechanism disclosure**, or **guessing after a failed/empty lookup** — i.e. when they paper over "I searched and found nothing" or invent likely causes (Jam §3: "This is likely… may involve…").

**Do not** treat the list as a global forbid on soft language in an otherwise clean, direct answer (e.g. ordinary hedging about market timing when no retrieval story is being told). Prefer: state the known fact, or use allowed miss-phrasing + ticket offer — never invent a process theory.

Compliance deflections (no investment advice) remain unchanged.

### Decision 4 — Few-shot reinforcement (optional, minimal)

Add one compact `<example>` if token budget allows: how-to → silent tool call → direct answer with zero banned words; or empty lookup → allowed miss + ticket offer. Prefer extending existing examples over many new ones. Keep CHO-241 ticket examples intact.

## Risks / Trade-offs

- **[Risk] Prompt-only may miss some leaks** → Mitigation: Jam-shaped QA scenarios in spec; post-filter only as a later change if needed.
- **[Risk] Over-broad uncertainty ban hurts quality** → Mitigation: Decision 3 scopes hedges to process/mechanism/guessing-after-miss; document in prompt as "do not guess or narrate uncertainty about lookups".
- **[Risk] Softened tool description reduces tool-use accuracy** → Mitigation: keep clear when-to-call routing; only strip leakable nouns.
- **[Risk] Cached prefix grows** → Mitigation: USER-FACING VOICE replaces scattered one-liners rather than duplicating; stay above Haiku cache floor.
- **[Risk] CHO-241 overlap on "let me raise"** → Mitigation: voice section references ticket policy; do not weaken offer-never-decide.

## Migration Plan

1. Land prompt + tool-description edits behind normal backend deploy (no feature flag).
2. Smoke: how-to with hit, how-to with miss, obscure question matching Jam theme.
3. Rollback: revert prompt/tools commits; no data migration.

## Open Questions

- None blocking apply. If prompt-only QA fails twice on Jam-class leaks, file a follow-up for a narrow mechanism/narration post-filter (not the full uncertainty list).
