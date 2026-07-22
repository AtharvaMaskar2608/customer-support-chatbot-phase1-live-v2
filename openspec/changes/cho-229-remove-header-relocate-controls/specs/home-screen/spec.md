# home-screen

## MODIFIED Requirements

### Requirement: Home screen layout per approved mock
The widget home screen SHALL render, top to bottom: a hero greeting, two subtitle lines ("Reports, charges, processes, ticket status." and "Files land right here — no email verification." with the final phrase highlighted), a "POPULAR RIGHT NOW" section of four quick-action chips, an "or ask anything about FinX" divider, a rounded chat composer with a send button, and the compliance footer "Factual answers only — never investment advice". There SHALL be **no header bar**: the sparkle logo, the "Choice Jini" title, the online status dot, and the client code are not displayed anywhere on the surface. The "What's new" control (with its Restart takeover per the whats-new capability) SHALL render as a **floating control pinned to the top-right** of the widget, overlaying the content, rather than inside a header. Chat content carries enough top spacing that the greeting does not sit under the floating control.

#### Scenario: Full render with session
- **WHEN** the page loads with a valid session context
- **THEN** the greeting, subtitles, chips, divider, composer, and footer render in order, with the "What's new" control floating at the top-right — and no header, logo, title, online status, or client code appears anywhere

#### Scenario: Client code is not shown
- **WHEN** the widget renders with a known client code
- **THEN** the client code is not displayed on screen (it previously appeared in the header, which is removed)

#### Scenario: Content clears the floating control
- **WHEN** the home screen or an active conversation renders
- **THEN** the top of the content (greeting or first message) is spaced below the floating top-right control and does not overlap it
