#!/usr/bin/env python3
"""Enterprise governance utilities for QuantaAlpha research runs."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core import (
    DEFAULT_DIRECTIONS,
    FieldCatalog,
    GateConfig,
    MetricPolicy,
    ResearchStore,
    aligned_correlation,
    atomic_write_json,
    candidate_id,
    iter_jsonl,
    latest_evaluations,
    read_json,
    structural_similarity,
    trajectory_reward,
    utc_now,
    validate_candidate,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_RUN_ROOT = SKILL_DIR / "private" / "research_runs"
DEFAULT_CATALOG = SKILL_DIR / "references" / "wq_usa_top3000_delay1_data_fields.json"


def _issue(issues: list[dict[str, Any]], severity: str, code: str, message: str) -> None:
    issues.append({"severity": severity, "code": code, "message": message})


def _reward(evaluation: dict[str, Any]) -> float | None:
    value = evaluation.get("reward", {}).get("reward")
    return None if value is None else float(value)


def _lineage_order_valid(parent: dict[str, Any], child: dict[str, Any]) -> bool:
    """Allow same-iteration repair nodes only when their timestamps are ordered."""
    parent_iteration = int(parent.get("iteration", -1))
    child_iteration = int(child.get("iteration", -1))
    if parent_iteration < child_iteration:
        return True
    if parent_iteration > child_iteration:
        return False
    try:
        parent_created = datetime.fromisoformat(str(parent["created_at"]))
        child_created = datetime.fromisoformat(str(child["created_at"]))
    except (KeyError, TypeError, ValueError):
        return False
    return parent_created < child_created


def command_audit(args: argparse.Namespace) -> int:
    store = ResearchStore(Path(args.run_root).expanduser().resolve(), args.run_id)
    run = store.load_run()
    candidates = store.candidates()
    evaluations = list(latest_evaluations(store.evaluations()).values())
    pool = read_json(store.pool_path, {"members": []})
    catalog = FieldCatalog(Path(args.catalog))
    gates = GateConfig(**run.get("gate_config", {}))
    policy = MetricPolicy(**run.get("metric_policy", {}))
    issues: list[dict[str, Any]] = []

    by_id: dict[str, dict[str, Any]] = {}
    prior_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        cid = str(candidate.get("candidate_id", ""))
        if not cid:
            _issue(issues, "CRITICAL", "CANDIDATE_ID_MISSING", "candidate without ID")
            continue
        if cid in by_id:
            _issue(issues, "CRITICAL", "CANDIDATE_ID_DUPLICATE", cid)
        by_id[cid] = candidate
        if candidate_id(candidate) != cid:
            _issue(issues, "CRITICAL", "CANDIDATE_HASH_MISMATCH", cid)
        operation = candidate.get("operation")
        parents = candidate.get("parents", [])
        expected_parent_count = 0 if operation == "initialization" else 1 if operation == "mutation" else 2
        if operation == "crossover":
            valid_parent_count = len(parents) >= expected_parent_count
        else:
            valid_parent_count = len(parents) == expected_parent_count
        if not valid_parent_count:
            _issue(issues, "CRITICAL", "LINEAGE_PARENT_COUNT", cid)
        for parent_id in parents:
            parent = by_id.get(str(parent_id)) or next(
                (item for item in candidates if item.get("candidate_id") == parent_id), None
            )
            if not parent:
                _issue(issues, "CRITICAL", "LINEAGE_PARENT_MISSING", f"{cid} <- {parent_id}")
                continue
            if not _lineage_order_valid(parent, candidate):
                _issue(issues, "CRITICAL", "LINEAGE_TIME_ORDER", f"{cid} <- {parent_id}")

        validation = validate_candidate(
            candidate, catalog, existing=prior_candidates, config=gates
        )
        stored = candidate.get("validation", {})
        if bool(stored.get("passed")) != bool(validation.get("passed")):
            _issue(issues, "CRITICAL", "VALIDATION_NOT_REPRODUCIBLE", cid)
        prior_candidates.append(candidate)

    eval_by_id = {str(item.get("candidate_id")): item for item in evaluations}
    for cid, evaluation in eval_by_id.items():
        candidate = by_id.get(cid)
        if not candidate:
            _issue(issues, "CRITICAL", "ORPHAN_EVALUATION", cid)
            continue
        pnl = evaluation.get("pnl", [])
        dates = [str(item.get("date")) for item in pnl if isinstance(item, dict)]
        if dates != sorted(set(dates)):
            _issue(issues, "CRITICAL", "PNL_DATE_INTEGRITY", cid)
        metrics = evaluation.get("metrics")
        complexity = candidate.get("validation", {}).get("complexity")
        stored_reward = _reward(evaluation)
        if metrics and complexity and stored_reward is not None:
            recalculated = trajectory_reward(
                metrics,
                complexity,
                max_abs_correlation=evaluation.get("max_active_correlation"),
                max_structural_similarity=evaluation.get("max_structural_similarity"),
                policy=policy,
                gates=gates,
            )["reward"]
            if abs(recalculated - stored_reward) > 1e-9:
                _issue(issues, "CRITICAL", "REWARD_NOT_REPRODUCIBLE", cid)

    members = pool.get("members", []) if isinstance(pool, dict) else []
    for member in members:
        cid = str(member.get("candidate_id", ""))
        evaluation = eval_by_id.get(cid)
        if cid not in by_id or not evaluation:
            _issue(issues, "CRITICAL", "ORPHAN_POOL_MEMBER", cid)
        elif not evaluation.get("reward", {}).get("metric_gate", {}).get("passed"):
            _issue(issues, "CRITICAL", "POOL_MEMBER_FAILED_GATE", cid)
    if run.get("components", {}).get("redundancy_gate", True):
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                left_candidate = by_id.get(str(left.get("candidate_id")), {})
                right_candidate = by_id.get(str(right.get("candidate_id")), {})
                similarity = structural_similarity(
                    str(left_candidate.get("expression", "")),
                    str(right_candidate.get("expression", "")),
                    catalog,
                )
                if similarity >= gates.max_structural_similarity:
                    _issue(
                        issues,
                        "CRITICAL",
                        "POOL_STRUCTURAL_REDUNDANCY",
                        f"{left.get('candidate_id')} vs {right.get('candidate_id')}: {similarity:.3f}",
                    )
                left_eval = eval_by_id.get(str(left.get("candidate_id")), {})
                right_eval = eval_by_id.get(str(right.get("candidate_id")), {})
                correlation = aligned_correlation(
                    left_eval.get("pnl", []), right_eval.get("pnl", [])
                ).get("correlation")
                if correlation is not None and abs(float(correlation)) >= gates.max_pnl_correlation:
                    _issue(
                        issues,
                        "CRITICAL",
                        "POOL_PNL_REDUNDANCY",
                        f"{left.get('candidate_id')} vs {right.get('candidate_id')}: {correlation:.3f}",
                    )

    direction_ids = {str(item.get("id")) for item in run.get("directions", [])}
    covered = {str(item.get("direction_id")) for item in candidates}
    if run.get("components", {}).get("diversified_planning", True):
        missing_directions = sorted(direction_ids - covered)
        if missing_directions:
            _issue(
                issues,
                "WARNING",
                "PLANNING_DIRECTIONS_UNCOVERED",
                ", ".join(missing_directions),
            )

    events = list(iter_jsonl(store.events_path))
    api_requests = sum(
        int(item.get("api_requests", 0))
        for item in events
        if item.get("event") in {"batch_finished", "batch_interrupted"}
    )
    budget = run.get("budget", {})
    if api_requests > int(budget.get("max_api_requests", 2000)):
        _issue(issues, "CRITICAL", "API_BUDGET_EXCEEDED", str(api_requests))
    if run.get("test_integrity", {}).get("use_hidden_or_submission_outcomes_for_evolution"):
        _issue(issues, "CRITICAL", "TEST_INTEGRITY_BREACH", "hidden outcomes enabled")

    report = {
        "generated_at": utc_now(),
        "run_id": args.run_id,
        "status": "PASS" if not any(item["severity"] == "CRITICAL" for item in issues) else "FAIL",
        "counts": {
            "candidates": len(candidates),
            "evaluations": len(evaluations),
            "pool_members": len(members),
            "events": len(events),
            "api_requests": api_requests,
        },
        "components": run.get("components"),
        "budget": budget,
        "issues": issues,
    }
    output = Path(args.output) if args.output else store.path / "governance_audit.json"
    atomic_write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


def _variant_components(disabled: str | None) -> dict[str, bool]:
    components = {
        "diversified_planning": True,
        "mutation": True,
        "crossover": True,
        "semantic_gate": True,
        "complexity_gate": True,
        "redundancy_gate": True,
    }
    mapping = {
        "planning": "diversified_planning",
        "mutation": "mutation",
        "crossover": "crossover",
        "semantic": "semantic_gate",
        "complexity": "complexity_gate",
        "redundancy": "redundancy_gate",
    }
    if disabled:
        components[mapping[disabled]] = False
    return components


def command_ablation(args: argparse.Namespace) -> int:
    root = Path(args.run_root).expanduser().resolve()
    base_store = ResearchStore(root, args.base_run_id)
    base = base_store.load_run()
    variants = [
        ("full", None),
        ("no-planning", "planning"),
        ("no-mutation", "mutation"),
        ("no-crossover", "crossover"),
        ("no-semantic", "semantic"),
        ("no-complexity", "complexity"),
        ("no-redundancy", "redundancy"),
    ]
    manifest = {
        "generated_at": utc_now(),
        "base_run_id": args.base_run_id,
        "control_contract": {
            "same_directions": True,
            "same_candidate_budget": True,
            "same_iteration_budget": True,
            "same_metric_policy": True,
            "same_prompt_version": args.prompt_version,
            "independent_seed_count": args.seeds,
            "test_window_must_remain_hidden": True,
        },
        "variants": [],
    }
    for name, disabled in variants:
        for seed in range(1, args.seeds + 1):
            run_id = f"{args.prefix}-{name}-s{seed}"
            components = _variant_components(disabled)
            record = {
                "run_id": run_id,
                "variant": name,
                "seed": seed,
                "disabled_component": disabled,
                "components": components,
            }
            manifest["variants"].append(record)
            if not args.create_runs:
                continue
            store = ResearchStore(root, run_id)
            directions = base.get("directions", DEFAULT_DIRECTIONS)
            if disabled == "planning":
                directions = directions[:1]
            run = store.initialize(
                iterations=int(base.get("target_iterations", 5)),
                max_iterations=int(base.get("max_iterations", 15)),
                directions=directions,
                components=components,
                budget=base.get("budget", {}),
            )
            run["experiment"] = {
                "type": "ablation",
                "variant": name,
                "seed": seed,
                "base_run_id": args.base_run_id,
                "prompt_version": args.prompt_version,
            }
            atomic_write_json(store.run_path, run)
    output = Path(args.output) if args.output else base_store.path / "ablation_manifest.json"
    atomic_write_json(output, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def command_transfer(args: argparse.Namespace) -> int:
    root = Path(args.run_root).expanduser().resolve()
    source = ResearchStore(root, args.source_run_id)
    source_run = source.load_run()
    pool = read_json(source.pool_path, {"members": []})
    source_candidates = {
        str(item.get("candidate_id")): item for item in source.candidates()
    }
    target = ResearchStore(root, args.target_run_id)
    target.initialize(
        iterations=int(source_run.get("target_iterations", 5)),
        max_iterations=int(source_run.get("max_iterations", 15)),
        directions=source_run.get("directions", DEFAULT_DIRECTIONS),
        components=source_run.get("components", {}),
        budget=source_run.get("budget", {}),
    )
    catalog = FieldCatalog(Path(args.target_catalog))
    registered = []
    for member in pool.get("members", []):
        source_id = str(member.get("candidate_id"))
        original = source_candidates.get(source_id)
        if not original:
            continue
        candidate = {
            key: value
            for key, value in original.items()
            if key not in {"candidate_id", "created_at", "iteration", "validation"}
        }
        candidate["operation"] = "initialization"
        candidate["parents"] = []
        candidate["settings"] = dict(candidate.get("settings", {}))
        candidate["settings"].update(
            {"region": args.region, "universe": args.universe, "delay": args.delay}
        )
        candidate["transfer_contract"] = {
            "source_run_id": args.source_run_id,
            "source_candidate_id": source_id,
            "expression_frozen": True,
            "hypothesis_frozen": True,
            "adapted_components": ["region", "universe", "delay"],
            "zero_shot_label_allowed_only_if_validation_passes": True,
        }
        validation = validate_candidate(
            candidate,
            catalog,
            existing=target.candidates(),
            config=GateConfig(**target.load_run().get("gate_config", {})),
        )
        result = target.register_candidate(candidate, validation)
        registered.append(
            {
                "source_candidate_id": source_id,
                "target_candidate_id": result["candidate_id"],
                "validation_passed": validation["passed"],
                "errors": validation["errors"],
            }
        )
    manifest = {
        "generated_at": utc_now(),
        "type": "frozen_transfer",
        "source_run_id": args.source_run_id,
        "target_run_id": args.target_run_id,
        "target": {"region": args.region, "universe": args.universe, "delay": args.delay},
        "registered": registered,
        "zero_shot": bool(registered) and all(
            item["validation_passed"] for item in registered
        ),
    }
    atomic_write_json(target.path / "transfer_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["zero_shot"] else 2


def command_budget(args: argparse.Namespace) -> int:
    store = ResearchStore(Path(args.run_root).expanduser().resolve(), args.run_id)
    run = store.load_run()
    events = list(iter_jsonl(store.events_path))
    report = {
        "generated_at": utc_now(),
        "run_id": args.run_id,
        "limits": run.get("budget", {}),
        "usage": {
            "candidates": len(store.candidates()),
            "evaluations": len(store.evaluations()),
            "iterations": run.get("iteration", 0),
            "api_requests": sum(
                int(item.get("api_requests", 0))
                for item in events
                if item.get("event") in {"batch_finished", "batch_interrupted"}
            ),
            "elapsed_batch_seconds": sum(
                float(item.get("elapsed_seconds", 0))
                for item in events
                if item.get("event") == "batch_finished"
            ),
            "simulation_errors": sum(
                item.get("stage") == "SIMULATION_ERROR" for item in store.evaluations()
            ),
        },
        "token_usage": "Not available from the BRAIN API; record externally when the agent runtime exposes it.",
    }
    output = Path(args.output) if args.output else store.path / "budget_report.json"
    atomic_write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Govern QuantaAlpha research integrity")
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="audit lineage, reward, PnL, pool, and budget")
    audit.add_argument("--run-id", required=True)
    audit.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    audit.add_argument("--output")
    audit.set_defaults(func=command_audit)

    ablation = subparsers.add_parser("ablation-plan", help="build controlled paper-style ablations")
    ablation.add_argument("--base-run-id", required=True)
    ablation.add_argument("--prefix", required=True)
    ablation.add_argument("--seeds", type=int, default=3)
    ablation.add_argument("--prompt-version", default="v1")
    ablation.add_argument("--create-runs", action="store_true")
    ablation.add_argument("--output")
    ablation.set_defaults(func=command_ablation)

    transfer = subparsers.add_parser("transfer-plan", help="freeze and validate a factor pool for transfer")
    transfer.add_argument("--source-run-id", required=True)
    transfer.add_argument("--target-run-id", required=True)
    transfer.add_argument("--target-catalog", required=True)
    transfer.add_argument("--region", required=True)
    transfer.add_argument("--universe", required=True)
    transfer.add_argument("--delay", type=int, required=True)
    transfer.set_defaults(func=command_transfer)

    budget = subparsers.add_parser("budget", help="report research budget and usage")
    budget.add_argument("--run-id", required=True)
    budget.add_argument("--output")
    budget.set_defaults(func=command_budget)
    return parser


if __name__ == "__main__":
    try:
        arguments = build_parser().parse_args()
        sys.exit(arguments.func(arguments))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
