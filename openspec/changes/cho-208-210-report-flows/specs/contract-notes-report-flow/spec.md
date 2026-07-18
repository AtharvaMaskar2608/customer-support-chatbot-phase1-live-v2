# contract-notes-report-flow

## ADDED Requirements

### Requirement: Contract Notes selection flow
The Contract Notes flow SHALL collect a **date range** (presets Last trading day / Last 7 days / This month / Custom; future cap = **today**, no maximum-range limit), then present a **selection step** — a list of the client's contract notes for that range, each tappable to download. It is **download-only** (no email step). Delivered contract-note PDFs are **not** password-protected.

#### Scenario: List and tap
- **WHEN** the user picks a date range that has multiple notes
- **THEN** a month-grouped list renders and tapping any note downloads that note's PDF

#### Scenario: Single-note shortcut
- **WHEN** the range resolves to exactly one note
- **THEN** the flow skips the list and delivers that note directly

#### Scenario: No notes
- **WHEN** the range has no notes (upstream 204)
- **THEN** the flow shows a friendly empty message with a "Change dates" affordance

### Requirement: Contract Notes list presentation
Each listed note SHALL show its trade date and segment; a segment/exchange badge (NSE·BSE / MCX) SHALL appear only when a single date has two notes (to disambiguate). The list paginates ("Show more") beyond an initial set.

#### Scenario: Badge only on collision
- **WHEN** a date has two notes (e.g. equity + commodity)
- **THEN** each shows its disambiguating badge; single-note dates show none

### Requirement: file_id is never exposed
The upstream `file_id` download handle SHALL never reach the client. The list hands back an opaque, per-session, short-TTL id that the backend maps to the `file_id` server-side; download resolves it. Every call binds to the authenticated session's client code (IDOR defense) and never trusts a client code from input.

#### Scenario: Opaque ids only
- **WHEN** the list response is returned to the browser
- **THEN** no `file_id` appears in it — only opaque ids

#### Scenario: Two-step upstream auth
- **WHEN** a note is downloaded
- **THEN** the list call uses `authorization: <SessionId>` and the download call uses `authorization: Session <SessionId>` (the prefixed form), fetched server-side
