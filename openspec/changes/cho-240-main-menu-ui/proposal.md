# CHO-240: main-menu-ui

## Why

The floating top-right control renders "🏠 Main Menu" (during a conversation) and "✨ What's new" (on the home screen) as a **black pill** (`bg-zinc-900` / white text; inverted to white in dark mode). Product says the Main Menu pill doesn't follow FinX branding, and as a floating overlay it can sit over the conversation. They want it recoloured to the brand blue and made self-contained so it doesn't cover the chat (CHO-240; tokens: background `#EEF3FD`, text `#1D4FB8`; keep the 🏠 emoji).

## What Changes

- Recolour the floating **Main Menu** pill from the black/inverted style to the FinX brand: a light-blue fill (`#EEF3FD`) with blue text (`#1D4FB8`), keeping the 🏠 emoji. Produce **2 colour variations** (e.g. filled `#EEF3FD`/`#1D4FB8` vs a lighter/outline treatment, or a blue vs a purple-leaning shade) for a quick design pick, then finalise one.
- Make the control **self-contained** so it does not overlap the conversation — give it its own contained treatment (backing / rounded container with the reserved top spacing) rather than a bare pill floating over messages.
- Dark mode gets an equivalent brand treatment (a legible elevated blue), preserving the existing "What's new pill stays visible in dark mode" guarantee.
- Frontend-only, `App.tsx` (`FloatingControls`). No backend/API change.

## Open decisions (design pick)

- Which of the 2 colour variants to finalise.
- Whether the **"What's new"** pill (same component, home-screen state) should match the new brand colour or stay as-is — recommend matching for consistency.

## Capabilities

### Modified Capabilities

- `home-screen`: the floating Main Menu control SHALL use the FinX brand colours (light-blue fill `#EEF3FD`, blue text `#1D4FB8`) with the 🏠 emoji, in a self-contained container that does not overlap the conversation, in both themes.

## Impact

- Frontend only: `frontend/src/App.tsx` — `FloatingControls` pill styling (engaged "Main Menu" state at minimum; the What's-new state to match if chosen).
- Preserve the CHO-229 relocation intent (controls at top-right) and the dark-mode visibility guarantee.
- `tsc` + lint + build gates; visible UI change → screenshot both variants (light + dark) for the pick.
- Linear: CHO-240 · branch `cho-240-main-menu-ui`.
