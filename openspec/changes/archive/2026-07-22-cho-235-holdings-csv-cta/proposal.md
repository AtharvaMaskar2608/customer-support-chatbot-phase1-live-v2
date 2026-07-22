# CHO-235: holdings-csv-cta

## Why

On the Holdings card the **Download CSV** action is a quiet text link in the footer (small accent text next to the "prices refetch" note). Testers miss it. Product wants it to be an obvious, prominent call-to-action — matching the mock: a full-width filled-accent button reading "⬇ Download CSV — all N holdings". Only the CSV CTA changes; the rest of the card is untouched.

## What Changes

- Promote the Holdings **Download CSV** control from a quiet footer text-link to a **prominent full-width primary button** (filled accent, download icon, clear label). Per the mock the label includes the holding count: **"Download CSV — all N holdings"** (singular "holding" when N = 1).
- Keep all existing behaviour: client-side CSV build, native-host bridge first (CHO-230) then browser Blob fallback, and the on-button feedback (spinner "Saving…" → green ✓ "Saved to downloads" → revert). The filename is still never echoed into the chat.
- Frontend-only. No backend, API, or contract change.

## Capabilities

### Modified Capabilities

- `holdings-flow`: the CSV export control SHALL render as a prominent full-width primary button labelled with the holding count, not a quiet footer link; behaviour (client-side build, on-button feedback, no filename echo) is unchanged.

## Impact

- Frontend only: `frontend/src/chat/datacards/HoldingsCard.tsx` (`CsvButton` → primary button; label includes count; moved out of the quiet `CardFooter` row into its own full-width action row).
- The CSV builder (`holdingsCsv.ts`), bridge delivery, and feedback timing are unchanged.
- No test impact expected; `tsc` + build are the gates.
- Ships as a new frontend image — visible UI change, so a screenshot review before deploy is warranted.
- Linear: CHO-235 · branch `cho-235-holdings-csv-cta`.
