# brand-theme

## ADDED Requirements

### Requirement: Accent token ramp follows the FinX blue design system
The widget SHALL define its accent identity as four semantic theme tokens in the frontend's Tailwind theme, pinned to the FinX blue design system: `--color-accent: #2777F3` (primary, from the FinX Figma), `--color-accent-strong: #1D5FD0` (hover/pressed), `--color-accent-soft: #7AA8F8` (dark-theme accents), `--color-accent-tint: #E9F1FE` (chip/background wash). Components MUST reference these tokens (or utilities derived from them) for accent colouring rather than hard-coded accent hexes, so a future re-brand is a token-only change.

#### Scenario: Token swap re-skins both themes
- **WHEN** the four accent token values change
- **THEN** every accent-coloured element (buttons, links, chips, highlights, user message bubble) reflects the new colours in both light and dark themes without per-component edits

#### Scenario: Primary accent is FinX blue
- **WHEN** the home screen renders its send button and hero name highlight
- **THEN** they use `#2777F3` (via the accent token), not the retired violet `#7c3aed`

### Requirement: Launcher and logo gradients draw from the accent ramp
The launcher bubble and the home-screen logo tile SHALL use the blue accent gradient `linear-gradient(135deg, #4A90F5 0%, #1D5FD0 100%)` (lighter-blue to `accent-strong`), keeping the two surfaces visually paired.

#### Scenario: Blue launcher bubble
- **WHEN** the embed script renders the launcher bubble on a host page
- **THEN** the bubble background is the blue gradient `#4A90F5 → #1D5FD0`, with no violet remaining

### Requirement: Status colours are independent of the accent ramp
Status colours SHALL NOT change with accent re-brands: online/positive green `#16a34a` (with soft variant `#4ade80`) and alert/notification red `#ef4444` remain as-is.

#### Scenario: Re-brand leaves status colours untouched
- **WHEN** the accent ramp changes (violet → blue)
- **THEN** the online dot, highlight-phrase green, and notification dot render in the same greens/red as before

### Requirement: Data-visualisation palettes lead with the accent hue
Categorical chart palettes (e.g. the holdings donut) SHALL use the brand accent `#2777F3` as their first segment colour, and the remaining segment hues MUST stay pairwise distinguishable from it and from each other.

#### Scenario: Holdings donut leads with brand blue
- **WHEN** the holdings allocation donut renders with two or more segments
- **THEN** the first segment is `#2777F3` and no other segment colour is a near-identical blue
