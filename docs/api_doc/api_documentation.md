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

---

## 2. P&L Report — `GetGlobalPNLPDF`

Generates the Profit & Loss report (PDF only, PAN-password-protected) and
either streams it back for download or emails it to the registered address.
This is the reference report flow; Ledger / Tax / Contract Notes reuse the same
client, router, and delivery layer (Wave 1).

**Status:** upstream contract live-confirmed in the FinX Android capture
(`docs/finx_android_api_reference.html`, captured 2026-07-16); our proxy is
verified against mocked upstreams. Live end-to-end run against FinX is pending
(change task 6.1).

**Auth is per-endpoint, not per-app.** This is a `.NET` middleware report
endpoint, so it authenticates with the **SessionId** in `authorization` — *not*
the SSO JWT (the JWT authenticates the MIS/CML endpoint instead). The `from`
header is a client build tag, not auth and not a source router.

| Item         | Value                                                             |
|--------------|-------------------------------------------------------------------|
| Method       | `POST`                                                            |
| URL          | `https://api.choiceindia.com/api/middleware/GetGlobalPNLPDF`      |
| Header       | `authorization: <SessionId>` (the session token, **not** the JWT) |
| Header       | `from: <build tag>` (non-authenticating, any stable value)        |
| Header       | `content-type: application/json`                                  |

### Upstream request body — fields we send (`PnlPdfRequest`)

| Field        | Type   | Value we send                                              |
|--------------|--------|------------------------------------------------------------|
| `ClientId`   | string | Session-derived client code (from the authenticated session, **never** the request body — IDOR defense) |
| `UserId`     | string | `== ClientId`                                              |
| `Group`      | string | `Cash` (Equity) · `Derv` (F&O) · `Comm` (Commodity). Backend-only codes; the customer only ever sees Equity/F&O/Commodity |
| `FromDate`   | string | `YYYY-MM-DD`                                               |
| `ToDate`     | string | `YYYY-MM-DD`                                               |
| `RequestFor` | int    | `0` = download · `1` = email. **Hardcoded per endpoint** — do not centralize (Tax uses `2` for download) |
| `With_Exp`   | bool   | `true` — charges included, surfaced as "incl. charges"     |
| `SessionId`  | string | Same session token as the `authorization` header          |

### Response shapes — fields we consume (`FileDeliveryResponse`)

`Response` is polymorphic; branch on delivery mode, never on `Reason`.

```json
// download (RequestFor 0) — 200
{ "Status": "Success", "Response": "https://client-report.choiceindia.com/PDFReports/PNLReport_<id>_<ClientId>.pdf", "Reason": "" }

// email (RequestFor 1) — 200; Response leaks the registered email, UPPERCASED
{ "Status": "Success", "Response": "PnL Report mail sent successfully to <REGISTERED_EMAIL>", "Reason": "" }

// no data — 200 (NOT 401)
{ "Status": "Fail", "Response": null, "Reason": "Data not found." }
```

| Field       | Type          | Used for                                                     |
|-------------|---------------|--------------------------------------------------------------|
| `Status`    | string        | Success detection: `"Success"` → OK, anything else → `NO_DATA`. Business failures are HTTP 200 — branch on this, never on `Reason` (wording differs across endpoints). |
| `Response`  | string / null | Download: a report **URL** — sensitive & effectively unauthenticated, fetched server-side and never surfaced/logged. Email: a confirmation string — the leaked email is masked before display. |

`Reason` is **never** inspected or logged.

### Two-layer error mapping

| Upstream                              | Our result       | Client HTTP |
|---------------------------------------|------------------|-------------|
| HTTP `401`                            | `AUTH_EXPIRED`   | `401`       |
| HTTP `204`                            | empty            | `404 NO_DATA` |
| HTTP `200`, body `Status` != Success  | `NO_DATA`        | `404`       |
| non-2xx / bad JSON / transport error  | `UPSTREAM_ERROR` | `502`       |

### Our proxy contract (browser ↔ backend)

The browser never calls FinX. It calls our proxy, which owns the credential
routing, error mapping, and the delivery/PII layer.

- **`POST /api/report/pnl`**
  - Request headers: `Authorization: <SSO JWT>`, `X-Session-Id: <session token>`,
    `X-User-Id: <client code>` (same triple as `/api/greeting`).
  - Request body: `{"segment": "Equity"|"F&O"|"Commodity", "fromDate": "YYYY-MM-DD", "toDate": "YYYY-MM-DD", "delivery": "download"|"email"}`.
    Any client code smuggled into the body is ignored; the client code sent
    upstream comes only from `X-User-Id`.
  - `200` download → `{"delivery":"download","file":{"name":"PnL_<Segment>_<from>_to_<to>.pdf","sizeLabel":"<e.g. 214 KB>","format":"PDF","passwordProtected":true},"fileToken":"<opaque short-lived id>"}`
  - `200` email → `{"delivery":"email","emailMasked":"san***@gmail.com"}`
  - `400 MISSING_CREDENTIALS` · `401 AUTH_EXPIRED` · `404 NO_DATA` · `422` (bad body) · `502 UPSTREAM_ERROR`
- **`GET /api/report/file/{fileToken}`** → streams the PDF bytes
  (`Content-Type: application/pdf`, `Content-Disposition: attachment`). Requires
  the `X-Session-Id` that created the token; the token is opaque, short-TTL, and
  in-memory. The upstream artifact is fetched server-side at token-creation time
  and the raw upstream URL is never persisted, returned, or logged.

### PII rules

- The report URL / email address are never returned raw to the client or
  logged. Download returns only an opaque token; the artifact is fetched
  server-side. Email returns only a masked address (`san***@gmail.com`).
- Logs carry status code + timing (+ the endpoint key) only — no bodies, URLs,
  emails, client codes, session tokens, or JWTs. `httpx`'s own request-line
  logging (which includes the full URL) is silenced for this reason.

> No real tokens, client codes, emails, or report URLs appear in this repo. All
> examples above use placeholders.

---

## 3. Ledger Report — `GetLedgerDetailsPDF`

**Status:** verified live 2026-07-18 (real PDF). Mirrors P&L; PDF only, no format.

| Item   | Value |
|--------|-------|
| Method / URL | `POST /api/middleware/GetLedgerDetailsPDF` (finx.choiceindia.com) |
| Auth   | `authorization: <SessionId>` (raw, no prefix) · `from: <build tag>` |
| Delivery | download / email (PDF). Delivered PDF is **PAN-password-protected**. |

### Upstream request body — fields we send (`LedgerPdfRequest`)

| Field | Notes |
|-------|-------|
| `ClientId` / `LoginId` | both = session client code (from `X-User-Id`, never body) |
| `Group` | fixed `"GROUP1"` (uppercase) |
| `Margin` | `0` = Normal · `1` = MTF *(MTF discriminator CONFIRM-pending)* |
| `FromDate` / `ToDate` | `YYYY-MM-DD` |
| `RequestFor` | **0 = download · 1 = email** (hardcoded per endpoint) |
| `SessionId` | matches the header |

### Our proxy contract

`POST /api/report/ledger` — headers `Authorization` / `X-Session-Id` / `X-User-Id`;
body `{"book":"Normal"|"MTF","fromDate","toDate","delivery":"download"|"email"}`.
Response identical to P&L (`{delivery, file, fileToken}` / `{delivery:"email", emailMasked}`;
401 `AUTH_EXPIRED` / 404 `NO_DATA` / 502 `UPSTREAM_ERROR`). Same `GET /api/report/file/{token}`.

---

## 4. Capital Gains / Tax Report — `GetTaxReportPDF`

**Status:** verified live 2026-07-18 (real PDF + Excel). The **only** endpoint with a format choice.

| Item   | Value |
|--------|-------|
| Method / URL | `POST /api/middleware/GetTaxReportPDF` (finx.choiceindia.com) |
| Auth   | `authorization: <SessionId>` · `from: <build tag>` |
| Delivery | download / email · **PDF or Excel** |

### Upstream request body — fields we send (`TaxReportRequest`)

| Field | Notes |
|-------|-------|
| `ClientId` | session client code (never body) |
| `FinYear` | `"YYYY-YYYY"` — **dynamic** window (current + last 2 FYs; never hardcode) |
| `RequestFor` | **2 = download · 1 = email** — the download value forks (2 here, not 0) |
| `FileFormat` | `1` = PDF · `2` = Excel |
| `SessionId` | matches the header |

Excel URL carries a `_<epoch>.xlsx` suffix; we name/label the file by `FileFormat`.
"No data" `Reason` is `"Data not available."` — branch on `Status`, never string-match.

### Our proxy contract

`POST /api/report/tax` — body `{"finYear","format":"PDF"|"Excel","delivery"}`. Response as P&L;
`file.format` and filename extension (`.pdf`/`.xlsx`) set from the chosen format.

---

## 5. Contract Notes — `/report/contract` + `/contract/download`

**Status:** verified live 2026-07-18 (list + real PDF). Two-step; **download only** (no email).

| Item   | Value |
|--------|-------|
| List   | `POST /middleware-go/report/contract` (finx.choiceindia.com) · `authorization: <SessionId>` |
| Download | `POST /middleware-go/contract/download` (api.choiceindia.com) · `authorization: Session <SessionId>` (note the `Session ` prefix) · returns raw PDF bytes |
| Delivery | download only · PDFs are **NOT** password-protected |

### Fields we consume (`ContractNote`)

| Field | Notes |
|-------|-------|
| `date` | `DDMMYYYY` (trade date) → displayed `D Mon YYYY` |
| `file_id` | ~88-char download handle — **sensitive, server-side only, never surfaced** |
| `group` | segment hint (only `Grp1`=Equity confirmed live) |
| `invoice_number` | contract-note number |

List no-data = HTTP **204** (`{notes: []}` to the client). The chain authorizes on body
`client_id` only (**IDOR**) — we bind every call to the authenticated session and never
accept a client code from input.

### Our proxy contract

- `POST /api/report/contract-notes/list` — body `{"fromDate","toDate"}` → `{"notes":[{id,date,segment,badge,month}]}`. `id` is an **opaque per-session token** mapped to `file_id` server-side; `file_id` never leaves the backend.
- `POST /api/report/contract-notes/download` — body `{"id"}` → `{delivery:"download", file, fileToken}` (`passwordProtected:false`). Same `GET /api/report/file/{token}`.

## 6. Holdings — `COTI/V1/Holdings`

**Status:** verified live 2026-07-18. Data endpoint (rendered in chat, no file).

| Item | Value |
|------|-------|
| Call | `POST /COTI/V1/Holdings` (**finxomne**.choiceindia.com) · `authorization: Session <SessionId>` (prefix) |
| Auth note | The web app also sends `ssotoken`, body `accessToken` (FINX-issued JWT) and `fingerprint` — **none are enforced** (probed live: Session header alone → 200). |
| Body | `{"UserId","UserCode","GroupId":"HO","SessionId","Status":""}` — **required** (empty body → upstream 404). All values session-derived. |

### Fields we consume (per scrip in `Response.lDictHoldingData`, keyed by ISIN)

| Field | Notes |
|-------|-------|
| `Sym` | e.g. `BANKBARODA-EQ` — `-EQ` suffix stripped for display |
| `Name` | full scrip name |
| `Q` | quantity held |
| `ABP` | avg buy price, **rupees** |
| `LTP` / `CP` | last traded / previous close price, **PAISE — divide by 100** (confirmed against FinX's own CSV export) |
| `LUT` | `DD-MM-YYYY HH:MM:SS` — max across scrips = the card's freshness stamp |

Empty portfolio = `Status: Success` with empty `lDictHoldingData` dict.

### Our proxy contract

- `POST /api/data/holdings` (headers only, no body) → `{"kind":"ok","asOf":"<ISO max LUT>","rows":[{sym,name,qty,abp,ltp,current,invested,pnl,pnlPct,day,dayPct,alloc}…] sorted by current desc, "totals":{current,invested,pnl,pnlPct,day,dayPct,count}}`. All derivation server-side. Empty → `{"kind":"empty"}`.

## 7. Pay-In / Pay-Out — `GetPayInTxnRpt` + `GetPayOutTxnRpt`

**Status:** verified live 2026-07-18 (72 merged transactions). Data endpoints, merged into one timeline.

| Item | Value |
|------|-------|
| Calls | `POST /api/middleware/GetPayInTxnRpt` and `…/GetPayOutTxnRpt` (finx.choiceindia.com) · `authorization: <SessionId>` (bare) |
| Body | `{"UserID","FromDate","ToDate","Segment":"","Status":"","StartPos":0,"NoOfRecords":500}` · default period FY-start → today+7 |
| Paging | `Response.TotalCount[0].TotalRecords` |

### Fields we consume (per txn in `Response.PayInTxn[]` / `Response.PayOutTxn[]`)

| Field | Notes |
|-------|-------|
| `Amount` | rupees |
| `Status` | **mixed casing upstream** (`SUCCESS` vs `Success`/`CANCELLED`) → normalized case-insensitively to `SUCCESS\|PENDING\|FAILURE\|CANCELLED` |
| `RequestedDateTime` | **two formats** (ISO-`T` pay-in, space-separated pay-out) → ISO 8601 |
| `ModeOfPayment` | pay-in only (`UPI`/`NB`/empty) |
| `DepositBankName` (in) / `ClientBankName`+`ClientBankAccNo` (out) | masked to bank + last-4 (`ICICI ••7280`, `Bank ••8829`) |
| `VoucherNo` | reference shown in detail |
| `Reason` | pay-out only — human-readable, **displayed verbatim, never branched on** |

**Dropped (PII/internal):** `ClientName`, full account numbers, `JiffyTransactionId`, `AtomReferenceNo`, `Search_All_Levels` (internal branch/employee hierarchy). Upstream quirks noted for FinX: `ClientCode` arrives as `'X008593` (Excel-escape artifact); empty-date sentinels differ (`1900-01-01…` vs `""`).

### Our proxy contract

- `POST /api/data/money` (headers only) → fetches both directions **concurrently**, returns `{"kind":"ok","txns":[{dir,amt,st,dt,mode,dest,ref,rsn}…] newest-first, "counts":{…}, "landed":{"in","out"} (SUCCESS only), "totalRecords":{"in","out"}}`; one direction failing → successful side + `"partial":true`.

## 8. Brokerage Slab — `get-brokerage-slab`

**Status:** shape verified from live capture 2026-07-18 (endpoint needs a **fresh SSO JWT**). Data endpoint.

| Item | Value |
|------|-------|
| Call | `POST /middleware-go/v2/get-brokerage-slab` (**api**.choiceindia.com) · `authorization: <raw SSO JWT>` |
| Body | `{"ClientID"}` — slabs are **per-client**; never hardcode groupings |

### Fields we consume (`Response[]`)

| Field | Notes |
|-------|-------|
| `title` | segment group (Equity / Derivative / Commodity / Currency) |
| `list[].title` | line item (Intraday, Stock Future, …) |
| `list[].desc` | rate text (e.g. `₹1.00 for trade value of 10 thousand`, `₹20.00 per order`) — parsed client-side for rate clustering, rendered verbatim on parse failure |

### Our proxy contract

- `POST /api/data/brokerage` (headers only) → `{"kind":"ok","groups":[{title,list:[{title,desc}]}]}` passthrough (no PII) after the field-based `Status` gate.
