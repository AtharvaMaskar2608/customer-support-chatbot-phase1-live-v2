# home-screen

## Purpose
The widget's home screen and its chrome: the personalized greeting, subtitle lines, the quick-action chip grid, the chat composer, and the compliance footer — plus the floating top-right control (What's new on the home screen, Main Menu during a conversation). Presentation only; chips submit predefined queries through the composer and never call tool APIs directly.
## Requirements
### Requirement: Chat page renders full-bleed
The chat page SHALL fill its viewport edge-to-edge with no outer backdrop, margin, or self-drawn card chrome — rounding and shadow are owned by the embedding surface (corner panel on web, webview on mobile). The mocks' floating-card look is produced by the embed, not by the page.

#### Scenario: Inside the corner panel
- **WHEN** the chat page loads inside the widget panel iframe
- **THEN** its content reaches the iframe edges with a single visible container (the panel itself), not a nested card

### Requirement: Home screen layout per approved mock
The widget home screen SHALL render, top to bottom: a hero greeting, two subtitle lines ("Reports, charges, processes, ticket status." and "Files land right here — no email verification needed." with the final phrase highlighted), a section of quick-action chips rendered **without an eyebrow heading** (no "POPULAR RIGHT NOW" label), an "or ask anything about FinX" divider, a rounded chat composer with a purple send button, and the compliance footer "Factual answers only — never investment advice". There SHALL be no header bar; the "What's new" control renders as a floating top-right overlay. Chat content carries enough top spacing that the greeting does not sit under the floating control.

#### Scenario: Chips render without the "Popular right now" heading
- **WHEN** the home screen loads with a valid session
- **THEN** the quick-action chips render directly under the subtitle lines with no "POPULAR RIGHT NOW" eyebrow label above them

#### Scenario: Full render with session
- **WHEN** the page loads with a valid session context
- **THEN** the greeting, subtitles, chips (unlabeled), divider, composer, and footer render in order, with the "What's new" control floating at the top-right and no header

### Requirement: Personalized hero greeting
The hero SHALL read "Hey <FirstName> — what do you need?" using the first name from the profile-greeting capability, with the name in the accent color. The client code appears in the header only, never in the hero.

#### Scenario: Profile available
- **WHEN** the greeting endpoint returns firstName "Pritam"
- **THEN** the hero reads "Hey Pritam — what do you need?"

#### Scenario: Profile unavailable
- **WHEN** the greeting endpoint fails or degrades
- **THEN** the hero reads "Hey there — what do you need?"

### Requirement: Quick-action chips fire predefined queries
The home-screen quick-action chips SHALL each submit their label (or trigger phrase) as a query through the chat composer; chips MUST NOT call tool APIs directly. The chip row is rendered from the flow registry, and a flow MAY opt out of the home chip row (via a `hideSticker` flag) while remaining reachable by composer keyword routing. The **Brokerage** flow SHALL NOT appear as a home chip.

#### Scenario: Chip tapped
- **WHEN** the user taps a quick-action chip (e.g. "Get my P&L")
- **THEN** the composer submits that chip's phrase as if typed by the user

#### Scenario: Brokerage is not a home chip
- **WHEN** the home screen renders
- **THEN** no Brokerage chip appears in the quick-action grid

#### Scenario: Brokerage stays reachable by typing
- **WHEN** the user types "what are my brokerage charges"
- **THEN** the brokerage flow runs and renders the rate card exactly as before

### Requirement: Host-controlled theme
The screen SHALL render in dark theme when the handoff includes `isDarkTheme=true` and in light theme otherwise, using Tailwind theme tokens; there is no in-widget theme toggle.

#### Scenario: Dark handoff
- **WHEN** the page is opened with `isDarkTheme=true`
- **THEN** the dark palette is applied at first paint with no light-theme flash

#### Scenario: What's new pill contrast in dark mode
- **WHEN** the header renders in dark theme
- **THEN** the "What's new" pill uses a light/elevated surface (not the light mode's black) so it is clearly visible against the dark header

