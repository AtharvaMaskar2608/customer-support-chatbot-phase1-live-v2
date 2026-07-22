# whats-new

## Purpose
The widget's announcement surface: remotely-served "What's new" content with an unseen indicator and modal, plus the header affordance that hosts it — home-screen-only, ceding its slot to the Restart control during a conversation.
## Requirements
### Requirement: Announcement content is served remotely
The backend SHALL expose `GET /api/whats-new` returning the current announcements as JSON: a content `version` string and an ordered list of items, each with `emoji`, `tint` (icon tile color key), `title`, and `description`. Content lives server-side only, so updating it requires no frontend/app release. The endpoint requires no credentials (content is non-personalized, non-PII).

#### Scenario: Content fetch
- **WHEN** the frontend requests `/api/whats-new`
- **THEN** it receives `{"version": "<id>", "items": [{"emoji": "📄", "tint": "indigo", "title": "Capital Gain report in Excel", "description": "Ask for FY 25-26 — delivered in-chat, tax-filing ready."}, {"emoji": "🎫", "tint": "green", "title": "Live ticket status", "description": "Type a ticket number to get its current stage, instantly."}]}`

### Requirement: What's new modal per approved mock
The modal SHALL render the announcement items from the fetched content as a titled list with tint-matched icon tiles, a close control, and a primary dismiss button. It SHALL NOT claim that content updates reach production without a release, since the content file is baked into the backend image and editing it requires a rebuild and redeploy.

#### Scenario: Modal lists the fetched items
- **WHEN** the customer opens the What's New modal
- **THEN** each item renders with its icon tile, title, and description, above a single dismiss button

#### Scenario: No remote-content claim
- **WHEN** the modal renders
- **THEN** no footer text asserts that content is updated remotely or that no app release is needed

### Requirement: Unseen indicator driven by content version
The "What's new" pill SHALL show a small red notification dot when the current content `version` has not been dismissed on this device. Dismissing the modal (Got it or ✕) SHALL persist the seen version locally so the dot stays hidden until the backend publishes a newer version.

#### Scenario: New content
- **WHEN** the page loads and the fetched `version` differs from the locally stored seen version
- **THEN** the pill shows the red dot

#### Scenario: Already seen
- **WHEN** the user has dismissed the modal for the current `version` and reloads the page
- **THEN** the pill renders without the red dot

#### Scenario: Content unavailable
- **WHEN** the `/api/whats-new` request fails
- **THEN** the pill renders without a red dot and opening it shows nothing broken (modal simply not available or empty state); the home screen is unaffected

### Requirement: Home-screen-only pill with Restart takeover
The "What's new" pill SHALL be shown only while the widget is on the home screen (greeting + stickers). From the moment the user engages (sticker tap or first composer submit) the same slot SHALL show a **"Main Menu"** control instead, for the life of the conversation. Tapping "Main Menu" SHALL return the widget to the home screen — clearing the conversation, aborting any in-flight agent stream, and requesting a fresh agent thread via `POST /api/chat/reset` — after which the What's New pill (including its unseen dot, if applicable) SHALL be shown again. The unseen-dot indicator SHALL never render on the "Main Menu" control. The control's visible label SHALL read "🏠 Main Menu" (a home emoji leading the label, mirroring the "✨ What's new" pill; not "Restart"); its behaviour is unchanged.

#### Scenario: Pill swaps on engagement
- **WHEN** the user taps a sticker or sends their first message
- **THEN** the What's New pill is replaced by the "Main Menu" control

#### Scenario: Main Menu returns to a clean home screen
- **WHEN** the user taps "Main Menu" mid-conversation (even while a reply is streaming)
- **THEN** the stream is aborted, the conversation clears to the greeting + stickers, the What's New pill returns, and the next message starts a fresh agent conversation

#### Scenario: Reset failure degrades safely
- **WHEN** `POST /api/chat/reset` fails or times out
- **THEN** the UI still resets to the home screen and the next message simply continues the previous agent thread

### Requirement: Every shipped item's emoji has a mapped glyph
Icon tiles SHALL render a tinted inline SVG glyph whose colour matches its tile. The emoji-to-glyph map exists because native emoji rendering breaks the two-tone tile design. Content shipped in `whats_new.json` MUST therefore use only emoji that are present in the map; the neutral-tile fallback remains for forward compatibility with content published later, but is not an acceptable state for shipped content.

#### Scenario: Shipped content never falls back to the neutral tile
- **WHEN** the modal renders the published announcement items
- **THEN** every tile shows a tinted SVG glyph, and none shows a raw colour emoji on a grey tile

#### Scenario: Unknown emoji still degrades safely
- **WHEN** content published later carries an emoji with no mapped glyph
- **THEN** that row renders the raw emoji on a neutral tile rather than failing to render

### Requirement: Content changes require a version bump
Any change to the announcement items SHALL be accompanied by a change to the `version` field. The unseen indicator is driven by comparing the fetched version against the locally persisted seen version, so unchanged versions leave previously-dismissed customers with no signal that the content changed.

#### Scenario: New copy reaches customers who already dismissed the previous version
- **WHEN** the items change and the version is bumped
- **THEN** a customer who dismissed the prior version sees the unseen dot again

#### Scenario: Unbumped content is invisible
- **WHEN** the items change but the version does not
- **THEN** previously-dismissed customers see no dot — this is the failure the requirement exists to prevent

