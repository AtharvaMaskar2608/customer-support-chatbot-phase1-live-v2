# FinX API — intermittent connect stalls (IPv6/AAAA DNS)

**Status:** worked around on our side; **worth raising with the FinX/infra team** (their DNS behavior is the trigger).

## Symptom

Calls from our backend (Python `httpx`, async) to FinX hosts
(`mf.choiceindia.com`, `finx.choiceindia.com`) intermittently failed with
`ConnectTimeout` — in bursts (e.g. a run of requests all succeed, then a run all
stall for the full connect timeout, then recover). Surfaced in the UI as the
greeting degrading to "Hey there" and reports failing with `UPSTREAM_ERROR`.

## Diagnosis (evidence)

- `curl` to the same hosts **always** connects in ~20–50 ms, HTTP 200. So the
  servers and the network path are healthy.
- DNS returns **only A (IPv4) records** — e.g. `mf.choiceindia.com` →
  `13.234.218.1`, `65.0.228.182`. **No AAAA (IPv6) record**, and IPv6 is not
  routable from our host (`curl -6` hangs).
- Both IPv4 addresses connect fine individually via `curl --resolve`.
- Yet `httpx`'s async resolver still issues an **AAAA lookup** as part of
  `getaddrinfo`. Against FinX's DNS that AAAA query intermittently **hangs**
  (no answer, no fast NXDOMAIN), stalling the whole connect phase until timeout.
  `curl` avoids this in practice; the async stack does not.

Root cause is therefore the **AAAA DNS lookup stalling**, not the API, the
servers, or the credentials.

## Our workaround (in `backend/app/main.py`)

Force the httpx client to IPv4-only so it never issues the AAAA query:

```python
transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=2)
httpx.AsyncClient(transport=transport,
                  timeout=httpx.Timeout(..., connect=8.0))
```

`local_address="0.0.0.0"` binds the socket to `AF_INET`, so resolution is
IPv4-only and the hanging AAAA lookup is never made. Combined with a
transport-level connect retry and our own per-call retries in
`app/finx/client.py` / `app/finx/delivery.py`. After this change: 8/8 greeting
and 4/4 P&L calls succeeded where the same calls were failing ~50% before.

## Recommendation for the FinX/infra team

- Ideally FinX DNS should return a fast negative (NXDOMAIN / empty AAAA) for the
  IPv6 lookup instead of dropping it, so clients don't stall.
- Or publish AAAA records if IPv6 is intended.
- Either way, any async HTTP client (not just ours) hitting these hosts will see
  the same intermittent stalls until the DNS behavior is fixed.

_Observed 2026-07-18 during CHO-207 Wave 0 integration._
