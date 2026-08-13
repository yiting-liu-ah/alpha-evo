#!/usr/bin/env python3
"""WQ-compatible account synchronization and private empirical memory."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from brain_client import BrainClient, BrainError
from research_core import aligned_correlation, atomic_write_json, read_json, utc_now


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ALPHA_DB_PATH = SKILL_DIR / "alpha_db.json"
LESSONS_PATH = SKILL_DIR / "references" / "validated_lessons.json"


def _expression(alpha: dict[str, Any]) -> str:
    value = alpha.get("regular", alpha.get("expression", ""))
    if isinstance(value, dict):
        return str(value.get("code", ""))
    return str(value or "")


def _metrics(alpha: dict[str, Any]) -> dict[str, Any]:
    value = alpha.get("is", {}) if isinstance(alpha.get("is"), dict) else {}
    checks = [
        {
            "name": item.get("name"),
            "result": item.get("result"),
            "limit": item.get("limit"),
            "value": item.get("value"),
        }
        for item in value.get("checks", [])
        if isinstance(item, dict)
    ]
    checks.sort(key=lambda item: (str(item.get("name")), str(item.get("result"))))
    return {
        "grade": str(alpha.get("grade") or "").upper() or None,
        "sharpe": value.get("sharpe"),
        "fitness": value.get("fitness"),
        "returns": value.get("returns"),
        "turnover": value.get("turnover"),
        "drawdown": value.get("drawdown"),
        "margin": value.get("margin"),
        "long_count": value.get("longCount"),
        "short_count": value.get("shortCount"),
        "checks": checks,
    }


def _family(expression: str) -> str:
    lower = expression.lower()
    families = []
    rules = {
        "fundamental": ["operating_income", "assets", "equity", "cashflow", "sales"],
        "analyst": ["est_eps", "est_fcf", "est_revenue", "est_ebitda", "target"],
        "technical": ["close", "open", "returns", "vwap", "volume", "high", "low"],
        "option": ["option", "implied_vol", "put_call"],
        "news": ["news", "event"],
        "sentiment": ["sentiment", "buzz", "social"],
    }
    for family, tokens in rules.items():
        if any(token in lower for token in tokens):
            families.append(family)
    return "+".join(families) if families else "other"


def _fingerprint(alpha: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": alpha.get("status"),
        "expression": _expression(alpha),
        "settings": alpha.get("settings", {}),
        "metrics": _metrics(alpha),
        "family": _family(_expression(alpha)),
    }


def _load_db() -> dict[str, Any]:
    value = read_json(ALPHA_DB_PATH, None)
    if isinstance(value, dict):
        return value
    return {"schema_version": 2, "last_update": None, "alphas": {}}


def _evidence_band(count: int) -> str:
    if count < 3:
        return "insufficient"
    if count < 10:
        return "3-9"
    if count < 30:
        return "10-29"
    return "30+"


def _value_band(value: float | None, boundaries: tuple[float, ...]) -> str:
    if value is None or not math.isfinite(value):
        return "missing"
    lower = "-inf"
    for boundary in boundaries:
        if value < boundary:
            return f"[{lower},{boundary})"
        lower = str(boundary)
    return f"[{lower},+inf)"


def _median(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return statistics.median(numeric) if numeric else None


def _lesson_signature(observations: list[dict[str, Any]]) -> str:
    material = json.dumps(observations, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _public_evolution_candidate(
    working: dict[str, Any],
    high_pairs: list[dict[str, Any]],
    *,
    min_support: int,
) -> dict[str, Any]:
    """Build k-thresholded mechanism lessons without account-linked artifacts."""
    by_family: dict[str, list[dict[str, Any]]] = {}
    failed_checks: Counter[str] = Counter()
    for value in working.values():
        fingerprint = value.get("fingerprint", {})
        family = str(fingerprint.get("family") or "other")
        metrics = fingerprint.get("metrics", {})
        by_family.setdefault(family, []).append(metrics)
        for check in metrics.get("checks", []):
            if check.get("result") == "FAIL" and check.get("name"):
                failed_checks[str(check["name"])] += 1

    observations: list[dict[str, Any]] = []
    for family, rows in sorted(by_family.items()):
        if len(rows) < min_support:
            continue
        median_fitness = _median([row.get("fitness") for row in rows])
        median_turnover = _median([row.get("turnover") for row in rows])
        median_sharpe = _median([row.get("sharpe") for row in rows])
        if median_turnover is not None and median_turnover > 0.35:
            action = "freeze the mechanism; test longer horizon, decay, or a verified trade condition"
            finding = "persistent high-turnover realization"
        elif median_fitness is not None and median_fitness < 1.0:
            action = "prefer mechanism-level mutation over parameter-only tuning"
            finding = "weak median fitness"
        elif median_fitness is not None and median_fitness >= 1.1:
            action = "retain as a parent only after redundancy and regime checks"
            finding = "promising median fitness"
        else:
            continue
        observations.append(
            {
                "kind": "family_metric_profile",
                "family": family,
                "support": _evidence_band(len(rows)),
                "finding": finding,
                "median_sharpe_band": _value_band(median_sharpe, (0.0, 1.25, 1.5, 2.0)),
                "median_fitness_band": _value_band(median_fitness, (0.5, 1.0, 1.1, 1.5)),
                "median_turnover_band": _value_band(median_turnover, (0.01, 0.20, 0.35, 0.70)),
                "action": action,
            }
        )

    for check_name, count in sorted(failed_checks.items()):
        if count < min_support:
            continue
        observations.append(
            {
                "kind": "repeated_is_failure",
                "check": check_name,
                "support": _evidence_band(count),
                "action": "use fault-localized mutation and preserve already validated segments",
            }
        )

    pair_counts: Counter[tuple[str, str]] = Counter()
    for pair in high_pairs:
        left = working.get(str(pair.get("left")), {}).get("fingerprint", {})
        right = working.get(str(pair.get("right")), {}).get("fingerprint", {})
        families = tuple(sorted((str(left.get("family", "other")), str(right.get("family", "other")))))
        pair_counts[families] += 1
    for families, count in sorted(pair_counts.items()):
        if count < min_support:
            continue
        observations.append(
            {
                "kind": "high_correlation_cluster",
                "families": list(families),
                "support": _evidence_band(count),
                "threshold": "abs(date-aligned daily-PnL correlation) >= 0.70",
                "action": "change the data source or economic mechanism; do not tune only windows or weights",
            }
        )

    return {
        "schema_version": 2,
        "generated_at": utc_now(),
        "source": "account_sync_sanitized",
        "lesson_id": _lesson_signature(observations),
        "evidence_grade": "repeatable" if observations else "insufficient",
        "minimum_support": min_support,
        "observations": observations,
        "privacy": (
            "Thresholded aggregate only. No alpha IDs, expressions, exact account counts, "
            "PnL series, timestamps, or account-linked statuses are included."
        ),
    }


def sync_account(
    *,
    apply: bool,
    max_pnl_fetch: int = 500,
    min_public_support: int = 3,
) -> dict[str, Any]:
    if min_public_support < 3:
        raise ValueError("min_public_support must be at least 3")
    client = BrainClient.from_environment(SKILL_DIR)
    client.authenticate()
    try:
        alphas = client.list_alphas()
        old_db = _load_db()
        old_alphas = old_db.get("alphas", {})
        event_mode = "baseline" if not old_alphas else "incremental"
        working: dict[str, Any] = {}
        new_ids = []
        changed_ids = []
        status_transitions: Counter[str] = Counter()
        pnl_fetches = 0
        pnl_fetch_errors = 0
        detail_fetches = 0

        for alpha in alphas:
            alpha_id = str(alpha.get("id", ""))
            if not alpha_id:
                continue
            has_detail = (
                isinstance(alpha.get("is"), dict)
                and ("regular" in alpha or "expression" in alpha)
                and isinstance(alpha.get("settings"), dict)
            )
            detail = alpha if has_detail else client.get_alpha(alpha_id)
            detail_fetches += 0 if has_detail else 1
            fingerprint = _fingerprint(detail)
            old = old_alphas.get(alpha_id, {})
            if not old:
                new_ids.append(alpha_id)
            elif old.get("fingerprint") != fingerprint:
                changed_ids.append(alpha_id)
                old_status = old.get("fingerprint", {}).get("status") or "UNKNOWN"
                new_status = fingerprint.get("status") or "UNKNOWN"
                if old_status != new_status:
                    status_transitions[f"{old_status}->{new_status}"] += 1
            pnl = old.get("pnl", [])
            needs_pnl = (
                alpha_id in new_ids
                or alpha_id in changed_ids
                or (fingerprint.get("status") == "ACTIVE" and not pnl)
            )
            if needs_pnl and pnl_fetches < max_pnl_fetch:
                pnl_fetches += 1
                try:
                    pnl = client.fetch_pnl(alpha_id)
                except BrainError:
                    # Keep the last valid private cache. A transient HTTP 200
                    # empty recordset must not erase usable PnL history.
                    pnl_fetch_errors += 1
                time.sleep(0.75)
            working[alpha_id] = {
                "fingerprint": fingerprint,
                "pnl": pnl,
                "updated_at": utc_now(),
            }

        active_status_ids = [
            alpha_id
            for alpha_id, value in working.items()
            if value.get("fingerprint", {}).get("status") == "ACTIVE"
        ]
        active_ids = [
            alpha_id
            for alpha_id in active_status_ids
            if working[alpha_id].get("pnl")
        ]
        high_pairs = []
        correlation_comparisons = 0
        for index, left_id in enumerate(active_ids):
            for right_id in active_ids[index + 1 :]:
                correlation = aligned_correlation(
                    working[left_id]["pnl"], working[right_id]["pnl"]
                )
                value = correlation.get("correlation")
                if value is not None:
                    correlation_comparisons += 1
                if value is not None and abs(float(value)) >= 0.70:
                    high_pairs.append(
                        {
                            "left": left_id,
                            "right": right_id,
                            "correlation": value,
                            "overlap": correlation.get("overlap"),
                        }
                    )

        public_candidate = _public_evolution_candidate(
            working, high_pairs, min_support=min_public_support
        )
        removed_ids = sorted(set(old_alphas) - set(working))
        summary = {
            "generated_at": utc_now(),
            "mode": "apply" if apply else "preview",
            "event_mode": event_mode,
            "total": len(working),
            "active": len(active_status_ids),
            "active_with_pnl": len(active_ids),
            "new": len(new_ids),
            "changed": len(changed_ids),
            "removed": len(removed_ids),
            "pnl_fetches": pnl_fetches,
            "pnl_fetch_errors": pnl_fetch_errors,
            "detail_fetches": detail_fetches,
            "api_requests": client.request_count,
            "correlation_comparisons": correlation_comparisons,
            "family_counts": dict(
                Counter(
                    value.get("fingerprint", {}).get("family", "other")
                    for value in working.values()
                )
            ),
            "high_correlation_pair_count": len(high_pairs),
            "new_alpha_ids": new_ids,
            "changed_alpha_ids": changed_ids,
            "removed_alpha_ids": removed_ids,
            "status_transitions": dict(status_transitions),
            "high_correlation_pairs": high_pairs[:50],
            "public_evolution_candidate": public_candidate,
            "public_lesson_promoted": False,
        }
        if apply:
            atomic_write_json(
                ALPHA_DB_PATH,
                {
                    "schema_version": 2,
                    "last_update": utc_now(),
                    "alphas": working,
                },
            )
            lessons = read_json(LESSONS_PATH, {"schema_version": 2, "lessons": []})
            lessons["schema_version"] = 2
            known_lesson_ids = {
                str(item.get("lesson_id"))
                for item in lessons.get("lessons", [])
                if isinstance(item, dict)
            }
            should_promote = (
                public_candidate["evidence_grade"] == "repeatable"
                and public_candidate["lesson_id"] not in known_lesson_ids
                and (event_mode == "baseline" or bool(new_ids or changed_ids or removed_ids))
            )
            if should_promote:
                lessons.setdefault("lessons", []).append(public_candidate)
                atomic_write_json(LESSONS_PATH, lessons)
                summary["public_lesson_promoted"] = True
        return summary
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize BRAIN account into private alpha_db.json")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-pnl-fetch", type=int, default=500)
    parser.add_argument("--min-public-support", type=int, default=3)
    args = parser.parse_args()
    summary = sync_account(
        apply=args.apply,
        max_pnl_fetch=args.max_pnl_fetch,
        min_public_support=args.min_public_support,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.apply:
        print("Preview only; alpha_db.json was not modified. Use --apply after review.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
