"""Per-flow report routers.

Each report flow (Ledger, Tax, …) lives in its own module here as a FastAPI
`APIRouter` that mirrors the Wave-0 P&L route in `app.report`: a per-flow
request model, an endpoint-specific upstream body mapping, the shared
`FinxClient` call, and the shared delivery/PII layer. The shared download
endpoint (`GET /api/report/file/{token}`) is owned by `app.report` and reused
by every flow — it is never redefined here.
"""
