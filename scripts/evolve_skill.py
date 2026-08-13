#!/usr/bin/env python3
"""Manage QuantaAlpha research trajectories without exposing private alpha assets."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from account_sync import sync_account
from research_core import (
    DEFAULT_DIRECTIONS,
    FieldCatalog,
    GateConfig,
    ResearchStore,
    active_expression_similarity,
    aligned_correlation,
    atomic_write_json,
    candidate_id,
    core_signal_fields,
    diagnose_evaluation,
    latest_evaluations,
    read_json,
    referenced_fields,
    structural_similarity,
    submission_eligibility,
    utc_now,
    validate_candidate,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
FIELD_PATH = SKILL_DIR / "references" / "wq_usa_top3000_delay1_data_fields.json"
DEFAULT_RUN_ROOT = SKILL_DIR / "private" / "research_runs"
LESSONS_PATH = SKILL_DIR / "references" / "validated_lessons.json"
ALPHA_DB_PATH = SKILL_DIR / "alpha_db.json"
ACTIVE_STRUCTURE_FLOOR = 0.35
ACTIVE_CORE_CONTAINMENT_LIMIT = 0.80


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def _load_objects(path: Path) -> list[dict[str, Any]]:
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
        raise ValueError(f"expected JSON candidate objects in {path}")
    return values


def _run_root(args: argparse.Namespace) -> Path:
    return Path(args.run_root).expanduser().resolve()


def _catalog() -> FieldCatalog:
    return FieldCatalog(FIELD_PATH)


def _validated_observations() -> list[dict[str, Any]]:
    lessons = read_json(LESSONS_PATH, {"lessons": []})
    output = []
    for lesson in lessons.get("lessons", []) if isinstance(lessons, dict) else []:
        if lesson.get("evidence_grade") != "repeatable":
            continue
        output.extend(
            item
            for item in lesson.get("observations", [])
            if isinstance(item, dict)
        )
    return output


def _active_references(
    catalog: FieldCatalog, store: ResearchStore | None = None
) -> list[dict[str, Any]]:
    references: dict[str, dict[str, Any]] = {}
    database = read_json(ALPHA_DB_PATH, {"alphas": {}})
    alphas = database.get("alphas", {}) if isinstance(database, dict) else {}
    if isinstance(alphas, dict):
        for alpha_id, value in alphas.items():
            fingerprint = value.get("fingerprint", {}) if isinstance(value, dict) else {}
            expression = str(fingerprint.get("expression") or "")
            if str(fingerprint.get("status", "")).upper() == "ACTIVE" and expression:
                references[expression] = {
                    "alpha_id": str(alpha_id),
                    "expression": expression,
                    "family": fingerprint.get("family"),
                }

    if store is not None:
        snapshot = read_json(store.path / "active_snapshot.json", {"active": []})
        candidates = _candidate_index(store)
        evaluation_to_candidate = {
            str(item.get("alpha_id")): candidates.get(str(item.get("candidate_id")))
            for item in latest_evaluations(store.evaluations()).values()
            if item.get("alpha_id")
        }
        for item in snapshot.get("active", []) if isinstance(snapshot, dict) else []:
            alpha_id = str(item.get("alpha_id") or "")
            expression = str(item.get("expression") or "")
            if not expression:
                candidate = evaluation_to_candidate.get(alpha_id) or {}
                expression = str(candidate.get("expression") or "")
            if expression:
                references[expression] = {
                    "alpha_id": alpha_id,
                    "expression": expression,
                    "family": None,
                }

    output = []
    for item in references.values():
        output.append(
            {
                **item,
                "core_signal_fields": sorted(
                    core_signal_fields(str(item["expression"]), catalog)
                ),
            }
        )
    return output


def _memory_context(
    catalog: FieldCatalog, store: ResearchStore | None = None
) -> dict[str, Any]:
    return {
        "validated_observations": _validated_observations(),
        "active_redundancy_avoid": _active_references(catalog, store),
        "active_adjacency_rule": {
            "structural_similarity_at_least": ACTIVE_STRUCTURE_FLOOR,
            "active_core_field_containment_at_least": ACTIVE_CORE_CONTAINMENT_LIMIT,
            "action": "reject or redesign the mechanism before simulation",
        },
        "evolution_parent_policy": {
            "mutation": (
                "Use evaluated non-ACTIVE trajectories. Let the recorded failure choose one explicit change. "
                "A child outcome judges that action only and never retires its parent."
            ),
            "crossover": (
                "Combine recorded parent evidence without cluster quotas, lineage caps, or thin-wrapper copying."
            ),
            "diversity": (
                "Similarity is a thin-wrapper guardrail, not an objective to maximize orthogonality."
            ),
        },
    }


def _is_active_adjacent(
    evaluation: dict[str, Any],
    candidate: dict[str, Any],
    active_references: list[dict[str, Any]],
    catalog: FieldCatalog,
) -> bool:
    if any(
        str(evaluation.get("alpha_id") or "") == str(item.get("alpha_id") or "")
        for item in active_references
    ):
        # A confirmed ACTIVE trajectory is valuable evidence for orthogonal
        # mutation. Its children still face the normal anti-wrapper gates.
        return False
    expression = str(candidate.get("expression") or "")
    for item in active_references:
        similarity = active_expression_similarity(
            expression, str(item.get("expression") or ""), catalog
        )
        if (
            similarity["structural_similarity"] >= ACTIVE_STRUCTURE_FLOOR
            and similarity["active_core_field_containment"]
            >= ACTIVE_CORE_CONTAINMENT_LIMIT
        ):
            return True
    return False


def command_init(args: argparse.Namespace) -> int:
    run_id = args.run_id or datetime.now(timezone.utc).strftime("qa-%Y%m%dT%H%M%SZ")
    if args.directions < 2 or args.directions > len(DEFAULT_DIRECTIONS):
        raise ValueError(f"directions must be between 2 and {len(DEFAULT_DIRECTIONS)}")
    disabled = set(args.disable_component or [])
    components = {
        "diversified_planning": "planning" not in disabled,
        "mutation": "mutation" not in disabled,
        "crossover": "crossover" not in disabled,
        "semantic_gate": "semantic" not in disabled,
        "complexity_gate": "complexity" not in disabled,
        "redundancy_gate": "redundancy" not in disabled,
    }
    directions = DEFAULT_DIRECTIONS[: args.directions]
    if not components["diversified_planning"]:
        directions = directions[:1]
    store = ResearchStore(_run_root(args), run_id)
    run = store.initialize(
        iterations=args.iterations,
        max_iterations=args.max_iterations,
        directions=directions,
        components=components,
        budget={
            "max_candidates_per_direction": args.candidates_per_direction,
            "max_repair_attempts": args.repair_attempts,
            "max_api_requests": args.max_api_requests,
            "max_elapsed_hours": args.max_elapsed_hours,
        },
    )
    packet = {
        "run_id": run_id,
        "instruction": (
            f"Generate at most {args.candidates_per_direction} candidates per direction. Each candidate must follow candidate_schema.json, "
            "use only catalogued fields, state observable proxies and failure modes, and differ in mechanism "
            "or data source rather than only window length. Read memory_context first and do not preserve "
            "the complete core signal of an ACTIVE reference inside a thin wrapper."
        ),
        "directions": run["directions"],
        "components": run["components"],
        "budget": run["budget"],
        "memory_context": _memory_context(_catalog(), store),
    }
    atomic_write_json(store.path / "planning_packet.json", packet)
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    return 0


def command_register(args: argparse.Namespace) -> int:
    store = ResearchStore(_run_root(args), args.run_id)
    candidate = _load_object(Path(args.candidate))
    catalog = _catalog()
    validation = validate_candidate(
        candidate,
        catalog,
        existing=[value for value in store.candidates() if value.get("validation", {}).get("passed")],
        config=GateConfig(**store.load_run().get("gate_config", {})),
    )
    registered = store.register_candidate(candidate, validation)
    print(json.dumps(registered, ensure_ascii=False, indent=2))
    return 0 if validation["passed"] else 2


def command_register_batch(args: argparse.Namespace) -> int:
    store = ResearchStore(_run_root(args), args.run_id)
    catalog = _catalog()
    existing = [
        value for value in store.candidates() if value.get("validation", {}).get("passed")
    ]
    results = []
    passed = 0
    for candidate in _load_objects(Path(args.input)):
        validation = validate_candidate(
            candidate,
            catalog,
            existing=existing,
            config=GateConfig(**store.load_run().get("gate_config", {})),
        )
        registered = store.register_candidate(candidate, validation)
        results.append(
            {
                "candidate_id": registered["candidate_id"],
                "direction_id": registered.get("direction_id"),
                "passed": validation["passed"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
            }
        )
        if validation["passed"]:
            passed += 1
            existing.append(registered)
    summary = {
        "run_id": args.run_id,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed == len(results) else 2


def command_continue_run(args: argparse.Namespace) -> int:
    """Start a fresh governed budget while retaining prior trajectory evidence."""
    root = _run_root(args)
    source = ResearchStore(root, args.source_run_id)
    source_run = source.load_run()
    target = ResearchStore(root, args.run_id)
    target_run = target.initialize(
        iterations=int(source_run.get("target_iterations", 5)),
        max_iterations=int(source_run.get("max_iterations", 15)),
        directions=source_run.get("directions", DEFAULT_DIRECTIONS),
        components=source_run.get("components", {}),
        budget={
            **source_run.get("budget", {}),
            "max_api_requests": args.max_api_requests,
            "max_elapsed_hours": args.max_elapsed_hours,
        },
        gate_config=GateConfig(**source_run.get("gate_config", {})),
    )

    for candidate in source.candidates():
        target.register_candidate(candidate, candidate.get("validation", {}))
    for evaluation in source.evaluations():
        target.record_evaluation(evaluation)

    atomic_write_json(target.pool_path, read_json(source.pool_path, {"members": []}))
    active_snapshot = read_json(source.path / "active_snapshot.json", None)
    if isinstance(active_snapshot, dict):
        atomic_write_json(target.path / "active_snapshot.json", active_snapshot)

    target_run["iteration"] = int(source_run.get("iteration", 0))
    target_run["status"] = "EVOLVING"
    target_run["continuation"] = {
        "source_run_id": args.source_run_id,
        "source_iteration": int(source_run.get("iteration", 0)),
        "imported_candidates": len(source.candidates()),
        "imported_evaluations": len(source.evaluations()),
        "api_budget_carryover": 0,
        "reason": args.reason,
    }
    atomic_write_json(target.run_path, target_run)
    target.record_event(
        {
            "event": "continuation_imported",
            "source_run_id": args.source_run_id,
            "source_iteration": int(source_run.get("iteration", 0)),
            "imported_candidates": len(source.candidates()),
            "imported_evaluations": len(source.evaluations()),
            "api_requests": 0,
        }
    )
    manifest = {
        "generated_at": utc_now(),
        "type": "governed_budget_continuation",
        "source_run_id": args.source_run_id,
        "target_run_id": args.run_id,
        "source_iteration": int(source_run.get("iteration", 0)),
        "imported_candidates": len(source.candidates()),
        "imported_evaluations": len(source.evaluations()),
        "fresh_budget": target_run["budget"],
        "historical_api_requests_charged_to_target": 0,
        "reason": args.reason,
    }
    atomic_write_json(target.path / "continuation_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def command_merge_run(args: argparse.Namespace) -> int:
    """Merge selected candidates and their completed evaluations into one logical run."""
    root = _run_root(args)
    source = ResearchStore(root, args.source_run_id)
    target = ResearchStore(root, args.run_id)
    selected_ids = {candidate_id(value) for value in _load_objects(Path(args.input))}
    target_candidate_ids = {
        str(value.get("candidate_id")) for value in target.candidates()
    }
    imported_candidates = 0
    for value in source.candidates():
        cid = str(value.get("candidate_id") or "")
        if cid not in selected_ids or cid in target_candidate_ids:
            continue
        target.register_candidate(value, value.get("validation", {}))
        target_candidate_ids.add(cid)
        imported_candidates += 1

    existing_evaluation_keys = {
        (
            str(value.get("candidate_id") or ""),
            str(value.get("alpha_id") or ""),
            str(value.get("evaluated_at") or ""),
        )
        for value in target.evaluations()
    }
    imported_evaluations = 0
    for value in source.evaluations():
        cid = str(value.get("candidate_id") or "")
        key = (cid, str(value.get("alpha_id") or ""), str(value.get("evaluated_at") or ""))
        if cid not in selected_ids or key in existing_evaluation_keys:
            continue
        target.record_evaluation(value)
        existing_evaluation_keys.add(key)
        imported_evaluations += 1

    source_snapshot = read_json(source.path / "active_snapshot.json", None)
    if isinstance(source_snapshot, dict):
        atomic_write_json(target.path / "active_snapshot.json", source_snapshot)
    source_tasks = read_json(source.path / args.tasks_name, None)
    if isinstance(source_tasks, dict):
        atomic_write_json(target.path / args.tasks_name, source_tasks)
    atomic_write_json(target.path / Path(args.input).name, read_json(Path(args.input), []))

    target_run = target.load_run()
    source_run = source.load_run()
    target_run["iteration"] = max(
        int(target_run.get("iteration", 0)), int(source_run.get("iteration", 0))
    )
    target_run["budget"]["max_api_requests"] = args.max_api_requests
    target_run["continuation_merge"] = {
        "source_run_id": args.source_run_id,
        "imported_candidates": imported_candidates,
        "imported_evaluations": imported_evaluations,
        "interrupted_api_requests_estimate": args.estimated_api_requests,
        "single_logical_run": True,
    }
    atomic_write_json(target.run_path, target_run)
    target.record_event(
        {
            "event": "batch_interrupted",
            "source_run_id": args.source_run_id,
            "candidate_count": imported_evaluations,
            "api_requests": args.estimated_api_requests,
            "api_requests_estimated": True,
            "reason": "user requested single-run continuation while the batch was in progress",
        }
    )
    source_run["status"] = "INTERRUPTED_MERGED"
    source_run["merged_into_run_id"] = args.run_id
    atomic_write_json(source.run_path, source_run)
    report = {
        "source_run_id": args.source_run_id,
        "target_run_id": args.run_id,
        "selected_candidates": len(selected_ids),
        "imported_candidates": imported_candidates,
        "imported_evaluations": imported_evaluations,
        "target_iteration": target_run["iteration"],
        "target_max_api_requests": args.max_api_requests,
        "interrupted_api_requests_estimate": args.estimated_api_requests,
    }
    atomic_write_json(target.path / "group6_merge_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _candidate_index(store: ResearchStore) -> dict[str, dict[str, Any]]:
    return {
        str(candidate["candidate_id"]): candidate
        for candidate in store.candidates()
        if candidate.get("candidate_id")
    }


def _submission_state(evaluation: dict[str, Any]) -> dict[str, Any]:
    state = submission_eligibility(evaluation.get("metrics", {}))
    active_confirmed = (
        str(evaluation.get("stage") or "").upper() == "ACTIVE"
        or str(evaluation.get("metrics", {}).get("status") or "").upper() == "ACTIVE"
    )
    if active_confirmed:
        state = {
            **state,
            "eligible": True,
            "grade_eligible": True,
            "active_confirmed": True,
            "blockers": [],
        }
    return {**state, "confirmed_parent": active_confirmed}


def _account_enriched_evaluations(
    evaluations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay newer account snapshots on immutable run evaluations."""
    database = read_json(ALPHA_DB_PATH, {"alphas": {}})
    alphas = database.get("alphas", {}) if isinstance(database, dict) else {}
    if not isinstance(alphas, dict):
        return evaluations
    enriched = []
    for evaluation in evaluations:
        value = dict(evaluation)
        alpha = alphas.get(str(evaluation.get("alpha_id") or ""), {})
        fingerprint = alpha.get("fingerprint", {}) if isinstance(alpha, dict) else {}
        account_metrics = fingerprint.get("metrics", {}) if isinstance(fingerprint, dict) else {}
        if isinstance(account_metrics, dict) and account_metrics:
            metrics = dict(evaluation.get("metrics", {}))
            metrics.update({key: item for key, item in account_metrics.items() if item is not None})
            if fingerprint.get("status") is not None:
                metrics["status"] = fingerprint.get("status")
            value["metrics"] = metrics
        enriched.append(value)
    return enriched


def _reward_value(evaluation: dict[str, Any]) -> float:
    value = evaluation.get("reward", {}).get("reward")
    return float(value) if value is not None else -999.0


def _parent_score(evaluation: dict[str, Any]) -> float:
    """Use the recorded trajectory reward without extra parent-allocation formulas."""
    return _reward_value(evaluation)


def _evolution_eligible(evaluation: dict[str, Any]) -> bool:
    metrics = evaluation.get("metrics")
    if not isinstance(metrics, dict):
        return False
    stage = str(evaluation.get("stage", ""))
    sharpe = float(metrics.get("sharpe") or 0.0)
    fitness = float(metrics.get("fitness") or 0.0)
    evaluated_stage = (
        stage.startswith("SIMULATED")
        or stage == "ACTIVE"
        or stage == "SUBMISSION_REJECTED_OR_UNRESOLVED"
    )
    return evaluated_stage and sharpe > 0.0 and fitness >= 0.0


def _field_category(field: str, catalog: FieldCatalog) -> str:
    value = catalog.get(field) or {}
    category = value.get("category", {})
    return str(category.get("id") or "unknown") if isinstance(category, dict) else "unknown"


def _mechanism_profile(candidate: dict[str, Any], catalog: FieldCatalog) -> dict[str, Any]:
    """Build a stable dominant-mechanism label rather than trusting submission status."""
    expression = str(candidate.get("expression") or "").lower()
    hypothesis = candidate.get("hypothesis", {})
    mechanism = str(hypothesis.get("mechanism") or "").lower() if isinstance(hypothesis, dict) else ""
    direction = str(candidate.get("direction_id") or "").lower()
    text = " ".join((expression, mechanism, direction))
    fields = core_signal_fields(expression, catalog)
    categories = sorted({_field_category(field, catalog) for field in fields})

    if "analyst" in categories:
        if any(token in text for token in ("revision", "revise", "disagreement", "修正", "分歧")) or "ts_delta" in expression:
            dominant = "analyst-change"
        else:
            dominant = "analyst-level"
    elif "fundamental" in categories:
        dominant = "fundamental-change" if "ts_delta" in expression or "变化" in text or "改善" in text else "fundamental-level"
    elif "option" in categories:
        dominant = "option-volatility"
    elif "news" in categories or "socialmedia" in categories:
        dominant = "news-attention"
    elif "pv" in categories:
        reversal_tokens = ("reversal", "反转", "-returns", "-ts_sum(returns", "-(close / open")
        dominant = "price-reversal" if any(token in text for token in reversal_tokens) else "price-volume"
    elif "model" in categories:
        dominant = "model-signal"
    else:
        dominant = "other"

    if "trade_when" in expression or "if_else" in expression:
        transformation = "conditional"
    elif "ts_delta" in expression:
        transformation = "change"
    elif "*" in expression:
        transformation = "interaction"
    elif "ts_mean" in expression or "ts_decay" in expression:
        transformation = "smoothed"
    else:
        transformation = "level"

    dominant_category = dominant.split("-", 1)[0]
    dominant_fields = sorted(
        field
        for field in fields
        if _field_category(field, catalog) == dominant_category
        or (dominant.startswith("price-") and _field_category(field, catalog) == "pv")
        or (dominant == "news-attention" and _field_category(field, catalog) in {"news", "socialmedia"})
        or (dominant == "option-volatility" and _field_category(field, catalog) == "option")
    )
    return {
        "cluster": dominant,
        "transformation": transformation,
        "categories": categories,
        "dominant_fields": dominant_fields,
    }


def _mutation_parent_order(
    evaluations: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    catalog: FieldCatalog,
    limit: int,
) -> list[dict[str, Any]]:
    """Select useful non-ACTIVE parents without cluster, lineage, or quota caps."""
    del catalog
    return sorted(
        (
            evaluation
            for evaluation in evaluations
            if _evolution_eligible(evaluation)
            and str(evaluation.get("candidate_id")) in candidates
            and not _submission_state(evaluation).get("active_confirmed")
        ),
        key=_parent_score,
        reverse=True,
    )[:limit]


def _evaluation_failures(evaluation: dict[str, Any]) -> list[str]:
    failures = set(evaluation.get("reward", {}).get("metric_gate", {}).get("failures", []))
    for check in evaluation.get("metrics", {}).get("checks", []):
        if isinstance(check, dict) and str(check.get("result") or "").upper() == "FAIL":
            failures.add(str(check.get("name") or "UNKNOWN_CHECK"))
    failures.update(str(value) for value in evaluation.get("governance_warnings", []))
    return sorted(value for value in failures if value)


def _lineage_feedback_history(
    candidate_id_value: str,
    candidates: dict[str, dict[str, Any]],
    evaluations: dict[str, dict[str, Any]],
    *,
    maximum: int = 6,
) -> list[dict[str, Any]]:
    """Return concise candidate-level history instead of a lossy batch report."""
    pending = [candidate_id_value]
    seen: set[str] = set()
    values: list[dict[str, Any]] = []
    while pending and len(values) < maximum:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)
        candidate = candidates.get(current)
        if not candidate:
            continue
        evaluation = evaluations.get(current, {})
        metrics = evaluation.get("metrics", {}) if isinstance(evaluation, dict) else {}
        values.append(
            {
                "candidate_id": current,
                "iteration": candidate.get("iteration"),
                "operation": candidate.get("operation"),
                "direction_id": candidate.get("direction_id"),
                "expression": candidate.get("expression"),
                "stage": evaluation.get("stage"),
                "sharpe": metrics.get("sharpe"),
                "fitness": metrics.get("fitness"),
                "turnover": metrics.get("turnover"),
                "reward": evaluation.get("reward", {}).get("reward"),
                "failures": _evaluation_failures(evaluation),
                "parent_feedback": evaluation.get("parent_feedback"),
            }
        )
        pending.extend(str(value) for value in candidate.get("parents", []) if value)
    return values


def _parent_attempt_history(
    parent_id: str,
    candidates: dict[str, dict[str, Any]],
    evaluations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return outcomes of concrete mutation actions tried on one parent."""
    attempts: list[dict[str, Any]] = []
    for child_id, child in candidates.items():
        if parent_id not in {str(value) for value in child.get("parents", []) if value}:
            continue
        evaluation = evaluations.get(child_id, {})
        feedback = evaluation.get("parent_feedback", {}) if isinstance(evaluation, dict) else {}
        comparison = next(
            (
                item
                for item in feedback.get("comparisons", [])
                if isinstance(item, dict) and str(item.get("parent_id")) == parent_id
            ),
            {},
        )
        trace = child.get("generation_trace", {}) if isinstance(child, dict) else {}
        action_id = str(trace.get("action_id") or "")
        if not action_id and trace.get("source") == "research_prior" and trace.get("recipe_id"):
            action_id = f"research_prior:{trace.get('recipe_id')}:{trace.get('architecture')}"
        if not action_id and trace.get("source") == "parent_realization" and trace.get("architecture"):
            action_id = f"parent_realization:{trace.get('fault')}:{trace.get('architecture')}"
        if not action_id:
            continue
        attempts.append(
            {
                "child_id": child_id,
                "action_id": action_id,
                "outcome": comparison.get("outcome"),
                "reward_delta": comparison.get("reward_delta"),
                "resolved_failures": comparison.get("resolved_failures", []),
                "introduced_failures": comparison.get("introduced_failures", []),
            }
        )
    return attempts


def _repair_card(
    candidate_id_value: str,
    candidate: dict[str, Any],
    evaluation: dict[str, Any],
    diagnosis: dict[str, Any],
    profile: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    evaluations: dict[str, dict[str, Any]],
    catalog: FieldCatalog,
) -> dict[str, Any]:
    fault = str(diagnosis.get("fault") or "risk_or_saturation")
    modification_depth = str(diagnosis.get("modification_depth") or "targeted")
    must_keep_fields = (
        list(profile.get("dominant_fields", []))
        if modification_depth in {"implementation", "realization"}
        else []
    )
    attempts = _parent_attempt_history(candidate_id_value, candidates, evaluations)
    failed_action_ids = sorted(
        {str(item["action_id"]) for item in attempts if item.get("outcome") == "WORSE"}
    )
    return {
        "version": 2,
        "parent_id": candidate_id_value,
        "fault": fault,
        "failure_reasons": _evaluation_failures(evaluation),
        "must_keep": list(diagnosis.get("freeze", [])),
        "must_keep_fields": must_keep_fields,
        "must_change": list(diagnosis.get("revise", [])),
        "forbidden": ["reuse the identical expression", "repeat a failed action_id"],
        "instruction": diagnosis.get("instruction"),
        "maximum_parent_structural_similarity": 0.90,
        "maximum_parent_core_retention": 1.0,
        "require_neutralization_or_core_change": fault == "exposure",
        "parent_core_fields": sorted(
            core_signal_fields(str(candidate.get("expression") or ""), catalog)
        ),
        "latest_parent_feedback": evaluation.get("parent_feedback"),
        "previous_attempts": attempts,
        "failed_action_ids": failed_action_ids,
        "attempt_scope": "Judge this mutation action only; never retire the parent from one child result.",
        "lineage_history": _lineage_feedback_history(
            candidate_id_value, candidates, evaluations
        ),
    }


def _assign_expression_budgets(
    briefs: list[dict[str, Any]], simulation_budget: int, max_per_hypothesis: int = 3
) -> list[dict[str, Any]]:
    """Allocate expensive simulations across trajectory tasks, capped as in the paper."""
    if simulation_budget < 1 or not briefs:
        return []
    selected = briefs[: min(len(briefs), simulation_budget)]
    budgets = [1] * len(selected)
    remaining = simulation_budget - len(selected)
    while remaining > 0 and any(value < max_per_hypothesis for value in budgets):
        for index in range(len(budgets)):
            if remaining <= 0:
                break
            if budgets[index] < max_per_hypothesis:
                budgets[index] += 1
                remaining -= 1
    for brief, budget in zip(selected, budgets):
        brief["expression_budget"] = budget
        brief["realization_contract"] = (
            f"Generate exactly {budget} candidates under one coherent child hypothesis. "
            "Use structurally distinct realizations; window-only or weight-only variants do not count."
        )
    return selected


def _mutation_briefs(
    evaluations: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    catalog: FieldCatalog,
    limit: int,
) -> list[dict[str, Any]]:
    ranked = _mutation_parent_order(evaluations, candidates, catalog, limit)
    evaluation_index = {
        str(evaluation.get("candidate_id")): evaluation
        for evaluation in evaluations
        if evaluation.get("candidate_id")
    }
    briefs = []
    for evaluation in ranked:
        candidate_id = str(evaluation.get("candidate_id"))
        candidate = candidates.get(candidate_id)
        if not candidate:
            continue
        submit_state = _submission_state(evaluation)
        diagnosis = diagnose_evaluation(evaluation)
        profile = _mechanism_profile(candidate, catalog)
        repair_card = _repair_card(
            candidate_id,
            candidate,
            evaluation,
            diagnosis,
            profile,
            candidates,
            evaluation_index,
            catalog,
        )
        market_settings = {
            key: value
            for key, value in candidate.get("settings", {}).items()
            if key in {"instrumentType", "region", "universe", "delay", "language", "visualization"}
        }
        preserve_hypothesis = diagnosis.get("modification_depth") in {
            "implementation",
            "realization",
            "targeted",
        }
        frozen_payload: dict[str, Any] = {"market_settings": market_settings}
        if preserve_hypothesis:
            frozen_payload["hypothesis"] = candidate.get("hypothesis")
            frozen_payload["direction_id"] = candidate.get("direction_id")
        briefs.append(
            {
                "operation": "mutation",
                "parent": candidate_id,
                "parent_reward": _reward_value(evaluation),
                "parent_submission_state": submit_state,
                "fault_localization": diagnosis,
                "repair_card": repair_card,
                "frozen_payload": frozen_payload,
                "expression_budget": 1,
                "instruction": (
                    "Create exactly one child with exactly one explicit change chosen from the diagnosed failure. "
                    "Read failed_action_ids and do not repeat an action that already made this parent worse. "
                    "A poor child is evidence against that action only; it never retires the parent."
                ),
            }
        )
    return briefs


def _pair_score(
    left_eval: dict[str, Any],
    right_eval: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
    catalog: FieldCatalog,
) -> float:
    left_fields = set(referenced_fields(str(left.get("expression", "")), catalog))
    right_fields = set(referenced_fields(str(right.get("expression", "")), catalog))
    union = left_fields | right_fields
    field_overlap = len(left_fields & right_fields) / max(1, len(union))
    structure = structural_similarity(
        str(left.get("expression", "")), str(right.get("expression", "")), catalog
    )
    pnl_corr = aligned_correlation(left_eval.get("pnl", []), right_eval.get("pnl", []))
    corr = pnl_corr.get("correlation")
    correlation_penalty = abs(float(corr)) if corr is not None else 0.50
    left_failures = set(left_eval.get("reward", {}).get("metric_gate", {}).get("failures", []))
    right_failures = set(right_eval.get("reward", {}).get("metric_gate", {}).get("failures", []))
    failure_union = left_failures | right_failures
    failure_overlap = len(left_failures & right_failures) / max(1, len(failure_union))
    quality = (_parent_score(left_eval) + _parent_score(right_eval)) / 2
    direction_bonus = 0.05 if left.get("direction_id") != right.get("direction_id") else 0.0
    return (
        quality
        + 0.10 * (1 - field_overlap)
        + 0.10 * (1 - structure)
        + 0.10 * (1 - correlation_penalty)
        + 0.05 * (1 - failure_overlap)
        + direction_bonus
    )


def _crossover_briefs(
    evaluations: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    catalog: FieldCatalog,
    limit: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        (
            evaluation
            for evaluation in evaluations
            if _evolution_eligible(evaluation)
            and str(evaluation.get("candidate_id")) in candidates
        ),
        key=_parent_score,
        reverse=True,
    )
    evaluation_index = {
        str(evaluation.get("candidate_id")): evaluation
        for evaluation in evaluations
        if evaluation.get("candidate_id")
    }
    eligible = ranked[: max(6, math.ceil(len(ranked) * 0.70))]
    ranked_pairs = []
    for index, left_eval in enumerate(eligible):
        for right_eval in eligible[index + 1 :]:
            left_id = str(left_eval["candidate_id"])
            right_id = str(right_eval["candidate_id"])
            left = candidates[left_id]
            right = candidates[right_id]
            left_profile = _mechanism_profile(left, catalog)
            right_profile = _mechanism_profile(right, catalog)
            score = _pair_score(left_eval, right_eval, left, right, catalog)
            ranked_pairs.append(
                (score, left_eval, right_eval, left, right, left_profile, right_profile)
            )
    ranked_pairs.sort(key=lambda item: item[0], reverse=True)

    briefs = []
    for score, left_eval, right_eval, left, right, left_profile, right_profile in ranked_pairs:
        if len(briefs) >= limit:
            break
        left_id = str(left["candidate_id"])
        right_id = str(right["candidate_id"])
        briefs.append(
            {
                "operation": "crossover",
                "parents": [left_id, right_id],
                "pair_score": score,
                "parent_evolution_scores": [_parent_score(left_eval), _parent_score(right_eval)],
                "parent_mechanism_profiles": [left_profile, right_profile],
                "parent_hypotheses": [left.get("hypothesis"), right.get("hypothesis")],
                "parent_metrics": [left_eval.get("metrics"), right_eval.get("metrics")],
                "generation_card": {
                    "version": 1,
                    "must_use_parent_decisions": [
                        {
                            "parent_id": left_id,
                            "mechanism_profile": left_profile,
                            "lineage_history": _lineage_feedback_history(
                                left_id, candidates, evaluation_index
                            ),
                        },
                        {
                            "parent_id": right_id,
                            "mechanism_profile": right_profile,
                            "lineage_history": _lineage_feedback_history(
                                right_id, candidates, evaluation_index
                            ),
                        },
                    ],
                    "active_parent_ids": [
                        parent_id
                        for parent_id, parent_evaluation in (
                            (left_id, left_eval),
                            (right_id, right_eval),
                        )
                        if _submission_state(parent_evaluation).get("active_confirmed")
                    ],
                    "maximum_active_parent_core_retention": 0.79,
                    "forbidden": [
                        "copy either complete parent expression",
                        "retain the complete ACTIVE parent core and add a decorative field",
                        "concatenate expression strings without one coherent mechanism",
                    ],
                },
                "inheritance_contract": (
                    "Inherit one validated decision segment from each parent. Do not copy either complete expression "
                    "or retain an ACTIVE parent's full dominant core. Keep predictive quality primary; use similarity "
                    "only to block thin wrappers, not to maximize orthogonality."
                ),
                "instruction": (
                    "Synthesize one coherent mechanism from parents with different dominant information sources. "
                    "Reuse validated hypothesis, construction, or repair decisions rather than expression strings. "
                    "Do not concatenate formulas or weaken a strong signal merely to look orthogonal. Every claim "
                    "must have an observable proxy, and the child must pass thin-wrapper and final correlation gates."
                ),
            }
        )
    return briefs


def _require_completed_mutation_phase(
    store: ResearchStore,
    run: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Keep Crossover downstream of the current cycle's evaluated Mutation pool."""
    mutation_iteration = int(run.get("iteration", 0))
    packet_path = store.path / f"iteration_{mutation_iteration:02d}_tasks.json"
    packet = read_json(packet_path)
    if not isinstance(packet, dict) or packet.get("phase") != "mutation":
        raise ValueError(
            "crossover requires the immediately preceding task packet to be a mutation phase"
        )
    mutation_tasks = packet.get("mutation", [])
    expected = sum(
        int(task.get("expression_budget", 0))
        for task in mutation_tasks
        if isinstance(task, dict)
    )
    if expected <= 0:
        raise ValueError("preceding mutation packet has no positive simulation budget")
    registered_ids = {
        candidate_id_value
        for candidate_id_value, candidate in candidates.items()
        if candidate.get("operation") == "mutation"
        and int(candidate.get("iteration", -1)) == mutation_iteration
    }
    evaluated_ids = {
        str(evaluation.get("candidate_id"))
        for evaluation in evaluations
        if str(evaluation.get("candidate_id")) in registered_ids
    }
    if len(evaluated_ids) < expected:
        raise ValueError(
            "crossover blocked until the preceding mutation phase is evaluated: "
            f"iteration={mutation_iteration}, expected={expected}, "
            f"registered={len(registered_ids)}, evaluated={len(evaluated_ids)}"
        )
    return {
        "mutation_iteration": mutation_iteration,
        "expected_evaluations": expected,
        "registered_children": len(registered_ids),
        "evaluated_children": len(evaluated_ids),
    }


def command_next(args: argparse.Namespace) -> int:
    store = ResearchStore(_run_root(args), args.run_id)
    run = store.load_run()
    candidates = _candidate_index(store)
    evaluations = _account_enriched_evaluations(
        list(latest_evaluations(store.evaluations()).values())
    )
    if not evaluations:
        raise ValueError("no evaluations available; simulate registered candidates first")
    catalog = _catalog()
    evolution_evaluations = [
        evaluation
        for evaluation in evaluations
        if candidates.get(str(evaluation.get("candidate_id")))
    ]
    if not evolution_evaluations:
        raise ValueError("no evaluated trajectories have registered candidates")
    next_iteration = int(run.get("iteration", 0)) + 1
    if next_iteration > int(run.get("max_iterations", 15)) * 3:
        raise ValueError("maximum iteration count reached")
    include_mutation = args.phase == "mutation" and run.get("components", {}).get("mutation", True)
    include_crossover = args.phase == "crossover" and run.get("components", {}).get("crossover", True)
    phase_prerequisite = (
        _require_completed_mutation_phase(
            store, run, candidates, evolution_evaluations
        )
        if include_crossover
        else None
    )
    mutation = (
        _mutation_briefs(
            evolution_evaluations,
            candidates,
            catalog,
            min(args.mutations, args.mutation_simulations),
        )
        if include_mutation
        else []
    )
    crossover = (
        _assign_expression_budgets(
            _crossover_briefs(evolution_evaluations, candidates, catalog, args.crossovers),
            args.crossover_simulations,
        )
        if include_crossover
        else []
    )
    packet = {
        "run_id": args.run_id,
        "iteration": next_iteration,
        "phase": args.phase,
        "phase_prerequisite": phase_prerequisite,
        "mutation": mutation,
        "crossover": crossover,
        "simulation_budget": sum(
            item["expression_budget"] for item in mutation + crossover
        ),
        "paper_cycle_20_contract": {
            "mutation_simulations": 14,
            "crossover_simulations": 6,
            "phase_order": ["mutation", "crossover"],
            "instruction": (
                "Run mutation first. Register and simulate its children, then generate a fresh crossover "
                "packet so crossover can use the newly evaluated trajectories."
            ),
        },
        "generation_contract": {
            "max_expressions_per_hypothesis": 3,
            "expression_budget_is_exact": True,
            "mutation_children_per_parent_task": 1,
            "mutation_parent_is_never_retired_by_one_child": True,
            "failed_mutation_action_must_not_be_repeated": True,
            "semantic_consistency_required": True,
            "compile_and_simulation_repair_budget": 2,
            "test_or_hidden_submission_metrics_must_not_guide_evolution": True,
            "feedback_driven_generation": True,
            "feedback_generation_version": 2,
            "history_scope": "all evaluated trajectories plus concrete action outcomes for the selected parent",
        },
        "memory_context": _memory_context(catalog, store),
    }
    packet_path = store.path / f"iteration_{next_iteration:02d}_tasks.json"
    atomic_write_json(packet_path, packet)
    run["iteration"] = next_iteration
    run["status"] = "EVOLVING"
    atomic_write_json(store.run_path, run)
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    return 0


def command_pool(args: argparse.Namespace) -> int:
    store = ResearchStore(_run_root(args), args.run_id)
    run = store.load_run()
    redundancy_enabled = run.get("components", {}).get("redundancy_gate", True)
    catalog = _catalog()
    candidates = _candidate_index(store)
    evaluations = list(latest_evaluations(store.evaluations()).values())
    eligible = []
    rejected = []
    active_snapshot = read_json(store.path / "active_snapshot.json", {"active": []})
    active_ids = {
        str(item.get("alpha_id"))
        for item in active_snapshot.get("active", [])
        if isinstance(item, dict) and item.get("alpha_id")
    }
    for evaluation in evaluations:
        candidate = candidates.get(str(evaluation.get("candidate_id")))
        if not candidate or not candidate.get("validation", {}).get("passed"):
            continue
        if not evaluation.get("reward", {}).get("metric_gate", {}).get("passed"):
            continue
        is_active = (
            str(evaluation.get("alpha_id") or "") in active_ids
            or str(evaluation.get("metrics", {}).get("status", "")).upper() == "ACTIVE"
        )
        unresolved_checks = [
            f"{item.get('name')}:{item.get('result')}"
            for item in evaluation.get("metrics", {}).get("checks", [])
            if str(item.get("result", "")).upper() != "PASS"
        ]
        if not is_active and unresolved_checks:
            rejected.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "reason": "unresolved_is_checks=" + ",".join(unresolved_checks),
                }
            )
            continue
        if "ACTIVE_EXPRESSION_REDUNDANCY" in evaluation.get("submission_blockers", []):
            rejected.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "reason": "active_expression_redundancy",
                }
            )
            continue
        correlation = evaluation.get("max_active_correlation")
        if redundancy_enabled and correlation is not None and abs(float(correlation)) >= args.max_corr:
            continue
        eligible.append((candidate, evaluation))
    eligible.sort(key=lambda item: _reward_value(item[1]), reverse=True)
    cap = min(args.max_size, max(1, math.ceil(len(eligible) * args.pool_fraction)))
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidate, evaluation in eligible:
        reason = None
        for selected_candidate, selected_evaluation in selected:
            similarity = structural_similarity(
                candidate["expression"], selected_candidate["expression"], catalog
            )
            if redundancy_enabled and similarity >= args.max_structure:
                reason = f"structural_similarity={similarity:.3f}"
                break
            correlation = aligned_correlation(
                evaluation.get("pnl", []), selected_evaluation.get("pnl", [])
            ).get("correlation")
            if redundancy_enabled and correlation is not None and abs(float(correlation)) >= args.max_corr:
                reason = f"pool_pnl_correlation={correlation:.3f}"
                break
        if reason:
            rejected.append({"candidate_id": candidate["candidate_id"], "reason": reason})
            continue
        selected.append((candidate, evaluation))
        if len(selected) >= cap:
            break

    pool = {
        "updated_at": utc_now(),
        "run_id": args.run_id,
        "selection_rule": {
            "pool_fraction": args.pool_fraction,
            "max_size": args.max_size,
            "max_pnl_correlation": args.max_corr,
            "max_structural_similarity": args.max_structure,
            "sort": "trajectory_reward_descending",
            "redundancy_gate_enabled": redundancy_enabled,
        },
        "members": [
            {
                "candidate_id": candidate["candidate_id"],
                "alpha_id": evaluation.get("alpha_id"),
                "reward": _reward_value(evaluation),
                "direction_id": candidate.get("direction_id"),
                "expression": candidate.get("expression"),
                "metrics": evaluation.get("metrics"),
            }
            for candidate, evaluation in selected
        ],
        "rejected": rejected,
    }
    atomic_write_json(store.pool_path, pool)
    print(json.dumps(pool, ensure_ascii=False, indent=2))
    return 0


def _runs(root: Path) -> list[dict[str, Any]]:
    output = []
    if not root.exists():
        return output
    for path in sorted(root.glob("*/run.json")):
        run = read_json(path, {})
        output.append(
            {
                "run_id": run.get("run_id"),
                "status": run.get("status"),
                "iteration": run.get("iteration"),
                "created_at": run.get("created_at"),
            }
        )
    return output


def command_status(args: argparse.Namespace) -> int:
    root = _run_root(args)
    if not args.run_id:
        print(json.dumps({"runs": _runs(root)}, ensure_ascii=False, indent=2))
        return 0
    store = ResearchStore(root, args.run_id)
    latest_values = _account_enriched_evaluations(
        list(latest_evaluations(store.evaluations()).values())
    )
    rewards = [_reward_value(value) for value in latest_values]
    submission_records = [
        {
            "candidate_id": value.get("candidate_id"),
            "alpha_id": value.get("alpha_id"),
            "stage": value.get("stage"),
            **_submission_state(value),
        }
        for value in latest_values
    ]
    output = {
        "run": store.load_run(),
        "candidate_count": len(store.candidates()),
        "evaluation_count": len(latest_values),
        "best_reward": max(rewards) if rewards else None,
        "submission_summary": {
            "eligible_count": sum(bool(item["eligible"]) for item in submission_records),
            "eligible_factors": [item for item in submission_records if item["eligible"]],
        },
        "factor_pool": read_json(store.pool_path, {"members": []}),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _evidence_band(count: int) -> str:
    if count < 3:
        return "insufficient"
    if count < 10:
        return "3-9"
    if count < 30:
        return "10-29"
    return "30+"


def command_promote(args: argparse.Namespace) -> int:
    store = ResearchStore(_run_root(args), args.run_id)
    candidates = _candidate_index(store)
    evaluations = list(latest_evaluations(store.evaluations()).values())
    faults = Counter()
    directions = Counter()
    for evaluation in evaluations:
        diagnosis = diagnose_evaluation(evaluation)
        faults[diagnosis["fault"]] += 1
        candidate = candidates.get(str(evaluation.get("candidate_id")), {})
        if candidate.get("direction_id"):
            directions[str(candidate["direction_id"])] += 1
    rewards = [_reward_value(value) for value in evaluations]
    passed_count = sum(
        1
        for evaluation in evaluations
        if evaluation.get("reward", {}).get("metric_gate", {}).get("passed")
    )
    operations = Counter(
        str(candidate.get("operation") or "unknown") for candidate in candidates.values()
    )
    minimum_support = max(3, args.min_support)
    eligible_faults = {name: count for name, count in faults.items() if count >= minimum_support}
    eligible_directions = {
        name: count for name, count in directions.items() if count >= minimum_support
    }
    observations = []
    for fault, count in sorted(eligible_faults.items()):
        observations.append(
            {
                "kind": "repeated_fault",
                "fault": fault,
                "support": _evidence_band(count),
                "action": diagnose_evaluation(
                    next(
                        evaluation
                        for evaluation in evaluations
                        if diagnose_evaluation(evaluation)["fault"] == fault
                    )
                )["instruction"],
            }
        )
    lesson = {
        "schema_version": 2,
        "generated_at": utc_now(),
        "source_run": args.run_id if not args.sanitize_run_id else "sanitized",
        "sample_size_band": _evidence_band(len(evaluations)),
        "minimum_support": minimum_support,
        "evidence_grade": "repeatable" if observations else "insufficient",
        "reward_summary": {
            "best_band": _reward_band(max(rewards) if rewards else None),
            "median_band": _reward_band(
                sorted(rewards)[len(rewards) // 2] if rewards else None
            ),
            "metric_gate_pass_rate_band": _rate_band(
                passed_count / len(evaluations) if evaluations else None
            ),
        },
        "operation_support": {
            name: _evidence_band(count) for name, count in sorted(operations.items())
        },
        "supported_directions": sorted(eligible_directions),
        "observations": observations,
        "privacy": (
            "Thresholded aggregate only. No run IDs, alpha IDs, candidate IDs, expressions, "
            "exact rewards, PnL series, or account statuses are included."
        ),
    }
    if args.apply:
        if lesson["evidence_grade"] != "repeatable":
            raise ValueError(
                "no lesson reached minimum support; keep it in the private run and gather more evidence"
            )
        existing = read_json(LESSONS_PATH, {"schema_version": 2, "lessons": []})
        existing["schema_version"] = 2
        signature = json.dumps(observations, ensure_ascii=False, sort_keys=True)
        if any(
            json.dumps(item.get("observations", []), ensure_ascii=False, sort_keys=True)
            == signature
            for item in existing.get("lessons", [])
            if isinstance(item, dict)
        ):
            print("equivalent sanitized lesson already exists; nothing promoted")
            return 0
        existing.setdefault("lessons", []).append(lesson)
        atomic_write_json(LESSONS_PATH, existing)
        print(f"promoted sanitized lesson to {LESSONS_PATH}")
    else:
        print(json.dumps(lesson, ensure_ascii=False, indent=2))
        print("preview only; use --apply after review")
    return 0


def _reward_band(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < 0:
        return "negative"
    if value < 0.5:
        return "[0,0.5)"
    if value < 1.0:
        return "[0.5,1.0)"
    return "[1.0,+inf)"


def _rate_band(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < 0.25:
        return "[0,0.25)"
    if value < 0.50:
        return "[0.25,0.50)"
    if value < 0.75:
        return "[0.50,0.75)"
    return "[0.75,1.00]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QuantaAlpha trajectory and skill evolution manager")
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="WQ-compatible mode: apply private account snapshot and sanitized lessons",
    )
    parser.add_argument("--max-pnl-fetch", type=int, default=500)
    parser.add_argument("--min-public-support", type=int, default=3)
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init", help="initialize a governed research run")
    init.add_argument("--run-id")
    init.add_argument("--directions", type=int, default=10)
    init.add_argument("--iterations", type=int, default=5)
    init.add_argument("--max-iterations", type=int, default=15)
    init.add_argument("--candidates-per-direction", type=int, default=3)
    init.add_argument("--repair-attempts", type=int, default=2)
    init.add_argument("--max-api-requests", type=int, default=2000)
    init.add_argument("--max-elapsed-hours", type=float, default=24.0)
    init.add_argument(
        "--disable-component",
        action="append",
        choices=["planning", "mutation", "crossover", "semantic", "complexity", "redundancy"],
        help="research-only ablation switch; repeat for multiple components",
    )
    init.set_defaults(func=command_init)

    register = subparsers.add_parser("register", help="validate and register one candidate JSON")
    register.add_argument("--run-id", required=True)
    register.add_argument("--candidate", required=True)
    register.set_defaults(func=command_register)

    register_batch = subparsers.add_parser(
        "register-batch", help="validate and register JSON/JSONL candidates"
    )
    register_batch.add_argument("--run-id", required=True)
    register_batch.add_argument("--input", required=True)
    register_batch.set_defaults(func=command_register_batch)

    continue_run = subparsers.add_parser(
        "continue-run",
        help="start a fresh governed API budget with imported trajectory history",
    )
    continue_run.add_argument("--source-run-id", required=True)
    continue_run.add_argument("--run-id", required=True)
    continue_run.add_argument("--max-api-requests", type=int, default=2000)
    continue_run.add_argument("--max-elapsed-hours", type=float, default=24.0)
    continue_run.add_argument(
        "--reason",
        default="Prior run reached its governed API budget; continue without charging historical requests.",
    )
    continue_run.set_defaults(func=command_continue_run)

    merge_run = subparsers.add_parser(
        "merge-run",
        help="merge selected candidates and completed evaluations into one logical run",
    )
    merge_run.add_argument("--source-run-id", required=True)
    merge_run.add_argument("--run-id", required=True)
    merge_run.add_argument("--input", required=True)
    merge_run.add_argument("--tasks-name", default="iteration_09_tasks.json")
    merge_run.add_argument("--max-api-requests", type=int, required=True)
    merge_run.add_argument("--estimated-api-requests", type=int, default=150)
    merge_run.set_defaults(func=command_merge_run)

    next_parser = subparsers.add_parser("next", help="generate one fixed mutation or crossover phase")
    next_parser.add_argument("--run-id", required=True)
    next_parser.add_argument(
        "--phase",
        choices=["mutation", "crossover"],
        default="mutation",
    )
    next_parser.add_argument("--mutations", type=int, default=14, help="one-parent/one-child mutation tasks")
    next_parser.add_argument("--crossovers", type=int, default=2, help="crossover hypothesis tasks")
    next_parser.add_argument(
        "--mutation-simulations", type=int, default=14, help="mutation phase budget"
    )
    next_parser.add_argument(
        "--crossover-simulations", type=int, default=6, help="crossover phase budget"
    )
    next_parser.set_defaults(func=command_next)

    pool = subparsers.add_parser("pool", help="rebuild the governed factor pool")
    pool.add_argument("--run-id", required=True)
    pool.add_argument("--pool-fraction", type=float, default=0.50)
    pool.add_argument("--max-size", type=int, default=150)
    pool.add_argument("--max-corr", type=float, default=0.70)
    pool.add_argument("--max-structure", type=float, default=0.90)
    pool.set_defaults(func=command_pool)

    status = subparsers.add_parser("status", help="show run status")
    status.add_argument("--run-id")
    status.set_defaults(func=command_status)

    promote = subparsers.add_parser("promote", help="preview or apply sanitized aggregate lessons")
    promote.add_argument("--run-id", required=True)
    promote.add_argument("--apply", action="store_true")
    promote.add_argument("--sanitize-run-id", action="store_true", default=True)
    promote.add_argument("--min-support", type=int, default=3)
    promote.set_defaults(func=command_promote)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        summary = sync_account(
            apply=args.apply,
            max_pnl_fetch=args.max_pnl_fetch,
            min_public_support=args.min_public_support,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if not args.apply:
            print("Preview only; alpha_db.json was not modified. Use --apply after review.")
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
