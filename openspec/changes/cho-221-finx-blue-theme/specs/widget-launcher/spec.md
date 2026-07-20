# widget-launcher — delta

## MODIFIED Requirements

### Requirement: Embeddable launcher script
We SHALL ship a standalone, framework-free embed script (`widget.js`, built from the frontend project as a separate entry) that the FinX website includes with one `<script>` tag. The host initializes it programmatically (e.g. `ChoiceJini.init({...})`) passing the session handoff values (userId, sessionId, accessToken, isDarkTheme, obStatus, optional screen name). On init it renders a floating circular launcher bubble fixed to the bottom-right corner of the host page.

#### Scenario: Host embeds and initializes
- **WHEN** a host page loads `widget.js` and calls `ChoiceJini.init` with session params
- **THEN** the blue-gradient launcher bubble (per `brand-theme`) appears fixed at the bottom-right, above host content
