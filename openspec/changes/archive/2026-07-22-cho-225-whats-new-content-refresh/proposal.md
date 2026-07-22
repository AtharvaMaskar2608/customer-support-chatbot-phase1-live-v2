# CHO-225: whats-new-content-refresh

## Why

QA raised two requests against the What's New modal.

**Remove the footer line** "Content updated remotely — no app release needed" (`WhatsNewModal.tsx:119-121`). Worth stating plainly: **that claim is currently false in production.** `backend/Dockerfile:14` does `COPY content ./content`, baking `whats_new.json` into the image, and `docker-compose.yml` mounts no volume over it. The "read per request" comment in `whats_new.py:25` buys live edits only in local development against the working tree. In production, changing the copy requires a backend image rebuild and redeploy. Deleting the line removes a promise the system does not keep.

**Replace the two announcement items.** The tester's proposed copy was:

> Your P&L - Contract Note right here / PDF or Excel in chat, any period — no email verification.

Both claims in that second line are wrong. P&L is PDF-only — `report.py:154-166` hardcodes `.pdf`, `application/pdf`, and `"format": "PDF"`, with no format parameter on the endpoint; contract notes are PDF-only too (`contract_notes.py:415`). The **only** report offering Excel is Capital Gains, via `_FORMAT_SPEC` in `tax.py:53-68`. And "any period" contradicts the pickers: P&L and Ledger both enforce `minDate: '2018-01-01'` with `maxRangeYears: 2`. Shipping that copy would advertise a capability the product does not have, to customers of a broker — a support-ticket generator at best. The copy below is corrected to what the flows actually deliver.

## What Changes

- **Delete** the hardcoded footer paragraph from `WhatsNewModal.tsx`. (Whether to *make* remote content genuinely remote — volume-mount or externalise `content/` — is deliberately out of scope here; it overlaps CHO-219's deploy work and is flagged as a follow-up rather than bundled in.)
- **Rewrite the announcement items** in `backend/content/whats_new.json` to three entries:
  1. **Your P&L and contract notes, right here** — "Delivered in chat as a PDF — no email verification."
  2. **Ask, don't search** — "Charges, processes, settlements"
  3. **Capital Gain report in Excel** — "Ask for FY 25-26 — delivered in-chat, tax-filing ready." *(retained: this is the one true Excel claim, and deleting it would drop a real differentiator)*
- **Add one icon glyph** so item 2 keeps the tinted-tile design. `WhatsNewModal.tsx:13-17` maps emoji → inline SVG so the glyph can be tinted to match its tile; only 📄, 🎫, 🎟️ are mapped, and anything else silently degrades to a raw emoji on a neutral grey tile — the exact failure the component's header comment says the map exists to prevent. `SparkleIcon` already exists in `icons.tsx` and is Jini's own mark, so ✨ → `SparkleIcon` plus a blue tint entry keeps the row on-system. This is why "text only" is not text-only.
- **Bump `version`** in `whats_new.json` (`2026-07-18.1` → `2026-07-20.1`). Without it, `useWhatsNew.ts:103` gates the unseen dot on `version !== seenVersion`, so every user who already dismissed the current version would receive the new copy silently and never see it.

## Capabilities

### Modified Capabilities

- `whats-new`: the "per approved mock" requirement drops the remote-content footer line; the tinted-tile requirement is extended to state that every shipped item's emoji must have a mapped glyph (no neutral-tile fallback in shipped content); and a new requirement makes the version bump mandatory whenever item content changes.

## Impact

- Frontend: `frontend/src/WhatsNewModal.tsx` (delete footer, add one `GLYPHS` entry and one `TINTS` entry).
- Backend content: `backend/content/whats_new.json` (three items + version bump). No backend code change.
- Both halves need a redeploy to reach production — the frontend for the code change, the backend image for the content. They are not independently shippable today, which is precisely the gap the deleted line was papering over.
- No API contract change; the `{version, items:[{emoji, tint, title, description}]}` shape is unchanged.
- **Copy sign-off required before implementation** — the corrected first item is a rewrite of the tester's text, not a transcription.
- Linear: CHO-225 · branch `cho-225-whats-new-content-refresh`.
