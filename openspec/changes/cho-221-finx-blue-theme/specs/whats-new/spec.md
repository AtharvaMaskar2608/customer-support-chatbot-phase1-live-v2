# whats-new — delta

## MODIFIED Requirements

### Requirement: What's new modal per approved mock
Tapping the header "✨ What's new" pill SHALL open a card-style modal over the home screen containing: title "✨ What's new in Jini" with a close (✕) button, one row per item (emoji on a rounded tinted tile, bold title, gray description), a full-width accent-coloured (FinX blue, per `brand-theme`) "Got it" button, and the footer "Content updated remotely — no app release needed". Emoji glyphs match the product's emoji icon language (✨ header, per-item emoji from the payload).

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
