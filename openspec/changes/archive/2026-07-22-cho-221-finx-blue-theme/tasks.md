# CHO-221: finx-blue-theme — tasks

## 1. Accent token swap

- [x] 1.1 In `frontend/src/index.css`, set `--color-accent: #2777F3`, `--color-accent-strong: #1D5FD0`, `--color-accent-soft: #7AA8F8`, `--color-accent-tint: #E9F1FE`; update the "violet-600 family" comment to name the FinX blue system
- [x] 1.2 Confirm status tokens (`--color-online`, `--color-online-soft`, `--color-alert`) are untouched

## 2. Hard-coded violet surfaces

- [x] 2.1 In `frontend/src/widget/widget.ts`, change the launcher gradient to `linear-gradient(135deg, #4A90F5 0%, #1D5FD0 100%)` and fix the "purple launcher bubble" comment
- [x] 2.2 In `frontend/src/App.tsx`, change the logo tile gradient `from-violet-500` to the blue ramp (`from-[#4A90F5] to-accent-strong`)
- [x] 2.3 In `frontend/src/chat/datacards/HoldingsCard.tsx`, set `SEG_COLORS = ['#2777F3', '#7c3aed', '#0d9488', '#d97706', '#db2777']` (brand blue leads; old near-identical `#2563eb` replaced by recycled violet)

## 3. Demo page (jini-embed-demo.html)

- [x] 3.1 Check the local embed demo page for any inline violet chrome and align it with the blue theme; verify the rebuilt `widget.js` renders the blue bubble/panel on it

## 4. Verification

- [x] 4.1 Sweep: `grep -rn "7c3aed\|6d28d9\|a78bfa\|ede9fe\|8b5cf6\|violet" frontend/src` — only the intentional categorical `#7c3aed` in `SEG_COLORS` (and the `TintKey`/tint-map key names, which are token-backed) remain
- [x] 4.2 `cd frontend && npm run build` passes (app + widget entries)
- [x] 4.3 Frontend tests pass; visual QA of home screen, chat, flow cards, and launcher in light and dark themes

## 5. Ship & sync

- [x] 5.1 Ship via git-sync: branch `cho-221-finx-blue-theme`, commit `CHO-221: ...`, push, PR with `Fixes CHO-221`
- [x] 5.2 linear-connector: move CHO-221 through In Progress → In Review with a summary comment
- [x] 5.3 Deploy per the repo's CHO-219 Docker process once the PR lands
