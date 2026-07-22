# whats-new

## MODIFIED Requirements

### Requirement: What's new modal per approved mock
The modal SHALL render the announcement items from the fetched content as a titled list with tint-matched icon tiles, a close control, and a primary dismiss button. It SHALL NOT claim that content updates reach production without a release, since the content file is baked into the backend image and editing it requires a rebuild and redeploy.

#### Scenario: Modal lists the fetched items
- **WHEN** the customer opens the What's New modal
- **THEN** each item renders with its icon tile, title, and description, above a single dismiss button

#### Scenario: No remote-content claim
- **WHEN** the modal renders
- **THEN** no footer text asserts that content is updated remotely or that no app release is needed

## ADDED Requirements

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
