# home-screen

## MODIFIED Requirements

### Requirement: Home screen layout per approved mock
The widget home screen SHALL render, top to bottom: a hero greeting, two subtitle lines ("Reports, charges, processes, ticket status." and "Files land right here — no email verification needed." with the final phrase highlighted), a section of quick-action chips rendered **without an eyebrow heading** (no "POPULAR RIGHT NOW" label), an "or ask anything about FinX" divider, a rounded chat composer with a purple send button, and the compliance footer "Factual answers only — never investment advice". There SHALL be no header bar; the "What's new" control renders as a floating top-right overlay. Chat content carries enough top spacing that the greeting does not sit under the floating control.

#### Scenario: Chips render without the "Popular right now" heading
- **WHEN** the home screen loads with a valid session
- **THEN** the quick-action chips render directly under the subtitle lines with no "POPULAR RIGHT NOW" eyebrow label above them

#### Scenario: Full render with session
- **WHEN** the page loads with a valid session context
- **THEN** the greeting, subtitles, chips (unlabeled), divider, composer, and footer render in order, with the "What's new" control floating at the top-right and no header
