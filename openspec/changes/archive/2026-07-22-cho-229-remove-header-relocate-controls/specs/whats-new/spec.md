# whats-new

## MODIFIED Requirements

### Requirement: Home-screen-only pill with Restart takeover
The "What's new" control SHALL be shown only while the widget is on the home screen (greeting + stickers), rendered as a **floating control pinned to the top-right of the widget** (not inside a header). From the moment the user engages (sticker tap or first composer submit) the **same top-right slot** SHALL show a "↻ Restart" control instead, for the life of the conversation. Tapping Restart SHALL return the widget to the home screen — clearing the conversation, aborting any in-flight agent stream, and requesting a fresh agent thread via `POST /api/chat/reset` — after which the What's New control (including its unseen dot, if applicable) SHALL be shown again. The unseen-dot indicator SHALL never render on the Restart control.

#### Scenario: Control swaps on engagement
- **WHEN** the user taps a sticker or sends their first message
- **THEN** the floating top-right What's New control is replaced by the Restart control

#### Scenario: Restart returns to a clean home screen
- **WHEN** the user taps Restart mid-conversation (even while a reply is streaming)
- **THEN** the stream is aborted, the conversation clears to the greeting + stickers, the top-right control shows What's New again, and the next message starts a fresh agent conversation

#### Scenario: Reset failure degrades safely
- **WHEN** `POST /api/chat/reset` fails or times out
- **THEN** the UI still resets to the home screen and the next message simply continues the previous agent thread

#### Scenario: No unseen dot on Restart
- **WHEN** the widget is engaged and the top-right slot shows Restart
- **THEN** the unseen (red) dot does not render on the Restart control
