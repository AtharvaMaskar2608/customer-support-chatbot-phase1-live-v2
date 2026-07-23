# CHO-268 — design

## Context

- **Current (CHO-260 on main / Jam on CHO-268):** Landing shows four chips + chevron/dot pager; page 2 holds the remaining chips. **"or ask anything about FinX"** renders directly under the pager, leaving a large empty band above the fixed composer. Product marked that divider in red and asked to drop the swipe UX.
- **Constraint:** Keep existing FinX chip/divider typography and colours. Do not touch traces, KB, or flow descriptors. Parallel agents own CHO-267 (KB/traces) and trace-cost work — this change owns only EmptyState / Stickers / home-screen OpenSpec.

## Goals / Non-Goals

**Goals:**

- Show every non-`hideSticker` chip on the landing screen in one wrap row (no pager).
- Place **"or ask anything about FinX"** immediately above the chat input so chips + divider + composer read as one screen.
- Preserve chip tap behaviour and `hideSticker` filtering.

**Non-Goals:**

- Changing greeting, subtitle, composer, footer, or chip visual language.
- Restoring "POPULAR RIGHT NOW" or the Brokerage home chip.
- Backend / API / registry edits.

## Decisions

### D1 — Remove pagination entirely (not raise PAGE_SIZE)

**Choice:** Delete `PAGE_SIZE`, page state, chevrons, dots, and the `paginate` prop. `Stickers` always renders the full filtered/sorted list.

**Rationale:** Product rejected swipe/pager UX, not merely the page size. Conversation no-match already used the full wrap row — unify on that.

**Alternative considered:** `PAGE_SIZE = 6` (one page today) — rejected; still leaves pager chrome if more flows land, and product asked to remove sliding cards.

### D2 — Divider stays in EmptyState; pin to bottom with flex

**Choice:** Keep the hairline divider inside `EmptyState` (so it collapses with the landing). Make the empty-state root a `flex-1 flex-col` child of the `min-h-full` scroll column and put `mt-auto` on the divider so it sits at the bottom of the landing canvas — visually just above the fixed composer strip.

**Screenshot grounding:** Jam red-box sits mid-screen under chips; product copy asks for “a little below just above the chat input.” Flex pin matches that without wiring phase into `ChatShell`.

**Alternative considered:** Render the divider in `ChatShell` above `Composer` when `phase !== 'chat'` — rejected; needs extra phase/collapse wiring and duplicates ownership of landing chrome.

### D3 — Styling unchanged

**Choice:** Reuse the CHO-260 hairline + `text-sm text-zinc-500` label classes; chip pills untouched.

**Rationale:** Linear: keep font/CSS of existing UI.

## Risks / Trade-offs

- **[Six chips taller than four + pager]** → Acceptable; reclaiming pager + mid-stack gap and pinning the divider should still fit the widget height used in Jam. If overflow appears on very short hosts, the scroll column already scrolls.
- **[flex-1 + collapse transition]** → Expanded state uses `flex-1` instead of a fixed `max-h-[640px]`; collapse still uses `max-h-0` + opacity. Verify collapse animation still settles cleanly on Restart / first send.
- **[origin/main may lag CHO-260]** → Branch from the CHO-260 merge commit; PR targets `main` once 260 is present (or nets to all-chips + bottom divider if 260 lands in the same window).

## Migration Plan

1. Land on a base that includes CHO-260.
2. Remove pager; pin divider; run frontend gates.
3. Rollback: revert frontend image / PR; no data migration.

## Open Questions

- None blocking — Jam + issue text are sufficient for placement.
