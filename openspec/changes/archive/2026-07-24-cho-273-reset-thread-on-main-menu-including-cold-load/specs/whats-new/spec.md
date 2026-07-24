## MODIFIED Requirements

### Requirement: Home-screen-only pill with Restart takeover
The "What's new" pill SHALL be shown only while the widget is on the home screen (greeting + stickers). From the moment the user engages (sticker tap or first composer submit) the same slot SHALL show a **"Main Menu"** control instead, for the life of the conversation. Tapping "Main Menu" SHALL return the widget to the home screen — clearing the conversation, aborting any in-flight agent stream, and requesting a fresh agent thread via `POST /api/chat/reset` — after which the What's New pill (including its unseen dot, if applicable) SHALL be shown again. The unseen-dot indicator SHALL never render on the "Main Menu" control. The control's visible label SHALL read "🏠 Main Menu" (a home emoji leading the label, mirroring the "✨ What's new" pill; not "Restart"); its behaviour is unchanged.

In addition (CHO-273), **every** landing on the home / main-menu screen — including cold widget open with credentials present — SHALL request a fresh agent thread via `POST /api/chat/reset` so an 8h FinX session never rehydrates prior short-term memory into a new visit. The call remains fire-and-forget; failure SHALL NOT block rendering the home screen.

#### Scenario: Pill swaps on engagement
- **WHEN** the user taps a sticker or sends their first message
- **THEN** the What's New pill is replaced by the "Main Menu" control

#### Scenario: Main Menu returns to a clean home screen
- **WHEN** the user taps "Main Menu" mid-conversation (even while a reply is streaming)
- **THEN** the stream is aborted, the conversation clears to the greeting + stickers, the What's New pill returns, and the next message starts a fresh agent conversation

#### Scenario: Cold open starts a blank agent thread
- **WHEN** the widget opens with valid FinX credentials and shows the home screen
- **THEN** the frontend issues `POST /api/chat/reset` once for that session
- **AND** the next `/api/chat` turn uses a fresh empty thread (no prior turns)

#### Scenario: Reset failure degrades safely
- **WHEN** `POST /api/chat/reset` fails or times out
- **THEN** the UI still resets to the home screen and the next message simply continues the previous agent thread
