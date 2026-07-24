# CHO-269: subtitle-text — tasks

## 1. Subtitle copy (`EmptyState.tsx`)

- [x] 1.1 Replace the two subtitle `<p>`s with one line: `Get your reports in chat, explain charges and processes -` + highlighted `no email verification needed`
- [x] 1.2 Style the highlight with `font-bold text-online dark:text-online-soft` (green + bold; same font size as surrounding text)

## 2. Spec

- [x] 2.1 OpenSpec change delta for `home-screen` subtitle copy + highlight colour

## 3. Verification

- [x] 3.1 `cd frontend && ./node_modules/.bin/tsc --noEmit` clean; `npm run build` + `npm run lint` pass
- [x] 3.2 Code check: single subtitle; only “no email verification needed” uses green + bold tokens

## 4. Ship & sync

- [ ] 4.1 Push branch + draft PR (`Fixes CHO-269`)
- [ ] 4.2 Linear summary when MCP/API available (blocked in this cloud run)
