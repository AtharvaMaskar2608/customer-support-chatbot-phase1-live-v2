"""The sweep runner (CHO-276 · task 4).

    uv run python -m evals.runner                     # both arms, 3 attempts
    uv run python -m evals.runner --case E1 --attempts 1
    uv run python -m evals.runner --arm off

What it does:

1. Runs every case in BOTH curation-flag states, `--attempts` times each, and
   records per-attempt pass/fail plus the model usage tracing captured
   in-process (input / output / cache-read / cache-creation tokens, priced to INR
   by `app.agent.trace_cost` — the production cost model).
2. Labels the sweep a **baseline** when the curation flag does not exist yet.
   `AGENT_CONTEXT_CURATION` lands with CHO-271; until then both arms are
   identical by construction, which is intended and is why this harness does not
   block on curation. Detection scans the `app` package for the env-var name, so
   it starts reporting `comparison` the moment CHO-271 lands, whatever the flag
   reader ends up being called.
3. Evaluates fixed thresholds — hard-fail cases 3/3, everything else >= 2/3, no
   regression of the flag-on arm against flag-off, and ZERO abstention matches
   anywhere — and exits non-zero when any is missed.
4. Writes `evals/reports/routing-evals-<ISO>.json` plus a markdown twin.

Two guarantees about the exit code:

* No `ANTHROPIC_API_KEY` ⇒ every case is recorded as skipped, a report is still
  written, and the process exits **0**. A gate that fails on a laptop without a
  key trains people to ignore it.
* Nothing here reaches FinX, Freshdesk, or Postgres — the harness blocks
  outbound HTTP outright, and the report carries the blocked-attempt count so
  "no Freshdesk request was issued" is an observation, not a claim.

Report hygiene: no secret and no assistant text is ever written. Reports record
case ids, pass counts, failure reasons drawn from `assertions`' own vocabulary,
the tool names/inputs a case asserted on, and token totals. The writer refuses
to emit a file that contains the API key.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

from app import config

from evals import harness
from evals.cases import ALL_CASES, CASES_BY_ID, PYTEST_ONLY_CASES

CURATION_ENV = "AGENT_CONTEXT_CURATION"
ARMS = ("off", "on")
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# Merge-gate thresholds (spec: "Explicit merge gate thresholds").
HARD_FAIL_PASS_RATE = 1.0
DEFAULT_MIN_PASS_RATE = 2.0 / 3.0


# --- the curation flag -------------------------------------------------------


def curation_flag_exists() -> bool:
    """True once something in `app/` reads `AGENT_CONTEXT_CURATION`.

    Deliberately a source scan rather than a `hasattr` on a guessed function
    name: CHO-271 owns the reader, and this must not need editing when it lands.
    """
    app_root = Path(config.__file__).resolve().parent
    for path in app_root.rglob("*.py"):
        try:
            if CURATION_ENV in path.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


# --- one attempt -------------------------------------------------------------


def run_attempt(case: harness.Case) -> harness.CaseOutcome:
    try:
        return case.run()
    except harness.HarnessError as exc:
        return harness.CaseOutcome(
            passed=False,
            failures=[f"harness-error:{exc}"],
            observed={},
            usage=harness.Usage(),
            abstained=False,
            error=f"harness-error:{exc}",
        )
    except Exception as exc:  # noqa: BLE001 — an attempt must never kill a sweep
        return harness.CaseOutcome(
            passed=False,
            failures=[f"exception:{type(exc).__name__}"],
            observed={},
            usage=harness.Usage(),
            abstained=False,
            error=f"exception:{type(exc).__name__}",
        )


def run_arm(
    cases: Iterable[harness.Case], *, arm: str, attempts: int, quiet: bool
) -> dict:
    """Every case, `attempts` times, with the curation flag set for this arm."""
    previous = os.environ.get(CURATION_ENV)
    os.environ[CURATION_ENV] = "1" if arm == "on" else "0"
    results: dict[str, dict] = {}
    try:
        for case in cases:
            outcomes = []
            for index in range(attempts):
                outcome = run_attempt(case)
                outcomes.append(outcome)
                if not quiet:
                    status = "pass" if outcome.passed else "FAIL"
                    detail = "" if outcome.passed else "  " + "; ".join(outcome.failures)
                    print(
                        f"  [{arm}] {case.id} attempt {index + 1}/{attempts}: "
                        f"{status}{detail}",
                        flush=True,
                    )
            results[case.id] = _aggregate(case, outcomes, attempts)
    finally:
        if previous is None:
            os.environ.pop(CURATION_ENV, None)
        else:
            os.environ[CURATION_ENV] = previous
    return results


def _aggregate(
    case: harness.Case, outcomes: list[harness.CaseOutcome], attempts: int
) -> dict:
    passes = sum(1 for outcome in outcomes if outcome.passed)
    usage = harness.Usage()
    for outcome in outcomes:
        usage = usage.add(outcome.usage)
    first_failure = next(
        (outcome for outcome in outcomes if not outcome.passed), None
    )
    elapsed = [
        outcome.seed_to_probe_seconds
        for outcome in outcomes
        if outcome.seed_to_probe_seconds is not None
    ]
    return {
        "attempts": attempts,
        "passes": passes,
        "passRate": round(passes / attempts, 3) if attempts else 0.0,
        "abstentions": sum(1 for outcome in outcomes if outcome.abstained),
        "firstFailure": (
            {
                "attempt": outcomes.index(first_failure) + 1,
                "failures": first_failure.failures,
                "observed": first_failure.observed,
            }
            if first_failure is not None
            else None
        ),
        "observed": [outcome.observed for outcome in outcomes],
        "seedToProbeSeconds": elapsed,
        "usage": usage.as_dict(),
    }


# --- thresholds --------------------------------------------------------------


def evaluate_thresholds(report: dict) -> list[str]:
    """Every threshold miss, as short strings. Empty ⇒ the gate passes."""
    violations: list[str] = []
    for case_id, entry in report["cases"].items():
        hard = entry["hardFail"]
        minimum = HARD_FAIL_PASS_RATE if hard else DEFAULT_MIN_PASS_RATE
        for arm, result in entry["arms"].items():
            if result.get("status") == "skipped":
                continue
            if result["passRate"] < minimum - 1e-9:
                violations.append(
                    f"{case_id}[{arm}] {result['passes']}/{result['attempts']} "
                    f"below {'3/3' if hard else '2/3'}"
                )
            if result["abstentions"]:
                violations.append(
                    f"{case_id}[{arm}] {result['abstentions']} abstention(s)"
                )
        arms = entry["arms"]
        if "on" in arms and "off" in arms:
            on, off = arms["on"], arms["off"]
            if on.get("status") != "skipped" and off.get("status") != "skipped":
                if on["passRate"] < off["passRate"] - 1e-9:
                    violations.append(
                        f"{case_id} regression: on {on['passes']}/{on['attempts']} "
                        f"< off {off['passes']}/{off['attempts']}"
                    )
    return violations


# --- report ------------------------------------------------------------------


def _totals(entries: Iterable[dict]) -> dict:
    usage = harness.Usage()
    for entry in entries:
        source = entry["usage"]
        usage = usage.add(
            harness.Usage(
                input_tokens=source["inputTokens"],
                output_tokens=source["outputTokens"],
                cache_read_tokens=source["cacheReadTokens"],
                cache_creation_tokens=source["cacheCreationTokens"],
                rounds=source["modelRounds"],
                model=source["model"],
                inr=source["inr"],
            )
        )
    return usage.as_dict()


def build_report(
    *,
    cases: list[harness.Case],
    per_arm: dict[str, dict],
    arms: list[str],
    attempts: int,
    skipped: bool,
) -> dict:
    flag_present = curation_flag_exists()
    report: dict[str, Any] = {
        "change": "CHO-276",
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"
        ),
        "kind": "comparison" if flag_present else "baseline",
        "curationFlag": {"env": CURATION_ENV, "present": flag_present},
        "arms": arms,
        "attemptsPerArm": attempts,
        "model": config.agent_model(),
        "apiKeyPresent": harness.api_key_present(),
        "skipped": skipped,
        "pytestOnlyCases": PYTEST_ONLY_CASES,
        "cases": {},
        "totals": {},
        "thresholds": {},
    }
    for case in cases:
        report["cases"][case.id] = {
            "title": case.title,
            "hardFail": case.hard_fail,
            "notes": case.notes,
            "arms": {
                arm: (
                    per_arm[arm][case.id]
                    if not skipped
                    else {
                        "status": "skipped",
                        "reason": "no ANTHROPIC_API_KEY",
                        "attempts": 0,
                        "passes": 0,
                        "passRate": 0.0,
                        "abstentions": 0,
                        "firstFailure": None,
                        "observed": [],
                        "seedToProbeSeconds": [],
                        "usage": harness.Usage().as_dict(),
                    }
                )
                for arm in arms
            },
        }
    if not skipped:
        for arm in arms:
            report["totals"][arm] = _totals(per_arm[arm].values())
        if "on" in arms and "off" in arms:
            on, off = report["totals"]["on"], report["totals"]["off"]
            report["totals"]["delta"] = {
                "totalTokens": on["totalTokens"] - off["totalTokens"],
                "inr": round((on["inr"] or 0.0) - (off["inr"] or 0.0), 6),
                "note": (
                    "both arms are identical until CHO-271 lands the curation "
                    "flag — this is a baseline, not a comparison"
                )
                if not flag_present
                else "flag-on minus flag-off",
            }
        blocked = sorted(
            {
                attempt
                for arm in arms
                for entry in per_arm[arm].values()
                for observed in entry["observed"]
                for attempt in observed.get("blockedHttpAttempts", [])
            }
        )
        report["blockedHttpAttempts"] = blocked
        report["freshdeskRequests"] = 0 if not blocked else len(
            [attempt for attempt in blocked if "freshdesk" in attempt.lower()]
        )
    else:
        report["blockedHttpAttempts"] = []
        report["freshdeskRequests"] = 0
    violations = evaluate_thresholds(report)
    report["thresholds"] = {
        "hardFailCases": [case.id for case in cases if case.hard_fail],
        "minPassRate": DEFAULT_MIN_PASS_RATE,
        "passed": not violations,
        "violations": violations,
    }
    return report


def _markdown(report: dict) -> str:
    lines = [
        f"# Routing evals — {report['kind']} ({report['generatedAt']})",
        "",
        f"* change: **{report['change']}** · model `{report['model']}`",
        f"* arms: {', '.join(report['arms'])} · {report['attemptsPerArm']} attempt(s) each",
        (
            f"* curation flag `{report['curationFlag']['env']}` present: "
            f"**{report['curationFlag']['present']}**"
        ),
        f"* gate: **{'PASS' if report['thresholds']['passed'] else 'FAIL'}**",
        (
            f"* blocked outbound HTTP attempts: "
            f"{len(report['blockedHttpAttempts'])} "
            f"(Freshdesk: {report['freshdeskRequests']})"
        ),
        "",
    ]
    if report["skipped"]:
        lines += [
            (
                "> No `ANTHROPIC_API_KEY` — every live case was skipped and "
                "the runner exited 0."
            ),
            "",
        ]
    lines += ["| case | " + " | ".join(report["arms"]) + " | hard fail | title |",
              "|---|" + "---|" * (len(report["arms"]) + 2)]
    for case_id, entry in report["cases"].items():
        cells = []
        for arm in report["arms"]:
            result = entry["arms"][arm]
            if result.get("status") == "skipped":
                cells.append("skipped")
            else:
                cells.append(f"{result['passes']}/{result['attempts']}")
        lines.append(
            f"| {case_id} | "
            + " | ".join(cells)
            + f" | {'yes' if entry['hardFail'] else 'no'} | {entry['title']} |"
        )
    lines.append("")
    if report["totals"]:
        lines += ["## Tokens and cost", "",
                  "| arm | input | output | cache read | cache write | total | INR |",
                  "|---|---|---|---|---|---|---|"]
        for arm in report["arms"]:
            totals = report["totals"].get(arm)
            if not totals:
                continue
            lines.append(
                f"| {arm} | {totals['inputTokens']} | {totals['outputTokens']} | "
                f"{totals['cacheReadTokens']} | {totals['cacheCreationTokens']} | "
                f"{totals['totalTokens']} | {totals['inr']} |"
            )
        delta = report["totals"].get("delta")
        if delta:
            lines += [
                "",
                (
                    f"Delta (on − off): {delta['totalTokens']} tokens, "
                    f"₹{delta['inr']} — {delta['note']}"
                ),
            ]
        lines.append("")
    failures = [
        (case_id, arm, result["firstFailure"])
        for case_id, entry in report["cases"].items()
        for arm, result in entry["arms"].items()
        if result.get("firstFailure")
    ]
    if failures:
        lines += ["## First failure per case/arm", ""]
        for case_id, arm, failure in failures:
            lines.append(
                f"* **{case_id} [{arm}]** attempt {failure['attempt']}: "
                + "; ".join(failure["failures"])
            )
        lines.append("")
    if report["thresholds"]["violations"]:
        lines += ["## Threshold violations", ""]
        lines += [f"* {violation}" for violation in report["thresholds"]["violations"]]
        lines.append("")
    lines += [
        "## Not measured here",
        "",
        (
            "* E5 (ticket-affirmation guard) runs in `uv run pytest`, never "
            "live — ticket creation has no dry-run mode."
        ),
        (
            "* Contract-note ids are synthetic: E3 measures id fidelity only, "
            "not that the download path works (600s TTL applies to real ids)."
        ),
        "",
    ]
    return "\n".join(lines)


def write_report(report: dict, *, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = (
        report["generatedAt"]
        .replace("+00:00", "Z")
        .replace(":", "")
        .replace("-", "")
    )
    json_path = directory / f"routing-evals-{stamp}.json"
    md_path = directory / f"routing-evals-{stamp}.md"
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    markdown = _markdown(report)
    # Belt and braces: a report is attached to Linear, so it must never be able
    # to carry the key even if a future field started echoing the environment.
    key = config.anthropic_api_key()
    if key and (key in payload or key in markdown):
        raise RuntimeError("refusing to write a report containing the API key")
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path


# --- CLI ---------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m evals.runner",
        description="CHO-276 routing/recall eval sweep (needs ANTHROPIC_API_KEY).",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=None,
        metavar="ID",
        help="case id to run (repeatable); default is every case",
    )
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--arm", choices=("on", "off", "both"), default="both")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPORTS_DIR,
        help="report directory (default evals/reports, gitignored)",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.attempts < 1:
        print("--attempts must be >= 1", file=sys.stderr)
        return 2
    if args.case:
        unknown = [case_id for case_id in args.case if case_id not in CASES_BY_ID]
        if unknown:
            known = ", ".join(CASES_BY_ID)
            print(f"unknown case(s): {', '.join(unknown)} (known: {known})",
                  file=sys.stderr)
            return 2
        cases = [CASES_BY_ID[case_id] for case_id in args.case]
    else:
        cases = list(ALL_CASES)
    arms = list(ARMS) if args.arm == "both" else [args.arm]

    skipped = not harness.api_key_present()
    per_arm: dict[str, dict] = {}
    if skipped:
        print(
            "ANTHROPIC_API_KEY is not set — every live case is SKIPPED "
            "(this is not a failure).",
            flush=True,
        )
    else:
        for arm in arms:
            per_arm[arm] = run_arm(
                cases, arm=arm, attempts=args.attempts, quiet=args.quiet
            )

    report = build_report(
        cases=cases,
        per_arm=per_arm,
        arms=arms,
        attempts=args.attempts,
        skipped=skipped,
    )
    json_path, md_path = write_report(report, directory=args.out)

    print()
    print(_markdown(report))
    print(f"report: {json_path}")
    print(f"report: {md_path}")

    if skipped:
        return 0
    return 0 if report["thresholds"]["passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
