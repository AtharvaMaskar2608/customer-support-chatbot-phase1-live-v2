# CHO-234: remove-popular-right-now — tasks

## 1. Remove the label

- [ ] 1.1 In `frontend/src/chat/EmptyState.tsx`, delete the "Popular right now" `<h3>` eyebrow (the heading above `<Stickers>`), keeping `<Stickers onPick={onPick} />`
- [ ] 1.2 Adjust the wrapping `<section className="pt-6">` spacing (drop the now-removed heading's `mb-3` gap) so the chips sit correctly under the subtitle lines

## 2. Verification

- [ ] 2.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 2.2 Home screen shows the chip grid with **no "POPULAR RIGHT NOW" heading**, spacing intact (light + dark)

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-234
- [ ] 3.2 `linear-connector` — summary comment + state on merge
