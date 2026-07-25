# contract-notes-report-flow Specification

## Purpose
TBD - created by archiving change cho-208-210-report-flows. Update Purpose after archive.
## Requirements
### Requirement: Contract Notes selection flow
The Contract Notes flow SHALL collect a **date range** (presets Last trading day / Last 7 days / This month / Custom; future cap = **today**, no maximum-range limit), then present a **selection step** — a list of the client's contract notes for that range, each tappable to download. It is **download-only** (no email step). Delivered contract-note PDFs are **not** password-protected. A "Change dates" affordance SHALL appear only when the result carries **no data** — an empty range (upstream 204) or an error — and SHALL NOT appear alongside a successful result (a multi-note list or a single-note delivery). Choosing "Change dates" SHALL start a FRESH contract-notes flow as a new message (prompting for a new range); it MUST NOT re-open or mutate the existing card's date step in place.

#### Scenario: List and tap
- **WHEN** the user picks a date range that has multiple notes
- **THEN** a month-grouped list renders and tapping any note downloads that note's PDF, with no "Change dates" affordance on the successful list

#### Scenario: Single-note shortcut
- **WHEN** the range resolves to exactly one note
- **THEN** the flow skips the list and delivers that note directly, with no "Change dates" / "Other dates" affordance

#### Scenario: No notes
- **WHEN** the range has no notes (upstream 204)
- **THEN** the flow shows a friendly empty message with a "Change dates" affordance

#### Scenario: Change dates starts a new message
- **WHEN** the user taps "Change dates" after an empty result
- **THEN** a fresh contract-notes flow card appears as a new message asking for a new range, and the earlier message stays above unchanged

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

