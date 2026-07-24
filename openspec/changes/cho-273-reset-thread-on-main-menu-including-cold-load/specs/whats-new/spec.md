## MODIFIED Requirements

### Requirement: Dual-purpose header pill (What's new / Main Menu)
The "What's new" pill SHALL be shown only while the widget is on the home screen (greeting + stickers). From the moment the user engages (sticker tap or first composer submit) the same slot SHALL show a **"Main Menu"** control instead, for the life of the conversation. Tapping "Main Menu" SHALL return the widget to the home screen — clearing the conversation, aborting any in-flight agent stream, and requesting a fresh agent thread via `POST /api/chat/reset` — after which the What's New pill (including its unseen dot, if applicable) SHALL be shown again. The unseen-dot indicator SHALL never render on the "Main Menu" control. The control's visible label SHALL read "🏠 Main Menu" (a home emoji leading the label, mirroring the "✨ What's new" pill; not "Restart"); its behaviour is unchanged.

In addition (CHO-273), **every** landing on the home / main-menu screen — including cold widget open with credentials present — SHALL request a fresh agent thread via `POST /api/chat/reset` so an 8h FinX session never rehydrates prior short-term memory into a new visit. The call remains fire-and-forget; failure SHALL NOT block rendering the home screen.

#### Scenario: Cold open starts a blank agent thread
- **WHEN** the widget opens with valid FinX credentials and shows the home screen
- **THEN** the frontend issues `POST /api/chat/reset` once for that session
- **AND** the next `/api/chat` turn uses a fresh empty thread (no prior turns)

#### Scenario: Main Menu still resets
- **WHEN** the user taps "Main Menu" during a conversation
- **THEN** the UI returns to home and `POST /api/chat/reset` runs (same as CHO-216)

#### Scenario: Reset failure does not block home
- **WHEN** `POST /api/chat/reset` fails or times out
- **THEN** the home screen still renders; the next message MAY continue the previous thread (degraded, never blocking)
