# CHO-260 — design

## Context

- **Current (CHO-260 jam / full-screen shots):** `Stickers.tsx` maps all six visible flows (Holdings, P&L, Ledger, Tax/Capital gains, Contract notes, Pay in/out) in one `flex-wrap` 2×3 grid. Brokerage is excluded via `hideSticker` (CHO-233). `EmptyState.tsx` renders greeting + two subtitle lines + `<Stickers>` with **no** divider and **no** pager. Composer + compliance footer live in `ChatShell.tsx`'s fixed footer. Jam shots labelled "New UI" still show this current production layout (problem state), not a finished paginated mock.
- **Attachment mock (take only these two ideas):** original Choice Jini home shows **four** quick-action chips and a hairline divider with centred **"or ask anything about FinX"** above the composer. Do **not** restore "POPULAR RIGHT NOW", the old header chrome, ticket-status chip, or brokerage chip from that mock. Keep live FinX fonts/CSS.
- **Spec gap:** `openspec/specs/home-screen/spec.md` already lists the divider in the layout requirement, but the frontend never renders it.
- **Constraint:** Subtitle copy + highlight colour land in **CHO-254** first. This change rebases onto main after 254 merges and must not touch greeting or subtitle text.

## Goals / Non-Goals

**Goals:**

- Paginate home-screen chips at **four per page**, with lightweight navigation (prev/next + dots) using existing FinX styling.
- Render **"or ask anything about FinX"** between the chip block and the composer on the landing screen (hairline + label per attachment).
- Preserve chip tap behaviour (submit trigger phrase through composer); preserve `hideSticker` filtering.

**Non-Goals:**

- Rewriting greeting, subtitle, or compliance footer copy (CHO-254 owns subtitle).
- Changing chip labels, flow registry, or backend APIs.
- Redesigning the composer, floating controls, or chip visual language (colours, pill shape, icon circles).
- Restoring "POPULAR RIGHT NOW", header bar, ticket chip, or brokerage home chip from the attachment.
- Paginating the **no-match reply** sticker row in conversation (default: home-only pagination).

## Decisions

### D1 — Page size = 4 (screenshot-grounded)

**Choice:** `PAGE_SIZE = 4`.

**Screenshot grounding:** The attachment mock shows four chips at a time; live has six non-`hideSticker` flows. Four-per-page yields two pages (4 + 2) and matches the mock density without implying the bot only does those four. Jam shots do **not** show pager chrome yet — pagination controls are the implementation of product's "show a pagination" ask on top of that density.

**Alternative considered:** Show all six with wrap — rejected; product explicitly wants pagination so the landing does not read as a closed menu.

### D2 — Pagination controls: chevrons + dot indicators

**Choice:** Below the chip row, render a centred control row: `‹` / `›` icon buttons (disabled at bounds) and small dot indicators for the active page. Reuse zinc/accent token classes consistent with chip borders and existing UI chrome. No new font sizes.

**Screenshot grounding:** Neither the jam nor the attachment draws pager controls; product text requires pagination. Chevrons + dots are the minimal discoverable pattern for a two-page chip set on a narrow widget.

**Alternative considered:** Swipe gestures only — rejected; no existing swipe patterns in the widget and harder to discover. Dots alone are less discoverable on mobile.

### D3 — Pagination scoped to landing via prop

**Choice:** Add an optional `paginate?: boolean` (default `false`) on `Stickers`. `EmptyState` passes `paginate`. The no-match composer reply keeps `paginate={false}` (full wrap row, current behaviour).

**Rationale:** Product scope is the landing screen; conversation fallback stickers benefit from seeing all options at once.

### D4 — Divider placement + hairline treatment

**Choice:** Add a section at the bottom of `EmptyState` after the chip/pagination block:

```text
———  or ask anything about FinX  ———
```

Use a flex row with left/right `border-t` hairlines (`border-zinc-200` / `dark:border-zinc-700`) and centred muted label (`text-sm text-zinc-500 dark:text-zinc-400`), matching the attachment mock. Top margin separates it from pagination controls; bottom spacing clears the fixed composer in `ChatShell`.

**Rationale:** Divider collapses with the empty state (same `max-h` / opacity transition as greeting and chips). Keeps composer/footer ownership in `ChatShell` unchanged.

**Alternative considered:** Plain centred text with no hairlines — acceptable fallback if hairlines clash with spacing, but prefer the mock's rule+label treatment. Rendering the divider in `ChatShell` above `Composer` was rejected — it would linger during collapse or need extra phase wiring.

### D5 — Styling: existing tokens only

**Choice:** Divider and pager use existing zinc/accent classes already present on chips and subtitles. No new CSS file, no font-size changes.

**Rationale:** Linear: "Keep the font and css same as existing UI."

### D6 — State: local `useState` page index

**Choice:** `const [page, setPage] = useState(0)` inside `Stickers` when `paginate` is true. Reset to page 0 on mount (Restart / Main Menu remounts the shell).

**Rationale:** No URL or session persistence needed; page is ephemeral landing UI.

## Risks / Trade-offs

- **[Second page has only two chips]** → Left-align / natural chip widths (no stretching). Acceptable; density matches page-1's wrap behaviour.
- **[New flows push page count]** → `PAGE_SIZE` constant keeps behaviour predictable; dot count grows automatically.
- **[Divider + composer spacing on small viewports]** → Verify on narrow widget width; adjust `pt`/`pb` only if overlap occurs.
- **[Parallel with CHO-254]** → Blocked on same file; must merge 254 first to avoid rebase conflicts on the subtitle section.

## Migration Plan

1. Merge **CHO-254** to `main`.
2. Rebase `cho-260-landing-pagination` onto `main`.
3. Implement pagination + divider; run frontend gates.
4. Screenshot home screen page 1 and page 2 (light + dark) before deploy.
5. Rollback: revert frontend image tag; no data migration.

## Open Questions

- None blocking — product confirmed mock scope (pagination + divider only; existing typography). Pager chrome is a documented design choice because screenshots do not draw the controls.
