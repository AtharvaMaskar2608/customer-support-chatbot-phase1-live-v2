# home-screen

## MODIFIED Requirements

### Requirement: Home screen layout per approved mock
The widget home screen SHALL render, top to bottom: a hero greeting, two subtitle lines ("Fetch your reports instantly, explain charges and processes." and "Files land right here in chat — no email verification needed." with the final phrase **"no email verification needed."** highlighted in FinX blue accent colour via `text-accent` / `text-accent-soft`, not online/green — per CHO-254), a section of quick-action chips rendered **without an eyebrow heading** (no "POPULAR RIGHT NOW" label), **paginated at four chips per page with navigation controls**, an **"or ask anything about FinX"** divider (hairline rules with centred label) rendered between the chip section and the composer, a rounded chat composer with a purple send button, and the compliance footer "Factual answers only — never investment advice". There SHALL be no header bar; the "What's new" control renders as a floating top-right overlay. Chat content carries enough top spacing that the greeting does not sit under the floating control.

#### Scenario: Chips render without the "Popular right now" heading
- **WHEN** the home screen loads with a valid session
- **THEN** the quick-action chips render directly under the subtitle lines with no "POPULAR RIGHT NOW" eyebrow label above them

#### Scenario: Divider renders above composer on home screen
- **WHEN** the home screen loads with a valid session
- **THEN** the text "or ask anything about FinX" renders between the chip section and the chat composer

#### Scenario: Full render with session
- **WHEN** the page loads with a valid session context
- **THEN** the greeting, subtitles, paginated chips (unlabeled), divider, composer, and footer render in order, with the "What's new" control floating at the top-right and no header

### Requirement: Quick-action chips fire predefined queries
The home-screen quick-action chips SHALL each submit their label (or trigger phrase) as a query through the chat composer; chips MUST NOT call tool APIs directly. The chip row is rendered from the flow registry, and a flow MAY opt out of the home chip row (via a `hideSticker` flag) while remaining reachable by composer keyword routing. The **Brokerage** flow SHALL NOT appear as a home chip. On the **landing screen**, chips SHALL be **paginated four per page** with prev/next or dot navigation so every non-`hideSticker` flow is reachable without implying the list is exhaustive on a single page.

#### Scenario: Chip tapped
- **WHEN** the user taps a quick-action chip (e.g. "Get my P&L")
- **THEN** the composer submits that chip's phrase as if typed by the user

#### Scenario: Brokerage is not a home chip
- **WHEN** the home screen renders
- **THEN** no Brokerage chip appears in the quick-action grid

#### Scenario: Brokerage stays reachable by typing
- **WHEN** the user types "what are my brokerage charges"
- **THEN** the brokerage flow runs and renders the rate card exactly as before

#### Scenario: Landing chips paginate four per page
- **WHEN** the home screen renders with more than four non-`hideSticker` flows registered
- **THEN** at most four chips are visible on the current page and navigation controls allow moving to additional pages until all flows are reachable

#### Scenario: Pagination navigation advances pages
- **WHEN** the user activates the next-page control on the landing chip row
- **THEN** the chip row shows the next page of up to four flows and the previous-page control becomes available
