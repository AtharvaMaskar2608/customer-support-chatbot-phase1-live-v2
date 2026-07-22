# CHO-235: holdings-csv-cta — tasks

## 1. Promote the CTA

- [ ] 1.1 In `frontend/src/chat/datacards/HoldingsCard.tsx`, restyle `CsvButton` as a prominent full-width primary button (filled accent background, white text, download icon, rounded) — matching the "Expected output" mock on CHO-235
- [ ] 1.2 Label it "Download CSV — all {count} holdings" ("holding" when count === 1); pass the holding count (`d.totals.count` / `d.rows.length`) into the button
- [ ] 1.3 Place it as its own full-width action row (below the "Ask again anytime — prices refetch" note) rather than inline in the quiet footer; keep that freshness note
- [ ] 1.4 Preserve behaviour exactly: `downloadHoldingsCsv` (native bridge → Blob fallback) and the on-button feedback states (idle → busy "Saving…" → ok ✓ "Saved to downloads" → revert), restyled to sit on the primary button; the filename is never echoed into the conversation

## 2. Verification

- [ ] 2.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 2.2 Holdings card shows a clearly visible full-width "Download CSV — all N holdings" button (light + dark); tapping it saves the CSV and shows the on-button ✓ feedback; no new chat bubble
- [ ] 2.3 Screenshot before deploy (visible UI change)

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-235
- [ ] 3.2 `linear-connector` — summary comment + state on merge
