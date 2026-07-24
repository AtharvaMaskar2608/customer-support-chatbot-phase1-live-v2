# CHO-269: subtitle-text — design

## Context

Home empty state currently shows two subtitle lines (CHO-254):

- Line 1: `Fetch your reports instantly, explain charges and processes.`
- Line 2: `Files land right here in chat —` + FinX-blue `no email verification needed.`

CHO-269 collapses this to one sentence and restores a green bold callout on the verification phrase.

## Decision

Single `<p>` under the hero:

> Get your reports in chat, explain charges and processes - **no email verification needed**

- Hyphen with spaces (` - `), matching the Linear copy (not an em dash).
- Highlight span: `font-bold text-online dark:text-online-soft` — green + bold; inherits `text-sm leading-relaxed` from the parent.
- No trailing period on the highlighted phrase (matches Linear).

## Alternatives considered

- Keep two lines / FinX blue (CHO-254): rejected — product explicitly asked for the new single-line copy and green bold styling.
