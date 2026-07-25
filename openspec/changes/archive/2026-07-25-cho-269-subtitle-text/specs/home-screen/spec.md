# home-screen

## MODIFIED Requirements

### Requirement: Home screen layout per approved mock
The widget home screen SHALL render, top to bottom: a hero greeting, **one** subtitle line ("Get your reports in chat, explain charges and processes - no email verification needed" with the final phrase **"no email verification needed"** highlighted in online/green via `text-online` / `text-online-soft` and **bold** via `font-bold`, same font size and leading as the surrounding subtitle text), a section of quick-action chips rendered **without an eyebrow heading** (no "POPULAR RIGHT NOW" label) showing **every** non-`hideSticker` flow in a single wrap row **with no pagination, swipe, or page controls**, an **"or ask anything about FinX"** divider (hairline rules with centred label) rendered **immediately above the chat composer** (not mid-stack under the chips), a rounded chat composer with a purple send button, and the compliance footer "Factual answers only — never investment advice". There SHALL be no header bar; the "What's new" control renders as a floating top-right overlay. Chat content carries enough top spacing that the greeting does not sit under the floating control.

#### Scenario: Chips render without the "Popular right now" heading
- **WHEN** the home screen loads with a valid session
- **THEN** the quick-action chips render directly under the subtitle with no "POPULAR RIGHT NOW" eyebrow label above them

#### Scenario: Full render with session
- **WHEN** the page loads with a valid session context
- **THEN** the greeting, subtitle, full unlabeled chip row, divider (above composer), composer, and footer render in order, with the "What's new" control floating at the top-right and no header

#### Scenario: Subtitle matches CHO-269 copy
- **WHEN** the home screen loads with a valid session
- **THEN** the subtitle reads "Get your reports in chat, explain charges and processes - no email verification needed" and does not use the CHO-254 two-line copy

#### Scenario: Highlight is green and bold
- **WHEN** the home screen renders the subtitle
- **THEN** only the phrase "no email verification needed" is styled with online/green tokens (`text-online` / `text-online-soft`) and `font-bold`; the rest of the subtitle stays the default muted body colour
