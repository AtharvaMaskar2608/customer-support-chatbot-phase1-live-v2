# home-screen

## MODIFIED Requirements

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
