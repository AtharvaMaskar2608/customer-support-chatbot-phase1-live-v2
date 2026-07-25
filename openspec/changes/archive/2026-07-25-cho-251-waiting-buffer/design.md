## Context

`ChatShell.tsx` overlaps narration with backend fetches for report flows (`generate`), data flows (`generateData`), and contract-notes selection (`runSelection`). Each path:

1. Appends a `narrate` message with the first caption.
2. Starts the fetch promise (`resultP` / `listP`).
3. Walks `steps[i]` with `await delay(720)` between updates.
4. Waits a short tail delay (`560`/`400` ms), then `await`s the promise.
5. Removes the narrate pill and renders the result.

The comment on `generate` documents today's behavior: *"the pill holds its last caption until the response resolves."* That is correct for fast responses but reads as stuck when the fetch outlasts the sequence (e.g. holdings: `Fetching your holdings…` → freeze on `Valuing at last prices…` — the CHO-251 screenshot).

## Goals / Non-Goals

**Goals:**

- Keep the narrate pill visibly alive for the entire fetch duration.
- Reuse existing per-flow caption copy and ~720ms cadence.
- One consistent loop shared by `generate`, `generateData`, and `runSelection`.
- Remove the pill and render results/errors exactly as today once the promise settles.

**Non-Goals:**

- New soft "Still working…" copy (rejected — see Decision 1).
- Fake progress percentages or indeterminate bars.
- Editing EmptyState, Stickers, BrokerageCard, backend, or flow descriptors.
- Single-caption ticket-raise waits — out of scope unless they share the helper trivially.

## Decisions

### 1. Cycle the descriptor narration array (locked)

After index `steps.length - 1`, wrap to index `0` and continue updating until the fetch promise resolves. Same ~720ms delay between steps.

**Why cycle over soft "Still working…" hold messages:** Reuses byte-stable copy already owned by each flow; continuous motion signals activity without inventing new strings or touching descriptors. Matches product ask (keep cycling until the document appears) and the triage preference.

**Why over extending descriptor arrays with duplicates:** Behavior belongs in the shell; descriptors stay unchanged (parallel-safe vs any copy/descriptor work).

**Single-step narrations** (e.g. brokerage `['Fetching your plan…']`): cycling keeps the same caption — no visual flicker gain, but no hang regression either; out of scope to invent extra copy for those.

### 2. Race the loop against the promise

```text
start fetch → promise P
show steps[0]
while P pending:
  await delay(720)   # or race delay vs P
  advance caption (wrap at end)
await P
remove narrate pill → render result
```

Prefer a small shared helper (e.g. `cycleNarration(narrId, steps, resultP, { stepMs: 720 })`) called from all three sites if it avoids copy-pasted loops. Keep it in `ChatShell.tsx` or an adjacent tiny util — no new module tree.

Exit promptly when `P` settles (race/`settled` flag) so we do not schedule an extra caption tick after the result is ready.

### 3. Drop the post-sequence tail delay

Today's `await delay(560)` / `400` after the last step exists because narration ends before awaiting `P`. With cycling, the loop covers the wait — remove the redundant tail delay so we don't add dead time after the fetch completes.

### 4. Email mode steps unchanged

`generate` still builds `steps` with the final "Emailing it to you…" swap for email delivery. The loop wraps the full `steps` array, including that substitution.

## Risks / Trade-offs

- **[Risk] Caption re-loop feels repetitive on very long fetches** → Mitigation: 720ms cadence unchanged; three-step loops still show each caption ~720ms per lap. Acceptable vs looking hung.
- **[Risk] Extra caption tick after fetch resolves** → Mitigation: race/check `P` before each delay or use a settled flag so the pill clears promptly.
- **[Risk] Contract-notes path used 400ms tail, reports used 560ms** → Mitigation: unify on the cycling helper; delete per-path tail delays.

## Migration Plan

Frontend-only deploy. No API, env, or data migration. Rollback = revert the `ChatShell` loop change.

## Open Questions

_(none — cycling vs soft hold is decided)_
