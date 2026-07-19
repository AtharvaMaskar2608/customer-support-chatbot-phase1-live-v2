# whats-new (delta)

## ADDED Requirements

### Requirement: Home-screen-only pill with Restart takeover
The "What's new" pill SHALL be shown only while the widget is on the home screen (greeting + stickers). From the moment the user engages (sticker tap or first composer submit) the same header slot SHALL show a "↻ Restart" control instead, for the life of the conversation. Tapping Restart SHALL return the widget to the home screen — clearing the conversation, aborting any in-flight agent stream, and requesting a fresh agent thread via `POST /api/chat/reset` — after which the What's New pill (including its unseen dot, if applicable) SHALL be shown again. The unseen-dot indicator SHALL never render on the Restart control.

#### Scenario: Pill swaps on engagement
- **WHEN** the user taps a sticker or sends their first message
- **THEN** the header's What's New pill is replaced by the Restart control

#### Scenario: Restart returns to a clean home screen
- **WHEN** the user taps Restart mid-conversation (even while a reply is streaming)
- **THEN** the stream is aborted, the conversation clears to the greeting + stickers, the header shows What's New again, and the next message starts a fresh agent conversation

#### Scenario: Reset failure degrades safely
- **WHEN** `POST /api/chat/reset` fails or times out
- **THEN** the UI still resets to the home screen and the next message simply continues the previous agent thread
