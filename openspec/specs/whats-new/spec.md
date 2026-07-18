# whats-new

## Requirements

### Requirement: Announcement content is served remotely
The backend SHALL expose `GET /api/whats-new` returning the current announcements as JSON: a content `version` string and an ordered list of items, each with `emoji`, `tint` (icon tile color key), `title`, and `description`. Content lives server-side only, so updating it requires no frontend/app release. The endpoint requires no credentials (content is non-personalized, non-PII).

#### Scenario: Content fetch
- **WHEN** the frontend requests `/api/whats-new`
- **THEN** it receives `{"version": "<id>", "items": [{"emoji": "📄", "tint": "indigo", "title": "Capital Gain report in Excel", "description": "Ask for FY 25-26 — delivered in-chat, tax-filing ready."}, {"emoji": "🎫", "tint": "green", "title": "Live ticket status", "description": "Type a ticket number to get its current stage, instantly."}]}`

### Requirement: What's new modal per approved mock
Tapping the header "✨ What's new" pill SHALL open a card-style modal over the home screen containing: title "✨ What's new in Jini" with a close (✕) button, one row per item (emoji on a rounded tinted tile, bold title, gray description), a full-width purple "Got it" button, and the footer "Content updated remotely — no app release needed". Emoji glyphs match the product's emoji icon language (✨ header, per-item emoji from the payload).

Item icons SHALL be tint-matched per the mock: the glyph renders in the tile's tint colour (blue document on the indigo tile, green ticket on the green tile) rather than in native multi-colour emoji rendering. Unknown tint keys fall back to a neutral tile with the emoji as-is.

#### Scenario: Open and render
- **WHEN** the user taps the "What's new" pill
- **THEN** the modal opens showing the fetched items in order with their emoji tiles, and the home screen remains visible behind it

#### Scenario: Tint-matched icon rendering
- **WHEN** an item with tint "green" and a ticket glyph renders
- **THEN** the icon appears in green tones on the green tile (mock-faithful), not in the emoji's native colours

#### Scenario: Dismissal
- **WHEN** the user taps "Got it" or ✕
- **THEN** the modal closes and the home screen is unchanged

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
