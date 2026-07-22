# CHO-225: whats-new-content-refresh — tasks

## 0. Gate

- [x] 0.1 Copy sign-off on the corrected item 1 ("Delivered in chat as a PDF — no email verification") — it replaces the tester's "PDF or Excel in chat, any period", which is factually wrong for P&L and contract notes
- [x] 0.2 Confirm keeping the Capital Gains Excel item as a third entry (the modal has no item cap)

## 1. Footer removal

- [x] 1.1 Delete the `<p>Content updated remotely — no app release needed</p>` block from `frontend/src/WhatsNewModal.tsx`
- [x] 1.2 Check the "Got it" button's bottom spacing still reads correctly without the paragraph below it, in light and dark themes

## 2. Icon glyph for the new item

- [x] 2.1 Add `'✨': SparkleIcon` to the `GLYPHS` map in `WhatsNewModal.tsx` (import from `./icons` — `SparkleIcon` already exists)
- [x] 2.2 Add a `blue` entry to `TINTS` using the accent tokens (`bg-accent-tint dark:bg-accent/20`, `text-accent dark:text-accent-soft`) so the tile matches the FinX blue system from CHO-221
- [x] 2.3 Verify no shipped item falls through to the `NEUTRAL` tile

## 3. Content

- [x] 3.1 Rewrite `backend/content/whats_new.json` items to the three agreed entries with emoji 📄 / ✨ / 📄 and tints indigo / blue / indigo
- [x] 3.2 Bump `version` to `2026-07-20.1`
- [x] 3.3 Re-read the copy against the code one final time: no Excel claim on P&L or contract notes, no "any period" claim on flows with `maxRangeYears`

## 4. Verification

- [ ] 4.1 With a stale `choiceJini.whatsNew.seenVersion` in localStorage, confirm the red dot appears after the version bump
- [ ] 4.2 Dismiss, reload, confirm the dot stays hidden
- [x] 4.3 All three tiles render tinted glyphs (no grey neutral tile, no raw colour emoji) — verified statically: all three emoji resolve in `GLYPHS` and all three tints resolve in `TINTS`, so neither `NEUTRAL` branch is reachable for shipped content
- [ ] 4.4 `cd frontend && npm run build`; `cd backend && uv run pytest` — `npx tsc --noEmit` clean and `pytest -k whats_new` 3 passed; full build deferred (concurrent build in flight)

## 5. Follow-up (not in this change)

- [ ] 5.1 Raise a separate issue for making `content/` genuinely remote (volume mount or config service) so future copy edits need no redeploy — overlaps CHO-219

## 6. Ship & sync

- [ ] 6.1 `git-sync` with issue key CHO-225
- [ ] 6.2 `linear-connector` — summary comment + state to Done on merge
