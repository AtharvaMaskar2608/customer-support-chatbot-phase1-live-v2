"""Live routing / recall eval harness (CHO-276).

NOT part of `uv run pytest` (`pyproject.toml` pins `testpaths = ["tests"]`).
The cases make one real model call each, so they run under their own command:

    uv run python -m evals.runner

With no `ANTHROPIC_API_KEY` every case is reported as skipped and the runner
exits 0 — a missing key must never fail anybody's run. See `README.md`.
"""
