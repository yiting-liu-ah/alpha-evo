#!/usr/bin/env python3
"""Offline checks for parsing, gates, reward, correlation, and research storage."""
from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import account_sync
from brain_client import BrainClient, BrainError
from feedback_generation import materialize_crossovers, materialize_mutations
from evolve_skill import (
    _assign_expression_budgets,
    _crossover_briefs,
    _evolution_eligible,
    _mechanism_profile,
    _mutation_briefs,
    _mutation_parent_order,
    _parent_attempt_history,
    _require_completed_mutation_phase,
    build_parser,
)
from submit_batch import (
    _active_correlation_audit,
    _correlation_submission_gate,
    batch_submission_summary,
)
from research_core import (
    FieldCatalog,
    GateConfig,
    ResearchStore,
    active_expression_similarity,
    aligned_correlation,
    core_signal_fields,
    diagnose_evaluation,
    metric_snapshot,
    submission_eligibility,
    trajectory_reward,
    validate_candidate,
    validate_feedback_contract,
)


SKILL_DIR = Path(__file__).resolve().parent.parent
FIELD_PATH = SKILL_DIR / "references" / "wq_usa_top3000_delay1_data_fields.json"


def sample_candidate() -> dict:
    return {
        "direction_id": "profitability-quality",
        "hypothesis": {
            "mechanism": "Improving operating profitability is incorporated with a delay within subindustries.",
            "expected_horizon": 126,
            "expected_sign": "positive",
            "observable_proxies": [
                {"field": "operating_income", "role": "profitability numerator", "required": True},
                {"field": "equity", "role": "capital denominator", "required": True},
                {"field": "subindustry", "role": "peer group", "required": True},
            ],
            "failure_modes": ["negative equity", "stale filings", "sector concentration"],
            "claims": [
                {"name": "fundamental quality", "required_categories": ["fundamental"]}
            ],
        },
        "semantic_description": "Rank the 126-day history of operating return on equity within subindustry.",
        "expression": "group_rank(ts_rank(operating_income / equity, 126), subindustry)",
        "settings": {"decay": 0, "neutralization": "SUBINDUSTRY"},
        "operation": "initialization",
        "parents": [],
    }


def main() -> int:
    catalog = FieldCatalog(FIELD_PATH)
    candidate = sample_candidate()
    validation = validate_candidate(candidate, catalog)
    assert validation["passed"], validation

    tautology = sample_candidate()
    tautology["hypothesis"]["observable_proxies"] = [
        {"field": "returns", "role": "return series", "required": True}
    ]
    tautology["hypothesis"]["claims"] = []
    tautology["expression"] = "ts_corr(returns, returns, 20)"
    rejected = validate_candidate(tautology, catalog)
    assert not rejected["passed"]
    assert any("tautological" in error for error in rejected["errors"]), rejected

    semantic_ablation = sample_candidate()
    semantic_ablation["hypothesis"]["observable_proxies"] = [
        {"field": "returns", "role": "deliberate mismatch", "required": True}
    ]
    assert not validate_candidate(semantic_ablation, catalog)["passed"]
    assert validate_candidate(
        semantic_ablation,
        catalog,
        config=GateConfig(enable_semantic_gate=False),
    )["passed"]

    complex_ablation = sample_candidate()
    complex_ablation["expression"] = (
        "rank(" * 50 + complex_ablation["expression"] + ")" * 50
    )
    assert not validate_candidate(complex_ablation, catalog)["passed"]
    assert validate_candidate(
        complex_ablation,
        catalog,
        config=GateConfig(enable_complexity_gate=False),
    )["passed"]

    duplicate = sample_candidate()
    assert not validate_candidate(duplicate, catalog, existing=[sample_candidate()])["passed"]
    assert validate_candidate(
        duplicate,
        catalog,
        existing=[sample_candidate()],
        config=GateConfig(enable_redundancy_gate=False),
    )["passed"]

    active_expression = "group_rank(ts_rank(est_eps / close, 126), subindustry)"
    thin_wrapper = (
        "group_rank(ts_rank(est_eps / close, 126) "
        "+ ts_rank(-ts_sum(returns, 5), 20), subindustry)"
    )
    active_match = active_expression_similarity(thin_wrapper, active_expression, catalog)
    assert core_signal_fields(active_expression, catalog) == {"est_eps", "close"}
    assert active_match["active_core_field_containment"] == 1.0
    assert active_match["structural_similarity"] >= 0.50
    independent = active_expression_similarity(
        sample_candidate()["expression"], active_expression, catalog
    )
    assert independent["active_core_field_containment"] == 0.0

    average_pending = metric_snapshot(
        {
            "status": "UNSUBMITTED",
            "grade": "AVERAGE",
            "is": {
                "sharpe": 1.5,
                "fitness": 1.1,
                "checks": [
                    {"name": "LOW_SHARPE", "result": "PASS"},
                    {"name": "SELF_CORRELATION", "result": "PENDING"},
                ],
            },
        }
    )
    assert average_pending["grade"] == "AVERAGE"
    pending_eligibility = submission_eligibility(average_pending)
    assert pending_eligibility["eligible"], pending_eligibility
    assert pending_eligibility["pending_checks"] == ["SELF_CORRELATION"]
    good_with_fail = submission_eligibility(
        {
            "grade": "GOOD",
            "checks": [{"name": "SELF_CORRELATION", "result": "FAIL"}],
        }
    )
    assert not good_with_fail["eligible"] and good_with_fail["grade_eligible"]
    needs_improvement = submission_eligibility(
        {"grade": "NEEDS_IMPROVEMENT", "checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}
    )
    assert not needs_improvement["eligible"]
    submission_summary = batch_submission_summary(
        [
            {
                "candidate_id": "eligible",
                "alpha_id": "alpha-eligible",
                "stage": "ACTIVE",
                "submit_attempted": True,
                "submission_eligibility": pending_eligibility,
                "submission_blockers": [],
            },
            {
                "candidate_id": "failed",
                "alpha_id": "alpha-failed",
                "stage": "SIMULATED_NOT_ELIGIBLE",
                "submit_attempted": False,
                "submission_eligibility": good_with_fail,
                "submission_blockers": good_with_fail["blockers"],
            },
            {
                "candidate_id": "correlated",
                "alpha_id": "alpha-correlated",
                "stage": "SIMULATED_ELIGIBLE_NOT_SUBMITTED",
                "submit_attempted": False,
                "submission_eligibility": pending_eligibility,
                "auto_submit_qualified": False,
                "submission_blockers": ["ACTIVE_PNL_CORRELATION"],
            },
        ]
    )
    assert submission_summary["auto_submit_candidate_count"] == 1
    assert submission_summary["active_success_count"] == 1
    assert submission_summary["grade_eligible_but_failed_is_test_count"] == 1

    class FakeResponse:
        status_code = 200
        text = "payload"

        @staticmethod
        def json() -> dict:
            return {
                "schema": {
                    "properties": [
                        {"name": "date"},
                        {"name": "pnl"},
                    ]
                },
                "records": [
                    [["2025-01-03", 3.0]],
                    [["2025-01-01", 0.0]],
                    [["2025-01-02", 1.0]],
                ],
            }

    client = BrainClient("user", "password")
    client.get = lambda *_args, **_kwargs: FakeResponse()  # type: ignore[method-assign]
    parsed = client.fetch_pnl("synthetic")
    client.close()
    assert [item["date"] for item in parsed] == ["2025-01-01", "2025-01-02", "2025-01-03"]

    class EmptyResponse:
        status_code = 200
        text = ""

    empty_client = BrainClient("user", "password")
    empty_client.get = lambda *_args, **_kwargs: EmptyResponse()  # type: ignore[method-assign]
    try:
        empty_client.fetch_pnl("synthetic", empty_response_retries=0)
    except BrainError as exc:
        assert "empty or unparseable" in str(exc)
    else:
        raise AssertionError("HTTP 200 empty PnL must not be accepted as valid data")
    finally:
        empty_client.close()

    left = [
        {"date": "2025-01-01", "pnl": 0},
        {"date": "2025-01-02", "pnl": 1},
        {"date": "2025-01-03", "pnl": 3},
        {"date": "2025-01-06", "pnl": 2},
    ]
    right = [
        {"date": "2025-01-01", "pnl": 0},
        {"date": "2025-01-02", "pnl": 2},
        {"date": "2025-01-03", "pnl": 6},
        {"date": "2025-01-06", "pnl": 4},
    ]
    correlation = aligned_correlation(left, right, min_overlap=3)
    assert abs(correlation["correlation"] - 1.0) < 1e-12, correlation
    shifted = [
        {"date": "2025-01-02", "pnl": 0},
        {"date": "2025-01-03", "pnl": 2},
        {"date": "2025-01-06", "pnl": 1},
        {"date": "2025-01-07", "pnl": 5},
    ]
    date_aligned = aligned_correlation(left, shifted, min_overlap=2)
    assert date_aligned["overlap"] == 2, date_aligned

    long_left = [
        {"date": str(date(2025, 1, 1) + timedelta(days=index)), "pnl": float(index**2)}
        for index in range(60)
    ]
    long_right = [
        {"date": str(date(2025, 1, 1) + timedelta(days=index)), "pnl": float(2 * index**2)}
        for index in range(60)
    ]
    complete_audit = _active_correlation_audit(
        long_left,
        {"active": [{"alpha_id": "old", "pnl": long_right, "pnl_source": "api"}]},
    )
    correlation_gate = _correlation_submission_gate(complete_audit, 0.70)
    assert not correlation_gate["passed"]
    assert correlation_gate["blockers"] == ["ACTIVE_PNL_CORRELATION"]
    incomplete_audit = _active_correlation_audit(
        long_left,
        {"active": [{"alpha_id": "missing", "pnl": [], "pnl_source": "unavailable"}]},
    )
    incomplete_gate = _correlation_submission_gate(incomplete_audit, 0.70)
    assert "ACTIVE_PNL_COVERAGE_INCOMPLETE" in incomplete_gate["blockers"]

    reward = trajectory_reward(
        {
            "sharpe": 1.8,
            "fitness": 1.4,
            "returns": 0.09,
            "turnover": 0.12,
            "drawdown": 0.08,
            "checks": [],
        },
        validation["complexity"],
        max_abs_correlation=0.25,
    )
    assert reward["metric_gate"]["passed"], reward

    structural_reward = trajectory_reward(
        {
            "sharpe": 1.4,
            "fitness": 0.9,
            "returns": 0.05,
            "turnover": 0.10,
            "drawdown": 0.08,
            "checks": [{"name": "LOW_FITNESS", "result": "FAIL", "value": 0.9, "limit": 1.0}],
        },
        validation["complexity"],
        max_abs_correlation=None,
        max_structural_similarity=0.85,
    )
    assert abs(structural_reward["novelty"] - 0.15) < 1e-12, structural_reward
    assert structural_reward["novelty_source"] == "structural_similarity"

    left_candidate = sample_candidate()
    left_candidate["candidate_id"] = "left"
    left_candidate["validation"] = {"passed": True}
    right_candidate = sample_candidate()
    right_candidate["candidate_id"] = "right"
    right_candidate["direction_id"] = "price-volume-microstructure"
    right_candidate["hypothesis"]["observable_proxies"] = [
        {"field": "returns", "role": "price response", "required": True},
        {"field": "volume", "role": "participation", "required": True},
    ]
    right_candidate["hypothesis"]["claims"] = [
        {"name": "price volume", "required_categories": ["pv"]}
    ]
    right_candidate["expression"] = "rank(ts_mean(returns, 5) * rank(volume))"
    right_candidate["candidate_id"] = "right"
    right_candidate["validation"] = {"passed": True}
    near_pass_evaluations = [
        {
            "candidate_id": "left",
            "stage": "ACTIVE",
            "metrics": {
                "sharpe": 1.5,
                "fitness": 1.1,
                "grade": "AVERAGE",
                "checks": [{"name": "SELF_CORRELATION", "result": "PENDING"}],
            },
            "reward": {"reward": 0.4, "metric_gate": {"passed": True, "failures": []}},
        },
        {
            "candidate_id": "right",
            "stage": "SIMULATED_NOT_SUBMITTED",
            "metrics": {
                "sharpe": 1.4,
                "fitness": 0.8,
                "checks": [{"name": "LOW_FITNESS", "result": "FAIL", "value": 0.8, "limit": 1.0}],
            },
            "reward": {"reward": 0.3, "metric_gate": {"passed": False, "failures": ["LOW_FITNESS"]}},
        },
    ]
    crossover = _crossover_briefs(
        near_pass_evaluations,
        {"left": left_candidate, "right": right_candidate},
        catalog,
        1,
    )
    assert crossover, "high-reward complementary trajectories must enable crossover"
    assert "different dominant information sources" in crossover[0]["instruction"]
    assert "not to maximize orthogonality" in crossover[0]["inheritance_contract"]
    budgeted = _assign_expression_budgets(crossover, simulation_budget=3)
    assert budgeted[0]["expression_budget"] == 3
    non_active_left = {
        **near_pass_evaluations[0],
        "stage": "SIMULATED_NOT_SUBMITTED",
        "metrics": {
            **near_pass_evaluations[0]["metrics"],
            "grade": "INFERIOR",
            "checks": [{"name": "LOW_FITNESS", "result": "FAIL", "value": 0.9, "limit": 1.0}],
        },
        "reward": {"reward": 0.4, "metric_gate": {"passed": False, "failures": ["LOW_FITNESS"]}},
    }
    crossover_without_active = _crossover_briefs(
        [non_active_left, near_pass_evaluations[1]],
        {"left": left_candidate, "right": right_candidate},
        catalog,
        1,
    )
    assert crossover_without_active, "positive near-gate parents must remain eligible for crossover"
    mutation = _mutation_briefs(
        [near_pass_evaluations[1]], {"right": right_candidate}, catalog, 1
    )[0]
    assert mutation["fault_localization"]["revise"] == ["one_identified_fitness_cause"]
    assert mutation["fault_localization"]["modification_depth"] == "targeted"
    assert "hypothesis" in mutation["frozen_payload"]
    assert "one explicit change" in mutation["instruction"]
    assert mutation["repair_card"]["failure_reasons"] == ["LOW_FITNESS"]
    assert mutation["repair_card"]["lineage_history"][0]["candidate_id"] == "right"
    pending_high_quality = {
        **near_pass_evaluations[1],
        "stage": "SUBMISSION_REJECTED_OR_UNRESOLVED",
        "metrics": {
            "sharpe": 2.0,
            "fitness": 1.5,
            "grade": "GOOD",
            "checks": [{"name": "SELF_CORRELATION", "result": "PENDING"}],
        },
        "reward": {"reward": 0.7, "metric_gate": {"passed": True, "failures": []}},
        "governance_warnings": ["ACTIVE_EXPRESSION_REDUNDANCY"],
    }
    assert _evolution_eligible(pending_high_quality)

    # Future cycles materialize from the repair card, not an iteration-specific table.
    feedback_parent = sample_candidate()
    feedback_parent["candidate_id"] = "feedback-parent"
    feedback_task = {
        "generation_contract": {"feedback_driven_generation": True},
        "iteration": 23,
        "mutation": [
            {
                "parent": "feedback-parent",
                "expression_budget": 1,
                "fault_localization": {"fault": "realization"},
                "repair_card": {
                    "version": 2,
                    "parent_id": "feedback-parent",
                    "fault": "realization",
                    "failure_reasons": ["LOW_FITNESS"],
                    "must_keep_fields": ["operating_income", "equity"],
                    "must_change": ["horizon", "decay"],
                    "forbidden": ["change the economic sign"],
                    "maximum_parent_structural_similarity": 0.90,
                    "maximum_parent_core_retention": 1.0,
                    "failed_action_ids": [],
                },
            }
        ],
    }
    feedback_children = materialize_mutations(
        feedback_task,
        {"feedback-parent": feedback_parent},
        [feedback_parent],
        catalog,
    )
    assert len(feedback_children) == 1
    assert feedback_children[0]["generation_trace"]["mode"] == "feedback_driven"
    assert feedback_children[0]["generation_trace"]["action_id"]
    failed_child = {
        **feedback_children[0],
        "candidate_id": "failed-child",
    }
    failed_attempts = _parent_attempt_history(
        "feedback-parent",
        {"feedback-parent": feedback_parent, "failed-child": failed_child},
        {
            "failed-child": {
                "parent_feedback": {
                    "comparisons": [
                        {"parent_id": "feedback-parent", "outcome": "WORSE"}
                    ]
                }
            }
        },
    )
    assert failed_attempts[0]["action_id"] == feedback_children[0]["generation_trace"]["action_id"]
    assert failed_attempts[0]["outcome"] == "WORSE"
    feedback_validation = validate_candidate(
        feedback_children[0], catalog, existing=[feedback_parent]
    )
    assert feedback_validation["passed"], feedback_validation
    assert feedback_validation["repair_contract"]["passed"]

    ignored_feedback = {
        **feedback_children[0],
        "expression": feedback_parent["expression"],
    }
    ignored_contract = validate_feedback_contract(
        ignored_feedback, catalog, [feedback_parent]
    )
    assert not ignored_contract["passed"]

    crossover_task = {
        "generation_contract": {"feedback_driven_generation": True},
        "iteration": 24,
        "crossover": [
            {
                "parents": ["left", "right"],
                "expression_budget": 3,
                "parent_mechanism_profiles": [
                    _mechanism_profile(left_candidate, catalog),
                    _mechanism_profile(right_candidate, catalog),
                ],
                "generation_card": {
                    "version": 1,
                    "active_parent_ids": ["left"],
                    "maximum_active_parent_core_retention": 0.79,
                },
            }
        ],
    }
    feedback_crossovers = materialize_crossovers(
        crossover_task,
        {"left": left_candidate, "right": right_candidate},
        [left_candidate, right_candidate],
        catalog,
    )
    assert len(feedback_crossovers) == 3
    assert all(
        item["generation_trace"]["mode"] == "feedback_driven"
        for item in feedback_crossovers
    )

    # ACTIVE trajectories are success demonstrations, never ordinary Mutation parents.
    selected_mutation = _mutation_parent_order(
        near_pass_evaluations,
        {"left": left_candidate, "right": right_candidate},
        catalog,
        2,
    )
    assert [item["candidate_id"] for item in selected_mutation] == ["right"]

    # Mechanism labels remain descriptive; they no longer allocate parent slots.
    left_profile = _mechanism_profile(left_candidate, catalog)
    right_profile = _mechanism_profile(right_candidate, catalog)
    assert left_profile["cluster"] == "fundamental-level"
    assert right_profile["cluster"] == "price-volume"
    redundant_evaluation = {
        **near_pass_evaluations[1],
        "governance_warnings": ["ACTIVE_EXPRESSION_REDUNDANCY"],
    }
    redundancy_mutation = _mutation_briefs(
        [redundant_evaluation], {"right": right_candidate}, catalog, 1
    )[0]
    assert redundancy_mutation["fault_localization"]["fault"] == "redundancy"
    assert redundancy_mutation["fault_localization"]["modification_depth"] == "targeted"
    assert "hypothesis" in redundancy_mutation["frozen_payload"]
    assert "one explicit change" in redundancy_mutation["instruction"]

    deepest_fault = diagnose_evaluation(
        {
            "reward": {
                "metric_gate": {
                    "failures": ["LOW_FITNESS", "HIGH_TURNOVER", "LOW_SHARPE"]
                }
            },
            "metrics": {"checks": []},
        }
    )
    assert deepest_fault["fault"] == "high_turnover", deepest_fault
    assert deepest_fault["modification_depth"] == "realization", deepest_fault

    next_args = build_parser().parse_args(["next", "--run-id", "regression"])
    assert next_args.phase == "mutation"
    assert next_args.mutations == 14
    assert next_args.crossovers == 2
    assert next_args.mutation_simulations == 14
    assert next_args.crossover_simulations == 6
    command_action = next(action for action in build_parser()._actions if action.dest == "command")
    next_parser = command_action.choices["next"]
    phase_action = next(action for action in next_parser._actions if action.dest == "phase")
    assert set(phase_action.choices) == {"mutation", "crossover"}

    single_private = {
        "only-one": {
            "fingerprint": {
                "family": "technical",
                "metrics": {"fitness": 0.2, "turnover": 0.8, "checks": []},
            }
        }
    }
    insufficient = account_sync._public_evolution_candidate(
        single_private, [], min_support=3
    )
    assert insufficient["evidence_grade"] == "insufficient"
    assert insufficient["observations"] == []

    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        store = ResearchStore(temporary_path, "selftest")
        store.initialize(iterations=5, max_iterations=15)
        registered = store.register_candidate(candidate, validation)
        store.record_evaluation(
            {
                "candidate_id": registered["candidate_id"],
                "metrics": {"sharpe": 1.8},
                "pnl": left,
                "reward": reward,
            }
        )
        assert len(store.candidates()) == 1
        assert len(store.evaluations()) == 1

        mutation_packet = {
            "phase": "mutation",
            "mutation": [{"expression_budget": 2}],
        }
        mutation_packet_path = store.path / "iteration_01_tasks.json"
        mutation_packet_path.write_text(json.dumps(mutation_packet), encoding="utf-8")
        mutation_parent = sample_candidate()
        mutation_parent["expression"] = (
            "group_rank(ts_rank(operating_income / equity, 125), subindustry)"
        )
        mutation_parent["hypothesis"]["expected_horizon"] = 125
        mutation_parent["operation"] = "mutation"
        mutation_parent["parents"] = [registered["candidate_id"]]
        mutation_parent["iteration"] = 1
        first_child = store.register_candidate(
            mutation_parent, validate_candidate(mutation_parent, catalog)
        )
        store.record_evaluation(
            {"candidate_id": first_child["candidate_id"], "metrics": {"sharpe": 1.2}}
        )
        run_state = store.load_run()
        run_state["iteration"] = 1
        try:
            _require_completed_mutation_phase(
                store,
                run_state,
                {item["candidate_id"]: item for item in store.candidates()},
                store.evaluations(),
            )
        except ValueError as exc:
            assert "expected=2" in str(exc) and "evaluated=1" in str(exc), exc
        else:
            raise AssertionError("incomplete Mutation phase must block Crossover")

        class FakeBrainClient:
            request_count = 5

            @classmethod
            def from_environment(cls, _skill_dir: Path) -> "FakeBrainClient":
                return cls()

            def authenticate(self) -> None:
                return None

            def list_alphas(self) -> list[dict]:
                return [{"id": f"private-alpha-{index}"} for index in range(3)]

            def get_alpha(self, alpha_id: str) -> dict:
                return {
                    "id": alpha_id,
                    "status": "ACTIVE",
                    "regular": {"code": "rank(returns)"},
                    "settings": {"region": "USA"},
                    "is": {
                        "sharpe": 1.5,
                        "fitness": 0.8,
                        "turnover": 0.1,
                        "checks": [{"name": "LOW_FITNESS", "result": "FAIL"}],
                    },
                }

            def fetch_pnl(self, _alpha_id: str) -> list[dict]:
                return [
                    {
                        "date": str(date(2025, 1, 1) + timedelta(days=index)),
                        "pnl": float(index),
                    }
                    for index in range(60)
                ]

            def close(self) -> None:
                return None

        original_client = account_sync.BrainClient
        original_db_path = account_sync.ALPHA_DB_PATH
        original_lessons_path = account_sync.LESSONS_PATH
        account_sync.BrainClient = FakeBrainClient  # type: ignore[assignment]
        account_sync.ALPHA_DB_PATH = temporary_path / "alpha_db.json"
        account_sync.LESSONS_PATH = temporary_path / "validated_lessons.json"
        account_sync.atomic_write_json(
            account_sync.LESSONS_PATH, {"schema_version": 1, "lessons": []}
        )
        try:
            preview = account_sync.sync_account(apply=False)
            assert preview["event_mode"] == "baseline"
            assert preview["new"] == 3
            assert preview["public_evolution_candidate"]["evidence_grade"] == "repeatable"
            assert not account_sync.ALPHA_DB_PATH.exists()
            applied = account_sync.sync_account(apply=True)
            assert applied["active"] == 3
            assert applied["public_lesson_promoted"]
            private_db = json.loads(account_sync.ALPHA_DB_PATH.read_text())
            assert "private-alpha-0" in private_db["alphas"]
            public_lessons = json.loads(account_sync.LESSONS_PATH.read_text())
            serialized = json.dumps(public_lessons)
            assert "private-alpha" not in serialized and "rank(returns)" not in serialized
            assert public_lessons["schema_version"] == 2
            assert public_lessons["lessons"][0]["minimum_support"] == 3
            incremental = account_sync.sync_account(apply=True)
            assert incremental["event_mode"] == "incremental"
            assert incremental["new"] == 0 and incremental["changed"] == 0
            assert not incremental["public_lesson_promoted"]
        finally:
            account_sync.BrainClient = original_client
            account_sync.ALPHA_DB_PATH = original_db_path
            account_sync.LESSONS_PATH = original_lessons_path

    print(json.dumps({"status": "ok", "reward": reward["reward"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
