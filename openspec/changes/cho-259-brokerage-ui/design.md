# CHO-259 — design

## Context

- **Current:** `BrokerageCard` renders a flat, **cross-segment rate-cluster** list (`brokerageClusters` → `ClusterRow`). `rateDisplay` is **percentage-primary** for value-based rates (`0.01%` bold + `₹1 per ₹10,000 traded` beneath). Follow-up is the generic help line ("Want a specific trade's charges? · Tell me."). No segment icons/colours. Segment order follows API payload order in the fallback list.
- **Approved mock (Linear CHO-259 attachment):** single answer **accordion** by segment — Equity expanded, Derivative / Commodity / Currency collapsed; coloured 22px icon tiles; line items with ₹ phrasing; statutory disclaimer in the card footer; two **pill chips** below the card ("Get my contract note", "🎫 Raise a ticket"). Intro: "Here's your brokerage plan — tap a segment to expand."
- **Constraint:** Wave 1 parallel with CHO-251 / CHO-265. Own brokerage card/cluster/descriptor + brokerage-flow delta. Prefer descriptor-level follow-up; only a minimal shared follow-up render hook in ChatShell/`DataFollowup` if needed. No backend/API change.

## Goals / Non-Goals

**Goals:**

- Replace rate-clustered flat list with a **segment accordion** as the primary UI (one fetch → one card).
- Fixed segment order **Equity → Derivative → Commodity → Currency**; Equity expanded by default.
- FinX four-colour icon tiles (22px, rounded) per segment.
- ₹-primary rate phrasing (drop %-primary).
- Statutory disclaimer always visible (keep existing honesty copy — Linear: "existing copy is close").
- Two post-card chips: Contract Notes flow + raise ticket (ticket emoji).
- Preserve parse honesty: unparseable lines show upstream `desc` verbatim; never invent cross-segment "All futures" summaries.

**Non-Goals:**

- Backend / `/api/data/brokerage` / upstream slab shape changes.
- Home `EmptyState`, `prompt.py`, narration-loop work (CHO-251).
- Redesigning other data cards (holdings / money) or generic help-card chrome.
- Restoring cross-segment rate clustering as a user-visible mode.

## Decisions

### D1 — Accordion by segment replaces rate clustering

**Choice:** Primary render path is one accordion panel per non-empty segment group. Drop `brokerageClusters` / `ClusterRow` / `clusterLabel` from the card path. Keep `parseRate` + INR formatting; reshape `rateDisplay` for ₹-primary single-line copy. Remove or leave unused the cluster helpers (prefer delete if nothing else imports them; add a small unit-testable `orderBrokerageGroups` helper instead).

**Rationale:** Mock and Linear both require segment accordion. Cross-segment "All futures" clustering is the old primary UX and conflicts with fixed segment order.

**Alternative considered:** Keep clustering as an alternate view — rejected; product wants one card pattern.

### D2 — Fixed segment order + Equity default open

**Choice:** Canonical order constant:

`['Equity', 'Derivative', 'Commodity', 'Currency']`

Sort/filter known titles into that order; append any unknown titles (stable, after known) so a new upstream label still appears. Empty groups stay dropped (existing `parseBrokeragePayload` behaviour). Default expanded key = `'Equity'` when present; otherwise first ordered group. Local `useState` for which panels are open — **independent toggles** (Equity stays open until the user collapses it; opening Derivative does not force-close Equity). Chevron up when open, down when closed.

**Rationale:** Linear: "do not sort" by API order; mock shows Equity open + others closed. Independent toggles match "tap a segment to expand" without surprising collapses on mobile.

**Alternative considered:** Exclusive accordion (one open) — rejected for now; mock does not show mutual exclusion and Equity-as-reference is useful while browsing another segment.

### D3 — Rate phrasing: ₹-primary (Linear copy wins over mock sample strings)

**Choice:** Change `rateDisplay` so the **visible primary line** is:

| Unit | Display |
|------|---------|
| `per10k` | `₹{amount} per ₹10,000 traded` |
| `order` | `₹{amount} flat per order` |

Use existing `formatRateInr` (no trailing `.00`). **Do not** show `formatRatePct` on the card. The mock attachment still shows raw upstream strings (`₹0.10 for trade value of 10 thousand`) in the Equity rows — treat that as sample API text in the HTML mock, not the target copy. Linear's explicit "Rate phrasing — the copy change" is authoritative.

**Rationale:** Current UI's %-primary is exactly what product is replacing; Linear gives the two shapes verbatim.

**Alternative considered:** Show upstream `desc` always — rejected; would leave the copy change unfinished when parse succeeds.

### D4 — Per-line fallback (no whole-card cluster fallback)

**Choice:** For each line: if `parseRate(desc)` succeeds → ₹ phrasing; else → show `desc` verbatim on the right. No `MAX_CLUSTERS` / poison-the-whole-card fallback. The accordion shell always wraps segments.

**Rationale:** Clustering fallback existed to avoid a wrong "All futures" summary. Without clustering, per-line honesty is enough and keeps the accordion chrome consistent.

### D5 — Segment icon tiles (22px, FinX colours)

**Choice:** Map segment title → `{ bg, fg, Icon }`:

| Segment | Tile bg | Icon colour | Icon motif (mock) |
|---------|---------|-------------|-------------------|
| Equity | `#E8F0FE` | `#1D4FB8` | line-chart |
| Derivative | `#F0EBFE` | `#6941C6` | bar-chart |
| Commodity | `#FEF4E6` | `#B76E00` | coin |
| Currency | `#E9F9F0` | `#17B26A` | exchange / circular arrows |

Tile: `22×22`px, rounded (`rounded-md` / ~6px). Inline small SVGs next to the card (or tiny local helpers in `BrokerageCard.tsx`) — do **not** expand the shared sticker icon set unless an icon already exists. Unknown segments: neutral zinc tile + generic glyph.

Panel header row (mock): coloured tile · **UPPERCASE** segment title · muted "`N rates`" · chevron. Expanded body: item title left, rate right, hairline dividers.

**Rationale:** Colours and 22px tiles are specified in Linear; motifs are visible in the mock attachment.

### D6 — Card chrome: no "grouped by rate" header

**Choice:** Drop the current hero ("Your brokerage rates" + "What you pay to trade — grouped by rate"). The card is the accordion + footer disclaimer. Update descriptor `intro` to the mock line: **"Here's your brokerage plan — tap a segment to expand."**

**Rationale:** Mock has no rate-group header; intro carries context. Keeping the old subline would contradict the new layout.

### D7 — Disclaimer: keep existing honesty copy

**Choice:** Keep the current footer string (plan rates + statutory charges + contract note). Do **not** switch to the mock's shorter "Brokerage only — …" variant unless product reopens it.

**Rationale:** Linear: "existing copy is close" / mandatory always-visible statutory disclaimer. Spec's plan-vs-billed honesty already matches the live string.

### D8 — Follow-up chips via descriptor (minimal shared render)

**Choice:** Extend data-flow `followup` so brokerage can declare **chips** instead of the text·help link:

```ts
// Conceptual — keep holdings/money working
followup:
  | { text: string; linkLabel: string }           // existing
  | { chips: Array<{
        label: string
        emoji?: string          // e.g. '🎫' for ticket
        action: 'startFlow' | 'raiseTicket'
        flowKey?: string        // when startFlow — 'contractNotes'
      }> }
  | null
```

Wire in `brokerage.ts`:

1. `{ label: 'Get my contract note', action: 'startFlow', flowKey: 'contractNotes' }`
2. `{ label: 'Raise a ticket', emoji: '🎫', action: 'raiseTicket' }`

**Minimal ChatShell touch:** in `case 'dataFollowup'`, if `chips` present, render a horizontal wrap of pill buttons (reuse `HelpCard` / Refresh-prices pill classes); `startFlow` → existing `runFlowBody(getFlow(...))` (or sticker-start path without duplicating user echo incorrectly — echo chip label as user message then start the file flow); `raiseTicket` → existing `handleRaiseTicket`. Holdings/money keep `{ text, linkLabel }` unchanged.

Prefer implementing chip UI in `DataFollowup` (or a sibling `DataFollowupChips`) under `primitives.tsx` so ChatShell stays a thin switch.

**Rationale:** Product wants chips below the card (same `dataFollowup` message slot). Descriptor-owned keeps ownership parallel-safe; avoids a brokerage-only ChatShell branch beyond the action dispatch.

**Alternative considered:** Embed chips inside `BrokerageCard` — rejected; feedback chips / message model already place follow-up as a sibling message, and card-internal chips would fight that layout.

### D9 — Parallel ownership

**Choice:** Touch only:

- `frontend/src/chat/datacards/BrokerageCard.tsx`
- `frontend/src/chat/datacards/brokerageCluster.ts` (rename responsibilities OK; file may keep parse/format + ordering helpers)
- `frontend/src/flow/dataflows/brokerage.ts`
- `frontend/src/flow/dataflow.ts` (followup type widen — shared, additive)
- `frontend/src/chat/datacards/primitives.tsx` (chip follow-up render)
- `frontend/src/chat/ChatShell.tsx` — **only** `dataFollowup` case action wiring (no narration loop)
- Unit tests for order + `rateDisplay` (new file under `frontend/src/...` or colocated if the repo pattern prefers)
- `openspec/.../brokerage-flow` delta

**Do not touch:** `EmptyState`, `prompt.py`, narration cycling, other flow descriptors' copy (except type-compat).

## Risks / Trade-offs

- **[Mock shows upstream desc; Linear wants ₹ phrasing]** → Documented in D3; implement Linear. If QA flags mismatch vs HTML mock, confirm with product — phrasing is the named "copy change".
- **[Follow-up type widen touches shared `dataflow.ts` + ChatShell]** → Additive discriminated field; holdings/money paths unchanged. Coordinate merge order if another Wave 1 PR also edits `followup` (unlikely).
- **[Contract-notes chip starts a multi-slot file flow]** → Reuse existing start path; user should see the contract-notes flow card, not a silent no-op.
- **[Unknown / renamed segment titles]** → Append after canonical order with neutral tile; still honest.
- **[Dark mode]** → Tile bg/fg hexes from FinX reports stay as specified (same as light); verify contrast on dark card chrome; adjust only if illegible.
- **[Removing clustering without tests]** → Add focused unit tests for `orderBrokerageGroups` + `rateDisplay` before deleting cluster helpers.

## Migration Plan

1. Land OpenSpec artifacts (this change) → implement on branch `cho-259-brokerage-ui`.
2. Frontend-only deploy (bump `frontend` image tag per `docs/deployment.md`).
3. Screenshot light + dark (Equity expanded + one other expanded; chips visible) before prod.
4. Rollback: revert frontend image tag; no data migration.

## Open Questions

- None blocking. Disclaimer copy: keep existing (D7). If product later insists on the mock's shorter footer, that is a one-line follow-up.
