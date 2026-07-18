# widget-launcher

## Requirements

### Requirement: Embeddable launcher script
We SHALL ship a standalone, framework-free embed script (`widget.js`, built from the frontend project as a separate entry) that the FinX website includes with one `<script>` tag. The host initializes it programmatically (e.g. `ChoiceJini.init({...})`) passing the session handoff values (userId, sessionId, accessToken, isDarkTheme, obStatus, optional screen name). On init it renders a floating circular launcher bubble fixed to the bottom-right corner of the host page.

#### Scenario: Host embeds and initializes
- **WHEN** a host page loads `widget.js` and calls `ChoiceJini.init` with session params
- **THEN** the purple launcher bubble appears fixed at the bottom-right, above host content

### Requirement: Bubble toggles the chat panel
Clicking the bubble SHALL toggle a corner panel (rounded card with shadow, ~380px wide × ~640px tall on desktop; full-screen overlay on narrow/mobile viewports) containing an iframe of the chat page, with the init params passed as query parameters and `platform=web`. The iframe SHALL stay mounted while the panel is hidden so conversation/session state survives close/reopen.

#### Scenario: Open and close from the bubble
- **WHEN** the user clicks the bubble
- **THEN** the panel opens with the chat page loaded and personalized; clicking the bubble again hides the panel without unloading the iframe

#### Scenario: State survives reopen
- **WHEN** the user opens the panel, the chat page finishes loading, and the user closes and reopens the panel
- **THEN** the chat page is NOT reloaded (same iframe document, no second boot)

### Requirement: In-chat back arrow closes the panel
When the chat page runs with `platform=web`, its header back arrow SHALL post a close message (`postMessage`, e.g. `{type: "choice-jini:close"}`) to the parent window; the embed script SHALL listen for it and close the panel. On other platforms the back arrow keeps its existing behavior (host webview owns navigation).

#### Scenario: Back arrow in web panel
- **WHEN** the user taps the chat header's back arrow inside the corner panel
- **THEN** the panel closes (bubble remains) and the iframe stays mounted

### Requirement: Theme pass-through
The embed SHALL forward `isDarkTheme` from init into the iframe query params so the panel content matches the host's theme, and the bubble/panel chrome SHALL look correct over both light and dark host pages.

#### Scenario: Dark host
- **WHEN** the host initializes with `isDarkTheme: true`
- **THEN** the chat inside the panel renders in dark theme at first paint

### Requirement: Demo host page
The repo SHALL include a local demo page simulating the FinX website (host content + embedded `widget.js`) for development and QA. The demo SHALL accept session values (e.g. from its own query string) and forward them to `ChoiceJini.init`, so the full corner experience is testable without the real FinX site.

#### Scenario: Local demo
- **WHEN** the demo page is opened locally with mock session values
- **THEN** the bubble renders over demo host content and the full open/close/personalized flow works
