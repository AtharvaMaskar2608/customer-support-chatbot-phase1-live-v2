"""CHO-211 data-card flows — answer-in-chat data endpoints.

Unlike the report flows (the answer is a PDF, chat is the courier), these
endpoints return the answer itself: normalized, derived, PII-minimized JSON
the frontend renders as an interactive card. One module per flow, mirroring
`app.reports`: holdings, money (merged pay-in/pay-out), brokerage.
"""
