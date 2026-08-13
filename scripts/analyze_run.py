#!/usr/bin/env python3
"""Generate regime, decay, stress, and convergence diagnostics for a research run."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from research_core import (
    ResearchStore,
    atomic_write_json,
    latest_evaluations,
    pnl_daily_changes,
    submission_eligibility,
    utc_now,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_RUN_ROOT = SKILL_DIR / "private" / "research_runs"


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _series_stats(series: list[dict[str, Any]], start: str | None = None, end: str | None = None) -> dict[str, Any]:
    changes = pnl_daily_changes(series)
    values = [
        (date, value)
        for date, value in sorted(changes.items())
        if (start is None or date >= start) and (end is None or date <= end)
    ]
    daily = [value for _, value in values]
    std = _std(daily)
    running = peak = 0.0
    max_drawdown = 0.0
    trough_date = None
    for date, value in values:
        running += value
        peak = max(peak, running)
        drawdown = running - peak
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            trough_date = date
    return {
        "start": values[0][0] if values else None,
        "end": values[-1][0] if values else None,
        "observations": len(values),
        "pnl_change": sum(daily),
        "daily_mean": _mean(daily),
        "daily_std": std,
        "annualized_signal_to_noise": (
            None if not std else (_mean(daily) or 0) / std * math.sqrt(252)
        ),
        "positive_day_share": (
            None if not daily else sum(value > 0 for value in daily) / len(daily)
        ),
        "max_drawdown_pnl_units": max_drawdown,
        "max_drawdown_date": trough_date,
    }


def build_report(store: ResearchStore, stress_start: str | None, stress_end: str | None) -> dict[str, Any]:
    candidates = {
        str(value.get("candidate_id")): value for value in store.candidates() if value.get("candidate_id")
    }
    evaluations = list(latest_evaluations(store.evaluations()).values())
    annual: dict[str, list[dict[str, Any]]] = defaultdict(list)
    iterations: dict[int, list[float]] = defaultdict(list)
    candidate_stats = []
    submission_records = []
    for evaluation in evaluations:
        candidate = candidates.get(str(evaluation.get("candidate_id")), {})
        reward = evaluation.get("reward", {}).get("reward")
        if reward is not None:
            iterations[int(candidate.get("iteration", 0))].append(float(reward))
        pnl = evaluation.get("pnl", [])
        changes = pnl_daily_changes(pnl)
        years = sorted({date[:4] for date in changes})
        yearly = {year: _series_stats(pnl, f"{year}-01-01", f"{year}-12-31") for year in years}
        for year, stats in yearly.items():
            annual[year].append(stats)
        candidate_stats.append(
            {
                "candidate_id": evaluation.get("candidate_id"),
                "direction_id": candidate.get("direction_id"),
                "reward": reward,
                "grade": evaluation.get("metrics", {}).get("grade"),
                "submission_eligibility": submission_eligibility(
                    evaluation.get("metrics", {})
                ),
                "submission_stage": evaluation.get("stage"),
                "full_period": _series_stats(pnl),
                "annual": yearly,
                "stress_period": (
                    _series_stats(pnl, stress_start, stress_end)
                    if stress_start and stress_end
                    else None
                ),
            }
        )
        eligibility = submission_eligibility(evaluation.get("metrics", {}))
        submission_records.append(
            {
                "candidate_id": evaluation.get("candidate_id"),
                "alpha_id": evaluation.get("alpha_id"),
                "grade": eligibility.get("grade"),
                "eligible": eligibility.get("eligible"),
                "pending_checks": eligibility.get("pending_checks"),
                "failed_checks": eligibility.get("failed_checks"),
                "stage": evaluation.get("stage"),
            }
        )
    convergence = []
    best_so_far = None
    for iteration in sorted(iterations):
        rewards = iterations[iteration]
        iteration_best = max(rewards)
        best_so_far = iteration_best if best_so_far is None else max(best_so_far, iteration_best)
        convergence.append(
            {
                "iteration": iteration,
                "count": len(rewards),
                "mean_reward": _mean(rewards),
                "best_reward": iteration_best,
                "best_so_far": best_so_far,
            }
        )
    return {
        "generated_at": utc_now(),
        "run_id": store.run_id,
        "methodology": {
            "correlations_and_periods": "daily changes of cumulative PnL aligned by date",
            "warning": "PnL-unit diagnostics are not portfolio returns and do not replace capacity or cost analysis.",
        },
        "convergence": convergence,
        "submission_summary": {
            "eligible_count": sum(bool(item["eligible"]) for item in submission_records),
            "active_success_count": sum(item["stage"] == "ACTIVE" for item in submission_records),
            "eligible_factors": [item for item in submission_records if item["eligible"]],
            "active_successes": [item for item in submission_records if item["stage"] == "ACTIVE"],
        },
        "candidate_diagnostics": candidate_stats,
        "stress_window": {"start": stress_start, "end": stress_end},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze QuantaAlpha run stability")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument("--stress-start")
    parser.add_argument("--stress-end")
    parser.add_argument("--output")
    args = parser.parse_args()
    if bool(args.stress_start) != bool(args.stress_end):
        parser.error("stress-start and stress-end must be provided together")
    store = ResearchStore(Path(args.run_root).expanduser().resolve(), args.run_id)
    report = build_report(store, args.stress_start, args.stress_end)
    output = Path(args.output) if args.output else store.path / "analysis_report.json"
    atomic_write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
