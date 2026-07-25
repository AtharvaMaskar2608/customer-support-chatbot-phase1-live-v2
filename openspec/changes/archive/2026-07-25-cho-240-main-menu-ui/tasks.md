# CHO-240: main-menu-ui — tasks

## 1. Recolour + contain (2 variants → finalise)

- [ ] 1.1 In `frontend/src/App.tsx` `FloatingControls`, restyle the engaged "Main Menu" pill to the brand: `#EEF3FD` fill, `#1D4FB8` text, keep the 🏠 emoji (replace `bg-zinc-900` / `text-white` / dark inversion)
- [ ] 1.2 Produce **2 colour variations** for review (e.g. filled `#EEF3FD`/`#1D4FB8` vs a lighter/outline or purple-leaning treatment); screenshot both (light + dark)
- [ ] 1.3 Make the control self-contained so it doesn't overlap the chat (own contained surface + keep the reserved top spacing in `ChatShell`)
- [ ] 1.4 Add a legible dark-mode brand treatment; preserve the "visible in dark mode" guarantee
- [ ] 1.5 Decide whether the "What's new" (home-screen) pill matches the new colour; apply if yes
- [ ] 1.6 Finalise the chosen variant

## 2. Verification

- [ ] 2.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 2.2 Main Menu pill shows brand colours + 🏠, self-contained, in light + dark; does not cover chat content
- [ ] 2.3 Screenshots of both variants for the design pick before finalising

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-240
- [ ] 3.2 `linear-connector` — summary comment + state on merge
