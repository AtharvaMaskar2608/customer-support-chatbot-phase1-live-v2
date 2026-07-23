# home-screen

## ADDED Requirements

### Requirement: Floating Main Menu control follows brand colours
The floating top-right Main Menu control SHALL use the FinX brand colours — a light-blue fill (token `#EEF3FD`) with blue text (token `#1D4FB8`) — rather than the black/inverted pill, keeping the 🏠 emoji. The control SHALL be self-contained (its own contained/rounded surface with the reserved top spacing) so it does not overlap the conversation content. In dark mode it SHALL use an equivalent legible brand treatment, preserving the existing guarantee that the control stays clearly visible against a dark surface.

#### Scenario: Main Menu uses brand colours
- **WHEN** a conversation is active and the Main Menu control renders
- **THEN** it shows the 🏠 emoji on a light-blue brand pill (`#EEF3FD` fill, `#1D4FB8` text), not the black pill

#### Scenario: Control does not cover the chat
- **WHEN** the conversation scrolls beneath the top-right control
- **THEN** the control reads as a self-contained element and does not visually sit on top of message content

#### Scenario: Visible in dark mode
- **WHEN** the widget renders in dark theme
- **THEN** the control uses a legible elevated brand treatment and stays clearly visible
