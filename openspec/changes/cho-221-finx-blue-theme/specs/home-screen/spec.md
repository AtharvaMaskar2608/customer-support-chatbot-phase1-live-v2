# home-screen — delta

## MODIFIED Requirements

### Requirement: Home screen layout per approved mock
The widget home screen SHALL render, top to bottom: a header (back button, Choice Jini logo and name, online status dot with the client code, and a "What's new" pill with notification dot), a hero greeting, two subtitle lines ("Reports, charges, processes, ticket status." and "Files land right here — no email verification." with the final phrase highlighted), a "POPULAR RIGHT NOW" section of four quick-action chips, an "or ask anything about FinX" divider, a rounded chat composer with an accent-coloured (FinX blue, per `brand-theme`) send button, and the compliance footer "Factual answers only — never investment advice".

#### Scenario: Full render with session
- **WHEN** the page loads with a valid session context
- **THEN** all sections render in the order above and the header shows "online · <USER_ID>"
