#!/usr/bin/env python3
"""Validate, simulate, evaluate, and optionally submit QuantaAlpha candidates."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

from brain_client import BrainClient, BrainError, default_settings
from research_core import (
    FieldCatalog,
    GateConfig,
    MetricPolicy,
    ResearchStore,
    active_expression_similarity,
    aligned_correlation,
    atomic_write_json,
    candidate_id,
    latest_evaluations,
    metric_snapshot,
    submission_eligibility,
    trajectory_reward,
    utc_now,
    validate_candidate,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
FIELD_PATH = SKILL_DIR / "references" / "wq_usa_top3000_delay1_data_fields.json"
DEFAULT_RUN_ROOT = SKILL_DIR / "private" / "research_runs"
ACTIVE_STRUCTURE_FLOOR = 0.35
ACTIVE_CORE_CONTAINMENT_LIMIT = 0.80
ACTIVE_REFRESH_INTERVAL_SECONDS = 0.75
MIN_CORRELATION_OVERLAP = 50


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        value = json.loads(text)
        if isinstance(value, dict) and isinstance(value.get("candidates"), list):
            values = value["candidates"]
        elif isinstance(value, list):
            values = value
        else:
            values = [value]
    if not all(isinstance(item, dict) for item in values):
        raise ValueError("candidate input must contain JSON objects")
    return values


def _candidate_values(store: ResearchStore, input_path: str | None) -> list[dict[str, Any]]:
    if input_path:
        return _load_candidates(Path(input_path))
    return [
        candidate
        for candidate in store.candidates()
        if candidate.get("validation", {}).get("passed")
    ]


def _active_snapshot_path(store: ResearchStore) -> Path:
    return store.path / "active_snapshot.json"


def _alpha_expression(alpha: dict[str, Any]) -> str:
    value = alpha.get("regular", alpha.get("expression", ""))
    if isinstance(value, dict):
        return str(value.get("code", ""))
    return str(value or "")


def _latest_run_id(root: Path) -> str:
    runs = []
    for path in root.glob("*/run.json") if root.exists() else []:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        runs.append((str(value.get("created_at", "")), path.parent.name))
    if not runs:
        raise FileNotFoundError(
            "no research run found; initialize one with `python scripts/evolve_skill.py init`"
        )
    return max(runs)[1]


def _refresh_active(client: BrainClient, store: ResearchStore) -> dict[str, Any]:
    values = []
    previous_path = _active_snapshot_path(store)
    previous = (
        json.loads(previous_path.read_text(encoding="utf-8"))
        if previous_path.exists()
        else {"active": []}
    )
    cached_pnl = {
        str(item.get("alpha_id")): item.get("pnl", [])
        for item in previous.get("active", [])
        if isinstance(item, dict) and item.get("alpha_id") and item.get("pnl")
    }
    alphas = client.list_alphas()
    active = [alpha for alpha in alphas if str(alpha.get("status", "")).upper() == "ACTIVE"]
    for index, alpha in enumerate(active):
        alpha_id = str(alpha.get("id", ""))
        if not alpha_id:
            continue
        detail = client.get_alpha(alpha_id)
        pnl_source = "api"
        pnl_error = None
        try:
            pnl = client.fetch_pnl(alpha_id)
        except (BrainError, requests.RequestException, TimeoutError) as exc:
            pnl = cached_pnl.get(alpha_id, [])
            pnl_source = "cache" if pnl else "unavailable"
            pnl_error = type(exc).__name__
        values.append(
            {
                "alpha_id": alpha_id,
                "expression": _alpha_expression(detail),
                "metrics": metric_snapshot(detail),
                "pnl": pnl,
                "pnl_source": pnl_source,
                "pnl_error": pnl_error,
            }
        )
        if index + 1 < len(active):
            time.sleep(ACTIVE_REFRESH_INTERVAL_SECONDS)
    active_with_pnl = sum(
        len(item.get("pnl", [])) > MIN_CORRELATION_OVERLAP for item in values
    )
    snapshot = {
        "updated_at": utc_now(),
        "active": values,
        "pnl_coverage": {
            "active_count": len(values),
            "active_with_usable_pnl": active_with_pnl,
            "complete": active_with_pnl == len(values),
            "minimum_points": MIN_CORRELATION_OVERLAP + 1,
        },
    }
    atomic_write_json(_active_snapshot_path(store), snapshot)
    return snapshot


def _load_active(client: BrainClient, store: ResearchStore, refresh: bool) -> dict[str, Any]:
    path = _active_snapshot_path(store)
    if refresh or not path.exists():
        return _refresh_active(client, store)
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    # Backfill expressions for snapshots created before expression-aware
    # redundancy control. This keeps the guard useful even before the next API
    # refresh when the ACTIVE alpha originated in the current research run.
    candidates = {
        str(item.get("candidate_id")): item
        for item in store.candidates()
        if item.get("candidate_id")
    }
    alpha_to_expression = {}
    for evaluation in store.evaluations():
        candidate = candidates.get(str(evaluation.get("candidate_id"))) or {}
        if evaluation.get("alpha_id") and candidate.get("expression"):
            alpha_to_expression[str(evaluation["alpha_id"])] = str(
                candidate["expression"]
            )
    for item in snapshot.get("active", []):
        if not item.get("expression"):
            item["expression"] = alpha_to_expression.get(
                str(item.get("alpha_id") or ""), ""
            )
    return snapshot


def _load_correlation_references(
    client: BrainClient, store: ResearchStore, active_snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Build the live submission reference set from ACTIVE plus pool-only members."""
    references = []
    known_ids = set()
    for item in active_snapshot.get("active", []):
        if not isinstance(item, dict):
            continue
        value = dict(item)
        value["reference_source"] = "ACTIVE"
        references.append(value)
        if value.get("alpha_id"):
            known_ids.add(str(value["alpha_id"]))

    pool_path = store.path / "factor_pool.json"
    pool = json.loads(pool_path.read_text(encoding="utf-8")) if pool_path.exists() else {}
    evaluations = latest_evaluations(store.evaluations())
    for member in pool.get("members", []):
        if not isinstance(member, dict):
            continue
        alpha_id = str(member.get("alpha_id") or "")
        if not alpha_id or alpha_id in known_ids:
            continue
        evaluation = evaluations.get(str(member.get("candidate_id") or ""), {})
        pnl = list(evaluation.get("pnl", []))
        pnl_error = None
        if len(pnl) <= MIN_CORRELATION_OVERLAP:
            try:
                pnl = client.fetch_pnl(alpha_id)
            except (BrainError, requests.RequestException, TimeoutError) as exc:
                pnl_error = type(exc).__name__
        references.append(
            {
                "alpha_id": alpha_id,
                "expression": member.get("expression", ""),
                "metrics": member.get("metrics", {}),
                "pnl": pnl,
                "pnl_source": "evaluation" if pnl else "unavailable",
                "pnl_error": pnl_error,
                "reference_source": "FACTOR_POOL",
            }
        )
        known_ids.add(alpha_id)
        time.sleep(ACTIVE_REFRESH_INTERVAL_SECONDS)
    return {
        "updated_at": active_snapshot.get("updated_at"),
        "active": references,
        "reference_counts": {
            "active": sum(item.get("reference_source") == "ACTIVE" for item in references),
            "factor_pool_only": sum(
                item.get("reference_source") == "FACTOR_POOL" for item in references
            ),
            "total": len(references),
        },
    }


def _add_dynamic_active_reference(
    store: ResearchStore,
    active_snapshot: dict[str, Any],
    reference_snapshot: dict[str, Any],
    *,
    alpha_id: str,
    expression: str,
    metrics: dict[str, Any],
    pnl: list[dict[str, Any]],
) -> None:
    """Make a newly ACTIVE alpha visible to every later candidate in the batch."""
    item = {
        "alpha_id": alpha_id,
        "expression": expression,
        "metrics": metrics,
        "pnl": pnl,
        "pnl_source": "current_batch",
        "pnl_error": None,
    }
    active_values = active_snapshot.setdefault("active", [])
    if alpha_id not in {str(value.get("alpha_id")) for value in active_values}:
        active_values.append(dict(item))
    reference_values = reference_snapshot.setdefault("active", [])
    existing = next(
        (value for value in reference_values if str(value.get("alpha_id")) == alpha_id),
        None,
    )
    if existing is None:
        reference_values.append({**item, "reference_source": "ACTIVE"})
    else:
        existing.update({**item, "reference_source": "ACTIVE"})
    reference_snapshot["reference_counts"] = {
        "active": sum(
            value.get("reference_source") == "ACTIVE" for value in reference_values
        ),
        "factor_pool_only": sum(
            value.get("reference_source") == "FACTOR_POOL" for value in reference_values
        ),
        "total": len(reference_values),
    }
    active_snapshot["updated_at"] = utc_now()
    usable = sum(
        len(value.get("pnl", [])) > MIN_CORRELATION_OVERLAP for value in active_values
    )
    active_snapshot["pnl_coverage"] = {
        "active_count": len(active_values),
        "active_with_usable_pnl": usable,
        "complete": usable == len(active_values),
        "minimum_points": MIN_CORRELATION_OVERLAP + 1,
    }
    atomic_write_json(_active_snapshot_path(store), active_snapshot)


def _active_correlation_audit(
    pnl: list[dict[str, Any]], snapshot: dict[str, Any]
) -> dict[str, Any]:
    output = []
    unavailable = []
    for old in snapshot.get("active", []):
        correlation = aligned_correlation(
            pnl, old.get("pnl", []), min_overlap=MIN_CORRELATION_OVERLAP
        )
        value = correlation.get("correlation")
        if value is None:
            unavailable.append(
                {
                    "alpha_id": old.get("alpha_id"),
                    "overlap": correlation.get("overlap", 0),
                    "pnl_source": old.get("pnl_source", "unknown"),
                    "reference_source": old.get("reference_source", "ACTIVE"),
                }
            )
            continue
        output.append(
            {
                "alpha_id": old.get("alpha_id"),
                "correlation": value,
                "overlap": correlation.get("overlap"),
                "start": correlation.get("start"),
                "end": correlation.get("end"),
                "reference_source": old.get("reference_source", "ACTIVE"),
            }
        )
    output.sort(key=lambda item: abs(float(item["correlation"])), reverse=True)
    return {
        "active_count": len(snapshot.get("active", [])),
        "reference_counts": snapshot.get("reference_counts", {}),
        "comparable_count": len(output),
        "unavailable_count": len(unavailable),
        "candidate_pnl_points": len(pnl),
        "complete": not unavailable,
        "correlations": output,
        "unavailable": unavailable,
    }


def _correlation_submission_gate(
    audit: dict[str, Any], max_pnl_correlation: float
) -> dict[str, Any]:
    correlations = audit.get("correlations", [])
    max_abs_correlation = (
        abs(float(correlations[0]["correlation"])) if correlations else None
    )
    blockers = []
    if int(audit.get("candidate_pnl_points", 0)) <= MIN_CORRELATION_OVERLAP:
        blockers.append("CANDIDATE_PNL_UNAVAILABLE")
    unavailable_sources = {
        str(item.get("reference_source") or "ACTIVE")
        for item in audit.get("unavailable", [])
    }
    if "ACTIVE" in unavailable_sources:
        blockers.append("ACTIVE_PNL_COVERAGE_INCOMPLETE")
    if "FACTOR_POOL" in unavailable_sources:
        blockers.append("FACTOR_POOL_PNL_COVERAGE_INCOMPLETE")
    high_sources = {
        str(item.get("reference_source") or "ACTIVE")
        for item in correlations
        if abs(float(item.get("correlation") or 0.0)) >= max_pnl_correlation
    }
    if "ACTIVE" in high_sources:
        blockers.append("ACTIVE_PNL_CORRELATION")
    if "FACTOR_POOL" in high_sources:
        blockers.append("FACTOR_POOL_PNL_CORRELATION")
    return {
        "passed": not blockers,
        "threshold": max_pnl_correlation,
        "max_abs_correlation": max_abs_correlation,
        "active_count": audit.get("active_count", 0),
        "comparable_count": audit.get("comparable_count", 0),
        "unavailable_count": audit.get("unavailable_count", 0),
        "candidate_pnl_points": audit.get("candidate_pnl_points", 0),
        "reference_counts": audit.get("reference_counts", {}),
        "blockers": blockers,
    }


def _active_expression_matches(
    expression: str, snapshot: dict[str, Any], catalog: FieldCatalog
) -> list[dict[str, Any]]:
    matches = []
    for old in snapshot.get("active", []):
        active_expression = str(old.get("expression") or "")
        if not active_expression:
            continue
        similarity = active_expression_similarity(expression, active_expression, catalog)
        if (
            similarity["structural_similarity"] >= ACTIVE_STRUCTURE_FLOOR
            and similarity["active_core_field_containment"]
            >= ACTIVE_CORE_CONTAINMENT_LIMIT
        ):
            matches.append({"alpha_id": old.get("alpha_id"), **similarity})
    matches.sort(
        key=lambda item: (
            float(item["active_core_field_containment"]),
            float(item["structural_similarity"]),
        ),
        reverse=True,
    )
    return matches


def _settings(candidate: dict[str, Any]) -> dict[str, Any]:
    settings = default_settings()
    candidate_settings = candidate.get("settings", {})
    if not isinstance(candidate_settings, dict):
        raise ValueError("candidate.settings must be an object")
    settings.update(candidate_settings)
    return settings


def _static_result(candidate: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "stage": "STATIC_VALIDATION",
        "validation": validation,
        "settings": _settings(candidate),
    }


def batch_submission_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the user-facing end-of-batch submission ledger."""

    def compact(item: dict[str, Any]) -> dict[str, Any]:
        eligibility = item.get("submission_eligibility", {})
        return {
            "candidate_id": item.get("candidate_id"),
            "alpha_id": item.get("alpha_id"),
            "grade": eligibility.get("grade") or item.get("metrics", {}).get("grade"),
            "stage": item.get("stage"),
            "pending_checks": eligibility.get("pending_checks", []),
            "failed_checks": eligibility.get("failed_checks", []),
            "blockers": item.get("submission_blockers", []),
            "correlation_gate": item.get("correlation_submission_gate"),
        }

    eligible = [
        item
        for item in results
        if item.get(
            "auto_submit_qualified",
            item.get("submission_eligibility", {}).get("eligible", False),
        )
    ]
    successful = [item for item in results if item.get("stage") == "ACTIVE"]
    rejected = [
        item
        for item in results
        if item.get("submit_attempted") and item.get("stage") != "ACTIVE"
    ]
    grade_with_fail = [
        item
        for item in results
        if item.get("submission_eligibility", {}).get("grade_eligible")
        and item.get("submission_eligibility", {}).get("failed_checks")
    ]
    below_grade = [
        item
        for item in results
        if item.get("metrics")
        and not item.get("submission_eligibility", {}).get("grade_eligible")
    ]
    return {
        "evaluated_count": len(results),
        "auto_submit_candidate_count": len(eligible),
        "active_success_count": len(successful),
        "submission_rejected_or_unresolved_count": len(rejected),
        "grade_eligible_but_failed_is_test_count": len(grade_with_fail),
        "below_average_count": len(below_grade),
        "auto_submit_candidates": [compact(item) for item in eligible],
        "active_successes": [compact(item) for item in successful],
        "submission_rejected_or_unresolved": [compact(item) for item in rejected],
        "grade_eligible_but_failed_is_test": [compact(item) for item in grade_with_fail],
    }


def _evaluation_failures(evaluation: dict[str, Any]) -> set[str]:
    failures = set(evaluation.get("reward", {}).get("metric_gate", {}).get("failures", []))
    for check in evaluation.get("metrics", {}).get("checks", []):
        if isinstance(check, dict) and str(check.get("result") or "").upper() == "FAIL":
            failures.add(str(check.get("name") or "UNKNOWN_CHECK"))
    failures.update(str(value) for value in evaluation.get("governance_warnings", []))
    return {value for value in failures if value}


def _parent_feedback(
    candidate: dict[str, Any],
    child_evaluation: dict[str, Any],
    evaluation_index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Record whether the requested repair improved the selected parent trajectory."""
    parents = [str(value) for value in candidate.get("parents", []) if value]
    comparisons = []
    child_metrics = child_evaluation.get("metrics", {})
    child_reward = child_evaluation.get("reward", {}).get("reward")
    child_failures = _evaluation_failures(child_evaluation)
    for parent_id in parents:
        parent = evaluation_index.get(parent_id)
        if not parent:
            continue
        parent_metrics = parent.get("metrics", {})
        parent_reward = parent.get("reward", {}).get("reward")
        parent_failures = _evaluation_failures(parent)
        reward_delta = (
            float(child_reward) - float(parent_reward)
            if child_reward is not None and parent_reward is not None
            else None
        )
        resolved = sorted(parent_failures - child_failures)
        introduced = sorted(child_failures - parent_failures)
        if (
            (reward_delta is not None and reward_delta >= 0.05)
            or (resolved and not introduced)
        ):
            outcome = "IMPROVED"
        elif (
            (reward_delta is not None and reward_delta <= -0.05)
            or len(introduced) > len(resolved)
        ):
            outcome = "WORSE"
        else:
            outcome = "MIXED"
        comparisons.append(
            {
                "parent_id": parent_id,
                "outcome": outcome,
                "reward_delta": reward_delta,
                "sharpe_delta": (
                    float(child_metrics.get("sharpe") or 0.0)
                    - float(parent_metrics.get("sharpe") or 0.0)
                ),
                "fitness_delta": (
                    float(child_metrics.get("fitness") or 0.0)
                    - float(parent_metrics.get("fitness") or 0.0)
                ),
                "turnover_delta": (
                    float(child_metrics.get("turnover") or 0.0)
                    - float(parent_metrics.get("turnover") or 0.0)
                ),
                "resolved_failures": resolved,
                "introduced_failures": introduced,
            }
        )
    if not comparisons:
        return None
    return {
        "repair_card": candidate.get("repair_card"),
        "generation_trace": candidate.get("generation_trace"),
        "action_id": candidate.get("generation_trace", {}).get("action_id"),
        "interpretation": (
            "This outcome evaluates the concrete mutation action only; it does not retire or invalidate the parent."
        ),
        "comparisons": comparisons,
        "overall": (
            "IMPROVED"
            if any(item["outcome"] == "IMPROVED" for item in comparisons)
            else "WORSE"
            if all(item["outcome"] == "WORSE" for item in comparisons)
            else "MIXED"
        ),
    }


def submit_existing(args: argparse.Namespace) -> int:
    """Submit already-simulated eligible alphas without consuming new simulations."""
    run_root = Path(args.run_root).expanduser().resolve()
    run_id = args.run_id or _latest_run_id(run_root)
    store = ResearchStore(run_root, run_id)
    run_config = store.load_run()
    gate_config = GateConfig(**run_config.get("gate_config", {}))
    latest = latest_evaluations(store.evaluations())
    client = BrainClient.from_environment(SKILL_DIR)
    client.authenticate()
    active_snapshot = _refresh_active(client, store)
    snapshot = _load_correlation_references(client, store, active_snapshot)
    results = []
    try:
        for prior in latest.values():
            alpha_id = str(prior.get("alpha_id") or "")
            if not alpha_id:
                continue
            if args.alpha_id and alpha_id not in set(args.alpha_id):
                continue
            evaluation = dict(prior)
            detail = client.get_alpha(alpha_id)
            metrics = metric_snapshot(detail)
            eligibility = submission_eligibility(metrics)
            status = str(detail.get("status") or "").upper()
            pnl = list(prior.get("pnl", []))
            pnl_error = None
            if status != "ACTIVE":
                try:
                    pnl = client.fetch_pnl(alpha_id)
                except (BrainError, requests.RequestException, TimeoutError) as exc:
                    pnl_error = type(exc).__name__
            correlation_audit = _active_correlation_audit(pnl, snapshot)
            correlation_gate = _correlation_submission_gate(
                correlation_audit, gate_config.max_pnl_correlation
            )
            submission_blockers = sorted(
                set(eligibility["blockers"] + correlation_gate["blockers"])
            )
            auto_submit_qualified = eligibility["eligible"] and correlation_gate["passed"]
            evaluation.update(
                {
                    "metrics": metrics,
                    "pnl": pnl,
                    "pnl_error": pnl_error,
                    "submission_eligibility": eligibility,
                    "correlation_submission_gate": correlation_gate,
                    "active_correlations": correlation_audit["correlations"][:10],
                    "correlation_unavailable": correlation_audit["unavailable"][:10],
                    "auto_submit_qualified": auto_submit_qualified,
                    "submission_blockers": submission_blockers,
                    "submit_attempted": False,
                }
            )
            if status == "ACTIVE":
                evaluation["stage"] = "ACTIVE"
                evaluation["already_active"] = True
                evaluation["submission_blockers"] = []
                evaluation["auto_submit_qualified"] = True
            elif prior.get("submit_attempted") and prior.get("stage") == "SUBMISSION_REJECTED_OR_UNRESOLVED":
                evaluation["stage"] = "SUBMISSION_REJECTED_OR_UNRESOLVED"
                evaluation["submission_followup_only"] = True
                evaluation["submission_blockers"] = list(
                    prior.get("submission_blockers") or ["NOT_ACTIVE_AFTER_SUBMIT"]
                )
            elif auto_submit_qualified:
                evaluation["submit_attempted"] = True
                try:
                    response = client.submit_alpha(alpha_id)
                    evaluation["submit_http_status"] = response.status_code
                    if response.status_code not in {200, 201}:
                        evaluation["submission_blockers"] = [
                            f"SUBMIT_HTTP_{response.status_code}"
                        ]
                        evaluation["stage"] = "SUBMISSION_REJECTED_OR_UNRESOLVED"
                    else:
                        final = client.wait_for_alpha_status(
                            alpha_id,
                            terminal=("ACTIVE",),
                            timeout_seconds=args.submit_timeout,
                        )
                        final_metrics = metric_snapshot(final)
                        final_eligibility = submission_eligibility(final_metrics)
                        final_status = str(final.get("status") or "").upper()
                        evaluation["post_submit"] = {
                            "status": final.get("status"),
                            "metrics": final_metrics,
                            "submission_eligibility": final_eligibility,
                        }
                        evaluation["submission_blockers"] = (
                            []
                            if final_status == "ACTIVE"
                            else sorted(
                                set(final_eligibility["blockers"] + ["NOT_ACTIVE_AFTER_SUBMIT"])
                            )
                        )
                        evaluation["stage"] = (
                            "ACTIVE"
                            if final_status == "ACTIVE"
                            else "SUBMISSION_REJECTED_OR_UNRESOLVED"
                        )
                        if final_status == "ACTIVE":
                            _add_dynamic_active_reference(
                                store,
                                active_snapshot,
                                snapshot,
                                alpha_id=alpha_id,
                                expression=str(evaluation.get("expression") or ""),
                                metrics=final_metrics,
                                pnl=pnl,
                            )
                except (BrainError, TimeoutError, requests.RequestException) as exc:
                    evaluation["submission_error"] = str(exc)
                    evaluation["submission_blockers"] = ["SUBMISSION_REQUEST_ERROR"]
                    evaluation["stage"] = "SUBMISSION_REJECTED_OR_UNRESOLVED"
            else:
                evaluation["stage"] = "SIMULATED_NOT_ELIGIBLE"
            store.record_evaluation(evaluation)
            results.append(evaluation)
    finally:
        client.close()

    summary = batch_submission_summary(results)
    result_path = store.path / "latest_submission_results.json"
    atomic_write_json(
        result_path,
        {"generated_at": utc_now(), "submission_summary": summary, "results": results},
    )
    store.record_event(
        {
            "event": "existing_alphas_auto_submission_finished",
            "candidate_count": len(results),
            "submit_attempt_count": sum(bool(item.get("submit_attempted")) for item in results),
            "active_count": summary["active_success_count"],
        }
    )
    print(json.dumps({"submission_summary": summary}, ensure_ascii=False, indent=2))
    print(f"results written to {result_path}")
    return 0


def run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    run_root = Path(args.run_root).expanduser().resolve()
    run_id = args.run_id or _latest_run_id(run_root)
    if args.run_id is None:
        print(f"using latest run: {run_id}")
    store = ResearchStore(run_root, run_id)
    run_config = store.load_run()
    historical_evaluations = latest_evaluations(store.evaluations())
    catalog = FieldCatalog(FIELD_PATH)
    if args.refresh_active_only:
        client = BrainClient.from_environment(SKILL_DIR)
        try:
            client.authenticate()
            snapshot = _refresh_active(client, store)
        finally:
            client.close()
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "updated_at": snapshot.get("updated_at"),
                    "active_count": len(snapshot.get("active", [])),
                    "active_with_pnl": sum(
                        bool(item.get("pnl")) for item in snapshot.get("active", [])
                    ),
                    "pnl_coverage": snapshot.get("pnl_coverage", {}),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    candidates = _candidate_values(store, args.input)
    if args.iteration is not None:
        candidates = [
            value
            for value in candidates
            if int(value.get("iteration", -1)) == args.iteration
        ]
    if args.skip_evaluated:
        evaluated_ids = set(latest_evaluations(store.evaluations()))
        candidates = [
            value for value in candidates if candidate_id(value) not in evaluated_ids
        ]
    candidates = candidates[: args.max_candidates]
    if not candidates:
        raise ValueError("no candidates found")

    existing = store.candidates()
    registered_ids = {str(item.get("candidate_id")) for item in existing}
    gate_config = GateConfig(**run_config.get("gate_config", {}))
    policy = MetricPolicy(**run_config.get("metric_policy", {}))
    prepared = []
    for candidate in candidates:
        computed_id = candidate_id(candidate)
        candidate["candidate_id"] = computed_id
        validation = validate_candidate(
            candidate,
            catalog,
            existing=[item for item in existing if item.get("candidate_id") != candidate.get("candidate_id")],
            config=gate_config,
        )
        if computed_id not in registered_ids:
            candidate = store.register_candidate(candidate, validation)
            existing.append(candidate)
            registered_ids.add(computed_id)
        prepared.append((candidate, validation))
        print(json.dumps(_static_result(candidate, validation), ensure_ascii=False))

    if not args.simulate and not args.submit:
        failed = sum(not validation["passed"] for _, validation in prepared)
        print(f"dry-run complete: {len(prepared)} candidates, {failed} failed static gates")
        return 2 if failed else 0

    auto_submit = bool(args.submit or (args.simulate and not args.no_auto_submit))

    client = BrainClient.from_environment(SKILL_DIR)
    client.authenticate()
    active_snapshot = _load_active(client, store, args.refresh_active or auto_submit)
    snapshot = _load_correlation_references(client, store, active_snapshot)
    recoverable_by_expression: dict[str, str] = {}
    if args.recover_account_alphas:
        for item in client.list_alphas():
            regular = item.get("regular") if isinstance(item, dict) else None
            expression = regular.get("code") if isinstance(regular, dict) else None
            alpha_id = item.get("id") if isinstance(item, dict) else None
            if expression and alpha_id and str(expression) not in recoverable_by_expression:
                recoverable_by_expression[str(expression)] = str(alpha_id)
    results = []
    try:
        for candidate, validation in prepared:
            if client.request_count >= int(run_config.get("budget", {}).get("max_api_requests", 2000)):
                store.record_event(
                    {
                        "event": "budget_stop",
                        "reason": "max_api_requests",
                        "api_requests": client.request_count,
                    }
                )
                break
            if (time.monotonic() - started) / 3600 >= float(
                run_config.get("budget", {}).get("max_elapsed_hours", 24)
            ):
                store.record_event({"event": "budget_stop", "reason": "max_elapsed_hours"})
                break
            cid = str(candidate.get("candidate_id") or "unregistered")
            if not validation["passed"]:
                evaluation = {
                    "candidate_id": cid,
                    "stage": "REJECTED_STATIC",
                    "validation": validation,
                }
                store.record_evaluation(evaluation)
                results.append(evaluation)
                continue

            try:
                expression = str(candidate["expression"])
                recovered_alpha_id = recoverable_by_expression.get(expression)
                if recovered_alpha_id:
                    alpha_id = recovered_alpha_id
                    simulation = {"status": "RECOVERED_EXISTING_ACCOUNT_ALPHA"}
                    recoverable_by_expression.pop(expression, None)
                else:
                    alpha_id, simulation = client.simulate(
                        expression,
                        _settings(candidate),
                        timeout_seconds=args.simulation_timeout,
                    )
                alpha = client.get_alpha(alpha_id)
                metrics = metric_snapshot(alpha)
                pnl_error = None
                try:
                    pnl = client.fetch_pnl(alpha_id)
                except (BrainError, requests.RequestException, TimeoutError) as exc:
                    pnl = []
                    pnl_error = type(exc).__name__
                correlation_audit = _active_correlation_audit(pnl, snapshot)
                correlations = correlation_audit["correlations"]
                correlation_gate = _correlation_submission_gate(
                    correlation_audit, gate_config.max_pnl_correlation
                )
                active_expression_matches = _active_expression_matches(
                    str(candidate["expression"]), snapshot, catalog
                )
                max_corr = correlation_gate["max_abs_correlation"]
                nearest_structure = validation.get("nearest_structure") or {}
                max_structure = max(
                    float(nearest_structure.get("similarity") or 0.0),
                    max(
                        (
                            float(item["structural_similarity"])
                            for item in active_expression_matches
                        ),
                        default=0.0,
                    ),
                )
                reward = trajectory_reward(
                    metrics,
                    validation["complexity"],
                    max_abs_correlation=max_corr,
                    max_structural_similarity=max_structure,
                    policy=policy,
                    gates=gate_config,
                )
                evaluation = {
                    "candidate_id": cid,
                    "alpha_id": alpha_id,
                    "stage": "SIMULATED",
                    "simulation_status": simulation.get("status"),
                    "metrics": metrics,
                    "pnl": pnl,
                    "pnl_error": pnl_error,
                    "active_correlations": correlations[:10],
                    "correlation_unavailable": correlation_audit["unavailable"][:10],
                    "correlation_submission_gate": correlation_gate,
                    "active_expression_matches": active_expression_matches[:10],
                    "max_active_correlation": max_corr,
                    "max_structural_similarity": max_structure,
                    "reward": reward,
                    "validation": validation,
                }
                feedback = _parent_feedback(candidate, evaluation, historical_evaluations)
                if feedback:
                    evaluation["parent_feedback"] = feedback

                eligibility = submission_eligibility(metrics)
                evaluation["submission_eligibility"] = eligibility
                submission_blockers = list(
                    eligibility["blockers"] + correlation_gate["blockers"]
                )
                governance_warnings = list(correlation_gate["blockers"])
                if active_expression_matches:
                    governance_warnings.append("ACTIVE_EXPRESSION_REDUNDANCY")
                evaluation["governance_warnings"] = sorted(set(governance_warnings))
                evaluation["auto_submit_qualified"] = (
                    eligibility["eligible"] and correlation_gate["passed"]
                )

                if auto_submit and evaluation["auto_submit_qualified"]:
                    evaluation["submit_attempted"] = True
                    try:
                        response = client.submit_alpha(alpha_id)
                        evaluation["submit_http_status"] = response.status_code
                        if response.status_code not in {200, 201}:
                            submission_blockers.append(f"SUBMIT_HTTP_{response.status_code}")
                        else:
                            final = client.wait_for_alpha_status(
                                alpha_id, terminal=("ACTIVE",), timeout_seconds=args.submit_timeout
                            )
                            final_metrics = metric_snapshot(final)
                            final_eligibility = submission_eligibility(final_metrics)
                            evaluation["post_submit"] = {
                                "status": final.get("status"),
                                "metrics": final_metrics,
                                "submission_eligibility": final_eligibility,
                            }
                            if str(final.get("status", "")).upper() != "ACTIVE":
                                submission_blockers.extend(final_eligibility["blockers"])
                                submission_blockers.append("NOT_ACTIVE_AFTER_SUBMIT")
                    except (BrainError, TimeoutError, requests.RequestException) as exc:
                        evaluation["submission_error"] = str(exc)
                        submission_blockers.append("SUBMISSION_REQUEST_ERROR")
                else:
                    evaluation["submit_attempted"] = False

                evaluation["submission_blockers"] = sorted(set(submission_blockers))
                evaluation["stage"] = (
                    "ACTIVE"
                    if evaluation.get("submit_attempted") and not submission_blockers
                    and str(evaluation.get("post_submit", {}).get("status", "")).upper() == "ACTIVE"
                    else "SUBMISSION_REJECTED_OR_UNRESOLVED"
                    if evaluation.get("submit_attempted")
                    else "SIMULATED_ELIGIBLE_NOT_SUBMITTED"
                    if eligibility["eligible"]
                    else "SIMULATED_NOT_ELIGIBLE"
                )
                if evaluation["stage"] == "ACTIVE":
                    _add_dynamic_active_reference(
                        store,
                        active_snapshot,
                        snapshot,
                        alpha_id=alpha_id,
                        expression=str(candidate["expression"]),
                        metrics=evaluation.get("post_submit", {}).get("metrics", metrics),
                        pnl=pnl,
                    )
            except (BrainError, TimeoutError, requests.RequestException) as exc:  # type: ignore[name-defined]
                evaluation = {
                    "candidate_id": cid,
                    "stage": "SIMULATION_ERROR",
                    "error": str(exc),
                    "repair_budget_remaining": 2,
                }
            store.record_evaluation(evaluation)
            results.append(evaluation)
            print(json.dumps(evaluation, ensure_ascii=False))
            time.sleep(args.between_candidates)
    finally:
        client.close()

    submission_summary = batch_submission_summary(results)
    result_path = store.path / "latest_batch_results.json"
    atomic_write_json(
        result_path,
        {"generated_at": utc_now(), "submission_summary": submission_summary, "results": results},
    )
    store.record_event(
        {
            "event": "batch_finished",
            "mode": "auto_submit" if auto_submit else "simulate_only",
            "candidate_count": len(results),
            "active_count": sum(item.get("stage") == "ACTIVE" for item in results),
            "auto_submit_candidate_count": submission_summary["auto_submit_candidate_count"],
            "submission_rejected_or_unresolved_count": submission_summary[
                "submission_rejected_or_unresolved_count"
            ],
            "api_requests": client.request_count,
            "elapsed_seconds": time.monotonic() - started,
        }
    )
    print(json.dumps({"submission_summary": submission_summary}, ensure_ascii=False, indent=2))
    print(f"results written to {result_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Governed BRAIN simulation and submission runner")
    parser.add_argument(
        "--run-id",
        help="research run ID; omit to use the latest run (WQ-compatible interface)",
    )
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument("--input", help="JSON or JSONL candidates; defaults to registered candidates")
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument(
        "--iteration",
        type=int,
        help="limit registered candidates to one research iteration",
    )
    parser.add_argument("--simulate", action="store_true", help="perform BRAIN simulations")
    parser.add_argument(
        "--submit",
        action="store_true",
        help="compatibility alias; simulation now auto-submits WQ-eligible candidates",
    )
    parser.add_argument("--confirm-submit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--no-auto-submit",
        action="store_true",
        help="diagnostic override: simulate without submitting eligible candidates",
    )
    parser.add_argument(
        "--submit-existing",
        action="store_true",
        help="auto-submit eligible alphas already simulated in the run without re-simulation",
    )
    parser.add_argument(
        "--alpha-id",
        action="append",
        help="limit --submit-existing to one or more explicit alpha IDs",
    )
    parser.add_argument("--refresh-active", action="store_true")
    parser.add_argument(
        "--refresh-active-only",
        action="store_true",
        help="refresh the run ACTIVE expression/PnL snapshot and exit before candidate generation",
    )
    parser.add_argument("--simulation-timeout", type=int, default=1800)
    parser.add_argument(
        "--submit-timeout",
        type=int,
        default=180,
        help="seconds to wait for ACTIVE/FAIL before recording an unresolved submission",
    )
    parser.add_argument("--between-candidates", type=float, default=2.0)
    parser.add_argument(
        "--skip-evaluated",
        action="store_true",
        help="skip candidates that already have a recorded evaluation in this run",
    )
    parser.add_argument(
        "--recover-account-alphas",
        action="store_true",
        help="reuse an exact-expression account Alpha before creating a new simulation",
    )
    return parser


if __name__ == "__main__":
    try:
        args = build_parser().parse_args()
        if args.submit_existing:
            sys.exit(submit_existing(args))
        if args.submit:
            args.simulate = True
        sys.exit(run(args))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
