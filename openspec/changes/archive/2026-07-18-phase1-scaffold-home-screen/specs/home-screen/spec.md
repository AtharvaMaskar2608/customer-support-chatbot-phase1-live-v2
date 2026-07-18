# home-screen

## ADDED Requirements

### Requirement: Chat page renders full-bleed
The chat page SHALL fill its viewport edge-to-edge with no outer backdrop, margin, or self-drawn card chrome — rounding and shadow are owned by the embedding surface (corner panel on web, webview on mobile). The mocks' floating-card look is produced by the embed, not by the page.

#### Scenario: Inside the corner panel
- **WHEN** the chat page loads inside the widget panel iframe
- **THEN** its content reaches the iframe edges with a single visible container (the panel itself), not a nested card

### Requirement: Home screen layout per approved mock
The widget home screen SHALL render, top to bottom: a header (back button, Choice Jini logo and name, online status dot with the client code, and a "What's new" pill with notification dot), a hero greeting, two subtitle lines ("Reports, charges, processes, ticket status." and "Files land right here — no email verification." with the final phrase highlighted), a "POPULAR RIGHT NOW" section of four quick-action chips, an "or ask anything about FinX" divider, a rounded chat composer with a purple send button, and the compliance footer "Factual answers only — never investment advice".

#### Scenario: Full render with session
- **WHEN** the page loads with a valid session context
- **THEN** all sections render in the order above and the header shows "online · <USER_ID>"

### Requirement: Personalized hero greeting
The hero SHALL read "Hey <FirstName> — what do you need?" using the first name from the profile-greeting capability, with the name in the accent color. The client code appears in the header only, never in the hero.

#### Scenario: Profile available
- **WHEN** the greeting endpoint returns firstName "Pritam"
- **THEN** the hero reads "Hey Pritam — what do you need?"

#### Scenario: Profile unavailable
- **WHEN** the greeting endpoint fails or degrades
- **THEN** the hero reads "Hey there — what do you need?"

### Requirement: Quick-action chips fire predefined queries
The four chips — "Get my P&L", "Show my ledger", "Check my ticket status", "What are my brokerage charges?" — SHALL each submit their label as a query through the chat composer. Chips MUST NOT call tool APIs directly.

#### Scenario: Chip tapped
- **WHEN** the user taps "Get my P&L"
- **THEN** the composer submits the text "Get my P&L" as if typed by the user

### Requirement: Host-controlled theme
The screen SHALL render in dark theme when the handoff includes `isDarkTheme=true` and in light theme otherwise, using Tailwind theme tokens; there is no in-widget theme toggle.

#### Scenario: Dark handoff
- **WHEN** the page is opened with `isDarkTheme=true`
- **THEN** the dark palette is applied at first paint with no light-theme flash

#### Scenario: What's new pill contrast in dark mode
- **WHEN** the header renders in dark theme
- **THEN** the "What's new" pill uses a light/elevated surface (not the light mode's black) so it is clearly visible against the dark header
