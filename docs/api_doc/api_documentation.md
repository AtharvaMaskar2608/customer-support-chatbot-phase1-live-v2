# API Documentation — Choice Jini (Phase 1)

Upstream Choice India APIs consumed by the chatbot backend.

**Convention:** for each API we document only the fields we actually consume,
even when the upstream response contains more. If we later need another field,
it gets added here first.

## Shared auth context

**Transport (how FinX hands data over):** the host page (FinX web / app
webview) opens the chat page with query params — `userId` (encrypted),
`sessionId`, `accessToken`, `isDarkTheme`, `platform`, `obStatus`, and later a
screen/page name.

**What the system actually operates on internally:**

| Input       | Mock value available | Notes                                        |
|-------------|----------------------|----------------------------------------------|
| `USER_ID`   | yes (`X008593`)      | **Decrypted** client code; the `userId` query param is its encrypted form |
| `session_id`| yes                  | ULID-style token                             |
| SSO token   | yes                  | RS256 JWT, `iss: sso.choiceindia.com`, 8-hour lifetime (`exp` = `auth_time` + 8h) |
| `platform`  | trivially mockable   | `android` / `ios` / `web`                    |
| `page`      | not used yet         | Screen name the user opened the chat from; reserved for context-aware behavior later |

`userId` decryption is handled by a Choice service — our system always
operates on the decrypted `USER_ID` and treats it as valid (guaranteed by the
host app; invalid credentials simply fail upstream). `obStatus` has no
special handling — stored, never acted on.

> Never commit real tokens or client codes' credentials to this repo. Mock
> credentials live in an untracked `.env`. Note the 8-hour SSO token lifetime:
> mock tokens go stale the same day they are minted.

---

## 1. Get Profile

Resolves the authenticated user's identity for the greeting
("Hey \<first name\> — what do you need?").

**Status:** verified live on 2026-07-18 (HTTP 200 with real credentials).

| Item         | Value                                                      |
|--------------|------------------------------------------------------------|
| Method       | `POST`                                                     |
| URL          | `https://mf.choiceindia.com/api/v2/investor/profile/extended` |
| Header       | `authorization: <SSO JWT>` (raw token, no `Bearer` prefix) |
| Header       | `from: <session token>`                                    |
| Header       | `content-type: application/json`                           |
| Request body | `{"InvCode": "<USER_ID>"}` (decrypted client code)         |

```bash
curl -s https://mf.choiceindia.com/api/v2/investor/profile/extended \
  -H "authorization: $FINX_SSO_JWT" \
  -H "from: $FINX_FROM_HEADER" \
  -H "content-type: application/json" \
  -d "{\"InvCode\": \"$FINX_TEST_CLIENT_ID\"}"
```

### Response shape (redacted sample)

```json
{
  "Status": "Success",
  "Response": {
    "InvCode": "X0xxxxx",
    "FirstHolderName": "FIRSTNAME MIDDLENAME LASTNAME",
    "...": "many more fields — ignored"
  },
  "Reason": ""
}
```

### Fields we consume

| Field                       | Type   | Used for                                                        |
|-----------------------------|--------|-----------------------------------------------------------------|
| `Response.FirstHolderName`  | string | Greeting. **No dedicated first-name field exists** — the value is the full name in caps; derive first name as the first whitespace-separated token, title-cased (`"PRITAM NITIN WAVHAL"` → `"Pritam"`). |

All other fields are ignored and **must never be stored or logged**. The raw
response is PII-heavy (PAN, DOB, full address, email, mobile, bank account
numbers) — log only status codes, never response bodies.

### Verified behavior

- Missing/invalid `authorization` → **401**. Treat 401 as expired/invalid SSO
  token (8h lifetime) and degrade to a non-personalized greeting.
- The `from` header is **not enforced** by this endpoint (200 without it), but
  we send it anyway per Choice's convention.
- `Response.OnboardFlag` returns `"C"` for our test user — matches the
  `obStatus=C` query param, confirming `obStatus` mirrors onboarding state.

### Notes

- Unknown/invalid `InvCode` is not a case we handle specially: the host app
  guarantees a valid USER_ID, and invalid credentials simply make the API
  fail — treated the same as any upstream error (degrade gracefully).
