"""Deterministic research controls for QuantaAlpha on WorldQuant BRAIN."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


TOKEN_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*|(?:\d+\.\d+|\d+)|==|!=|<=|>=|&&|\|\||[-+*/%^<>()=,?:]"
)

# This is a validation allowlist, not an exhaustive platform operator catalog.
# Add newly verified operators deliberately instead of silently accepting typos.
KNOWN_OPERATORS = {
    "abs",
    "add",
    "and",
    "arc_cos",
    "arc_sin",
    "arc_tan",
    "bucket",
    "densify",
    "divide",
    "equal",
    "exp",
    "group_backfill",
    "group_mean",
    "group_neutralize",
    "group_rank",
    "group_scale",
    "group_zscore",
    "if_else",
    "inverse",
    "less",
    "log",
    "max",
    "min",
    "multiply",
    "negate",
    "normalize",
    "not",
    "or",
    "power",
    "rank",
    "reverse",
    "round",
    "scale",
    "signed_power",
    "sign",
    "subtract",
    "trade_when",
    "ts_arg_max",
    "ts_arg_min",
    "ts_av_diff",
    "ts_backfill",
    "ts_co_kurtosis",
    "ts_corr",
    "ts_count_nans",
    "ts_covariance",
    "ts_decay_exp_window",
    "ts_decay_linear",
    "ts_delay",
    "ts_delta",
    "ts_ir",
    "ts_kurtosis",
    "ts_max",
    "ts_mean",
    "ts_median",
    "ts_min",
    "ts_moment",
    "ts_product",
    "ts_quantile",
    "ts_rank",
    "ts_regression",
    "ts_scale",
    "ts_skewness",
    "ts_std_dev",
    "ts_step",
    "ts_sum",
    "ts_zscore",
    "vec_avg",
    "vec_sum",
    "winsorize",
    "zscore",
}

RESERVED_IDENTIFIERS = {
    "true",
    "false",
    "nan",
    "null",
    "inf",
    "filter",
    "dense",
    "std",
    "rate",
    "driver",
    "lag",
    "rettype",
}

SUBMITTABLE_GRADES = frozenset({"AVERAGE", "GOOD", "EXCELLENT", "SPECTACULAR"})


DEFAULT_DIRECTIONS = [
    {
        "id": "profitability-quality",
        "mechanism": "Persistent profitability and balance-sheet quality are underpriced cross-sectionally.",
        "categories": ["fundamental"],
        "horizons": [63, 126, 252],
    },
    {
        "id": "fundamental-change",
        "mechanism": "Changes in operating performance contain incremental information beyond levels.",
        "categories": ["fundamental"],
        "horizons": [21, 63, 126],
    },
    {
        "id": "cashflow-accrual",
        "mechanism": "Cash conversion and accrual quality separate sustainable from fragile earnings.",
        "categories": ["fundamental"],
        "horizons": [126, 252],
    },
    {
        "id": "valuation",
        "mechanism": "Fundamental or forecast yield predicts relative repricing after neutralization.",
        "categories": ["fundamental", "analyst"],
        "horizons": [126, 252],
    },
    {
        "id": "analyst-revision",
        "mechanism": "Slow diffusion of estimate revisions creates medium-horizon continuation.",
        "categories": ["analyst"],
        "horizons": [21, 63, 126],
    },
    {
        "id": "investment-efficiency",
        "mechanism": "Capital allocation and asset efficiency predict future operating outcomes.",
        "categories": ["fundamental"],
        "horizons": [126, 252],
    },
    {
        "id": "price-volume-microstructure",
        "mechanism": "Short-horizon price pressure reverses or continues conditional on participation.",
        "categories": ["pv"],
        "horizons": [2, 5, 10, 20],
    },
    {
        "id": "volatility-option",
        "mechanism": "Volatility state and option-implied information alter return distributions.",
        "categories": ["pv", "option"],
        "horizons": [5, 20, 60],
    },
    {
        "id": "news-sentiment",
        "mechanism": "Attention and sentiment shocks diffuse with state-dependent speed.",
        "categories": ["news", "socialmedia"],
        "horizons": [2, 5, 20],
    },
    {
        "id": "regime-conditioned-composite",
        "mechanism": "A slow structural signal becomes more robust when gated by a distinct fast regime proxy.",
        "categories": ["fundamental", "analyst", "pv", "option", "news"],
        "horizons": [5, 20, 126],
    },
]


@dataclass(frozen=True)
class GateConfig:
    max_chars: int = 250
    max_features: int = 6
    max_depth: int = 12
    max_parameter_ratio: float = 0.50
    max_structural_similarity: float = 0.90
    max_pnl_correlation: float = 0.70
    min_coverage: float = 0.20
    enable_semantic_gate: bool = True
    enable_complexity_gate: bool = True
    enable_redundancy_gate: bool = True


@dataclass(frozen=True)
class MetricPolicy:
    min_sharpe: float = 1.25
    min_fitness: float = 1.00
    min_turnover: float = 0.01
    max_turnover: float = 0.70
    preferred_max_turnover: float = 0.20
    max_drawdown: float = 0.20


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(value, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


class FieldCatalog:
    def __init__(self, path: Path) -> None:
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise ValueError("field catalog must be a JSON array")
        self.by_id = {str(value["id"]).lower(): value for value in values}

    def get(self, field_id: str) -> dict[str, Any] | None:
        return self.by_id.get(field_id.lower())

    def search(
        self,
        keyword: str,
        *,
        category: str | None = None,
        field_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        needle = keyword.lower()
        matches = []
        for value in self.by_id.values():
            haystack = f"{value.get('id', '')} {value.get('description', '')}".lower()
            if needle not in haystack:
                continue
            if category and value.get("category", {}).get("id") != category:
                continue
            if field_type and value.get("type") != field_type:
                continue
            matches.append(value)
        matches.sort(
            key=lambda value: (
                float(value.get("coverage") or 0),
                int(value.get("alphaCount") or 0),
            ),
            reverse=True,
        )
        return matches[:limit]


def tokenize(expression: str) -> list[str]:
    return TOKEN_RE.findall(re.sub(r"//.*?$|/\*.*?\*/", "", expression, flags=re.M | re.S))


def referenced_fields(expression: str, catalog: FieldCatalog) -> list[str]:
    fields = {token.lower() for token in tokenize(expression) if catalog.get(token)}
    return sorted(fields)


def unknown_identifiers(expression: str, catalog: FieldCatalog) -> list[str]:
    unknown = set()
    for token in tokenize(expression):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
            continue
        lower = token.lower()
        if catalog.get(lower) or lower in KNOWN_OPERATORS or lower in RESERVED_IDENTIFIERS:
            continue
        unknown.add(lower)
    return sorted(unknown)


def expression_depth(tokens: Iterable[str]) -> int:
    current = maximum = 0
    for token in tokens:
        if token == "(":
            current += 1
            maximum = max(maximum, current)
        elif token == ")":
            current = max(0, current - 1)
    return maximum


def expression_complexity(expression: str, catalog: FieldCatalog) -> dict[str, Any]:
    tokens = tokenize(expression)
    fields = referenced_fields(expression, catalog)
    parameters = [token for token in tokens if re.fullmatch(r"\d+(?:\.\d+)?", token)]
    operators = [token for token in tokens if token.lower() in KNOWN_OPERATORS]
    denominator = max(1, len(parameters) + len(operators))
    return {
        "chars": len(expression),
        "tokens": len(tokens),
        "features": fields,
        "feature_count": len(fields),
        "parameters": parameters,
        "parameter_count": len(parameters),
        "parameter_ratio": len(parameters) / denominator,
        "operator_count": len(operators),
        "depth": expression_depth(tokens),
    }


def canonical_tokens(expression: str, catalog: FieldCatalog, abstract_fields: bool = False) -> list[str]:
    output = []
    for token in tokenize(expression.lower()):
        if catalog.get(token):
            output.append("<field>" if abstract_fields else token)
        elif re.fullmatch(r"\d+(?:\.\d+)?", token):
            output.append("<number>")
        else:
            output.append(token)
    return output


def _ngrams(values: list[str], n: int = 3) -> set[tuple[str, ...]]:
    if len(values) < n:
        return {tuple(values)} if values else set()
    return {tuple(values[i : i + n]) for i in range(len(values) - n + 1)}


def _jaccard(left: set[Any], right: set[Any]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / max(1, len(left | right))


def structural_similarity(left: str, right: str, catalog: FieldCatalog) -> float:
    left_tokens = canonical_tokens(left, catalog, abstract_fields=True)
    right_tokens = canonical_tokens(right, catalog, abstract_fields=True)
    structure = _jaccard(_ngrams(left_tokens), _ngrams(right_tokens))
    left_fields = set(referenced_fields(left, catalog))
    right_fields = set(referenced_fields(right, catalog))
    fields = _jaccard(left_fields, right_fields)
    return 0.70 * structure + 0.30 * fields


def core_signal_fields(expression: str, catalog: FieldCatalog) -> set[str]:
    """Return economic signal fields, excluding grouping/platform identifiers."""
    excluded_types = {"GROUP", "SYMBOL", "UNIVERSE"}
    return {
        field
        for field in referenced_fields(expression, catalog)
        if str((catalog.get(field) or {}).get("type", "")).upper() not in excluded_types
    }


def active_expression_similarity(
    expression: str, active_expression: str, catalog: FieldCatalog
) -> dict[str, float]:
    """Measure whether a candidate is a thin wrapper around an ACTIVE signal."""
    candidate_fields = core_signal_fields(expression, catalog)
    active_fields = core_signal_fields(active_expression, catalog)
    overlap = candidate_fields & active_fields
    return {
        "structural_similarity": structural_similarity(
            expression, active_expression, catalog
        ),
        # Containment is intentionally asymmetric: adding one extra field to an
        # already-deployed core should not be mistaken for a new mechanism.
        "active_core_field_containment": (
            len(overlap) / len(active_fields) if active_fields else 0.0
        ),
        "core_field_jaccard": (
            len(overlap) / len(candidate_fields | active_fields)
            if candidate_fields or active_fields
            else 0.0
        ),
    }


def candidate_id(candidate: dict[str, Any]) -> str:
    material = json.dumps(
        {
            "expression": re.sub(r"\s+", "", str(candidate.get("expression", "")).lower()),
            "settings": candidate.get("settings", {}),
            "hypothesis": candidate.get("hypothesis", {}),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def validate_feedback_contract(
    candidate: dict[str, Any],
    catalog: FieldCatalog,
    existing: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Verify that a generated child actually follows its parent feedback card."""
    existing_values = list(existing)
    parent_index = {
        str(item.get("candidate_id")): item
        for item in existing_values
        if item.get("candidate_id")
    }
    errors: list[str] = []
    details: dict[str, Any] = {"checked": False}
    operation = str(candidate.get("operation") or "")

    if operation == "mutation" and isinstance(candidate.get("repair_card"), dict):
        card = candidate["repair_card"]
        parent_id = str(card.get("parent_id") or (candidate.get("parents") or [""])[0])
        parent = parent_index.get(parent_id)
        details = {"checked": True, "kind": "mutation", "parent_id": parent_id}
        if not parent:
            errors.append(f"repair card parent {parent_id} is missing from candidate history")
            return {**details, "passed": False, "errors": errors}

        expression = str(candidate.get("expression") or "")
        parent_expression = str(parent.get("expression") or "")
        similarity = structural_similarity(expression, parent_expression, catalog)
        child_core = core_signal_fields(expression, catalog)
        parent_core = core_signal_fields(parent_expression, catalog)
        retained = child_core & parent_core
        retention = len(retained) / len(parent_core) if parent_core else 0.0
        details.update(
            {
                "parent_structural_similarity": similarity,
                "parent_core_retention": retention,
                "retained_core_fields": sorted(retained),
                "child_core_fields": sorted(child_core),
            }
        )
        maximum_similarity = float(card.get("maximum_parent_structural_similarity", 0.90))
        if similarity >= maximum_similarity:
            errors.append(
                f"feedback repair remains too similar to parent: {similarity:.3f} >= {maximum_similarity:.2f}"
            )
        maximum_retention = float(card.get("maximum_parent_core_retention", 1.0))
        if retention > maximum_retention:
            errors.append(
                f"feedback repair retains too much parent core: {retention:.3f} > {maximum_retention:.2f}"
            )
        must_keep_fields = {
            str(field).lower() for field in card.get("must_keep_fields", []) if field
        }
        missing_preserved = must_keep_fields - child_core
        if missing_preserved:
            errors.append(
                f"feedback repair dropped required fields: {sorted(missing_preserved)}"
            )
        if card.get("require_neutralization_or_core_change"):
            parent_neutralization = str(parent.get("settings", {}).get("neutralization") or "").upper()
            child_neutralization = str(candidate.get("settings", {}).get("neutralization") or "").upper()
            if parent_neutralization == child_neutralization and child_core == parent_core:
                errors.append(
                    "exposure repair changed neither neutralization nor the parent core fields"
                )

    if operation == "crossover" and isinstance(candidate.get("generation_card"), dict):
        card = candidate["generation_card"]
        details = {"checked": True, "kind": "crossover"}
        child_core = core_signal_fields(str(candidate.get("expression") or ""), catalog)
        maximum_retention = float(card.get("maximum_active_parent_core_retention", 0.79))
        active_parent_retention: dict[str, float] = {}
        for parent_id in card.get("active_parent_ids", []):
            parent = parent_index.get(str(parent_id))
            if not parent:
                continue
            parent_core = core_signal_fields(str(parent.get("expression") or ""), catalog)
            retention = len(child_core & parent_core) / len(parent_core) if parent_core else 0.0
            active_parent_retention[str(parent_id)] = retention
            if retention > maximum_retention:
                errors.append(
                    f"crossover retains {retention:.3f} of ACTIVE parent {parent_id} core; "
                    f"limit is {maximum_retention:.2f}"
                )
        details["active_parent_core_retention"] = active_parent_retention

    return {**details, "passed": not errors, "errors": errors}


def validate_candidate(
    candidate: dict[str, Any],
    catalog: FieldCatalog,
    *,
    existing: Iterable[dict[str, Any]] = (),
    config: GateConfig | None = None,
) -> dict[str, Any]:
    config = config or GateConfig()
    expression = str(candidate.get("expression", "")).strip()
    hypothesis = candidate.get("hypothesis")
    errors: list[str] = []
    warnings: list[str] = []
    if not expression:
        errors.append("expression is required")
    operation = str(candidate.get("operation", ""))
    parents = candidate.get("parents", [])
    if not isinstance(parents, list):
        errors.append("parents must be an array")
        parents = []
    if operation == "initialization" and parents:
        errors.append("initialization candidates must not have parents")
    elif operation == "mutation" and len(parents) != 1:
        errors.append("mutation candidates must have exactly one parent")
    elif operation == "crossover" and len(parents) < 2:
        errors.append("crossover candidates must have at least two parents")
    elif operation not in {"initialization", "mutation", "crossover"}:
        errors.append("operation must be initialization, mutation, or crossover")
    if not isinstance(hypothesis, dict):
        errors.append("hypothesis must be an object")
        hypothesis = {}
    for key in ("mechanism", "expected_horizon", "expected_sign", "observable_proxies", "failure_modes"):
        if not hypothesis.get(key):
            errors.append(f"hypothesis.{key} is required")

    complexity = expression_complexity(expression, catalog)
    unknown = unknown_identifiers(expression, catalog)
    if unknown:
        errors.append(f"unknown identifiers: {', '.join(unknown)}")
    if config.enable_complexity_gate and complexity["chars"] > config.max_chars:
        errors.append(f"expression exceeds {config.max_chars} characters")
    if config.enable_complexity_gate and complexity["feature_count"] > config.max_features:
        errors.append(f"expression uses more than {config.max_features} fields")
    if config.enable_complexity_gate and complexity["depth"] > config.max_depth:
        errors.append(f"expression depth exceeds {config.max_depth}")
    balance = 0
    for token in tokenize(expression):
        if token == "(":
            balance += 1
        elif token == ")":
            balance -= 1
            if balance < 0:
                break
    if balance != 0:
        errors.append("expression has unbalanced parentheses")
    if config.enable_complexity_gate and complexity["parameter_ratio"] >= config.max_parameter_ratio:
        errors.append(f"free-parameter ratio must be below {config.max_parameter_ratio:.2f}")
    if re.search(
        r"\bts_corr\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*\1\s*,",
        expression,
        flags=re.I,
    ):
        errors.append("self-correlation is tautological and must be removed")
    if re.search(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*/\s*([A-Za-z_][A-Za-z0-9_]*)"
        r"\s*\*\s*\2\s*/\s*([A-Za-z_][A-Za-z0-9_]*)\b",
        expression,
        flags=re.I,
    ):
        errors.append("algebraically cancelling ratio chain must be simplified")

    proxy_fields = set()
    required_proxy_fields = set()
    for proxy in hypothesis.get("observable_proxies", []) if isinstance(hypothesis, dict) else []:
        if isinstance(proxy, str):
            proxy_fields.add(proxy.lower())
        elif isinstance(proxy, dict) and proxy.get("field"):
            field = str(proxy["field"]).lower()
            proxy_fields.add(field)
            if proxy.get("required", True):
                required_proxy_fields.add(field)
    expression_fields = set(complexity["features"])
    undocumented = expression_fields - proxy_fields
    omitted = required_proxy_fields - expression_fields
    if config.enable_semantic_gate and undocumented:
        errors.append(f"expression fields missing from observable_proxies: {sorted(undocumented)}")
    if config.enable_semantic_gate and omitted:
        errors.append(f"required observable proxies absent from expression: {sorted(omitted)}")

    for field in expression_fields:
        metadata = catalog.get(field) or {}
        if metadata.get("type") == "VECTOR" and not re.search(rf"vec_(?:avg|sum)\s*\([^)]*\b{re.escape(field)}\b", expression, re.I):
            errors.append(f"VECTOR field {field} must be reduced with a verified vec operator")
        coverage = float(metadata.get("coverage") or 0)
        if coverage < config.min_coverage:
            warnings.append(f"field {field} has low coverage {coverage:.2f}")
        settings = candidate.get("settings", {})
        if isinstance(settings, dict):
            for key, metadata_key in (("region", "region"), ("universe", "universe"), ("delay", "delay")):
                requested = settings.get(key)
                available = metadata.get(metadata_key)
                if requested is not None and available is not None and str(requested).upper() != str(available).upper():
                    errors.append(
                        f"field {field} is catalogued for {metadata_key}={available}, not {requested}"
                    )

    claims = hypothesis.get("claims", []) if isinstance(hypothesis, dict) else []
    categories = {
        str((catalog.get(field) or {}).get("category", {}).get("id", ""))
        for field in expression_fields
    }
    for claim in claims if config.enable_semantic_gate and isinstance(claims, list) else []:
        if not isinstance(claim, dict):
            continue
        required_categories = set(claim.get("required_categories", []))
        if required_categories and not (required_categories & categories):
            errors.append(
                f"claim {claim.get('name', '<unnamed>')} lacks data from {sorted(required_categories)}"
            )

    existing_values = list(existing)
    nearest: dict[str, Any] | None = None
    for prior in existing_values:
        prior_expression = str(prior.get("expression", ""))
        if not prior_expression:
            continue
        similarity = structural_similarity(expression, prior_expression, catalog)
        if nearest is None or similarity > nearest["similarity"]:
            nearest = {"candidate_id": prior.get("candidate_id"), "similarity": similarity}
    if (
        config.enable_redundancy_gate
        and nearest
        and nearest["similarity"] >= config.max_structural_similarity
    ):
        errors.append(
            f"structural similarity {nearest['similarity']:.3f} exceeds {config.max_structural_similarity:.2f}"
        )

    repair_contract = validate_feedback_contract(candidate, catalog, existing_values)
    errors.extend(repair_contract.get("errors", []))

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "complexity": complexity,
        "nearest_structure": nearest,
        "repair_contract": repair_contract,
    }


def pnl_daily_changes(series: list[dict[str, Any]]) -> dict[str, float]:
    ordered = sorted(
        ((str(item["date"]), float(item["pnl"])) for item in series), key=lambda item: item[0]
    )
    return {
        ordered[index][0]: ordered[index][1] - ordered[index - 1][1]
        for index in range(1, len(ordered))
    }


def aligned_correlation(
    left: list[dict[str, Any]], right: list[dict[str, Any]], min_overlap: int = 50
) -> dict[str, Any]:
    left_returns = pnl_daily_changes(left)
    right_returns = pnl_daily_changes(right)
    dates = sorted(set(left_returns) & set(right_returns))
    if len(dates) < min_overlap:
        return {"correlation": None, "overlap": len(dates)}
    x = [left_returns[date] for date in dates]
    y = [right_returns[date] for date in dates]
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    denominator = math.sqrt(
        sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y)
    )
    return {
        "correlation": None if denominator == 0 else numerator / denominator,
        "overlap": len(dates),
        "start": dates[0],
        "end": dates[-1],
    }


def metric_snapshot(alpha: dict[str, Any]) -> dict[str, Any]:
    is_metrics = alpha.get("is", {}) if isinstance(alpha.get("is"), dict) else {}
    checks = [item for item in is_metrics.get("checks", []) if isinstance(item, dict)]
    return {
        "status": alpha.get("status"),
        "grade": str(alpha.get("grade") or "").upper() or None,
        "sharpe": is_metrics.get("sharpe"),
        "fitness": is_metrics.get("fitness"),
        "returns": is_metrics.get("returns"),
        "turnover": is_metrics.get("turnover"),
        "drawdown": is_metrics.get("drawdown"),
        "margin": is_metrics.get("margin"),
        "long_count": is_metrics.get("longCount"),
        "short_count": is_metrics.get("shortCount"),
        "checks": checks,
    }


def submission_eligibility(metrics: dict[str, Any]) -> dict[str, Any]:
    """Apply the WQ UI submission rule while allowing PENDING checks to resolve server-side."""
    grade = str(metrics.get("grade") or "").strip().upper()
    checks = [item for item in metrics.get("checks", []) if isinstance(item, dict)]
    failed_checks = sorted(
        {
            str(item.get("name") or "UNKNOWN_CHECK")
            for item in checks
            if str(item.get("result") or "").upper() == "FAIL"
        }
    )
    pending_checks = sorted(
        {
            str(item.get("name") or "UNKNOWN_CHECK")
            for item in checks
            if str(item.get("result") or "").upper() == "PENDING"
        }
    )
    unknown_checks = sorted(
        {
            f"{item.get('name') or 'UNKNOWN_CHECK'}:{item.get('result') or 'MISSING'}"
            for item in checks
            if str(item.get("result") or "").upper() not in {"PASS", "PENDING", "FAIL"}
        }
    )
    blockers = []
    if grade not in SUBMITTABLE_GRADES:
        blockers.append(f"IS_GRADE_{grade or 'MISSING'}")
    if not checks:
        blockers.append("IS_CHECKS_MISSING")
    blockers.extend(f"IS_TEST_FAIL:{name}" for name in failed_checks)
    blockers.extend(f"IS_TEST_UNKNOWN:{name}" for name in unknown_checks)
    return {
        "eligible": not blockers,
        "grade": grade or None,
        "grade_eligible": grade in SUBMITTABLE_GRADES,
        "failed_checks": failed_checks,
        "pending_checks": pending_checks,
        "unknown_checks": unknown_checks,
        "check_count": len(checks),
        "blockers": blockers,
        "pending_policy": "ALLOW_SERVER_RESOLUTION",
    }


def metric_gate(metrics: dict[str, Any], policy: MetricPolicy | None = None) -> dict[str, Any]:
    policy = policy or MetricPolicy()
    failures = []
    values = {
        key: float(metrics.get(key) or 0)
        for key in ("sharpe", "fitness", "returns", "turnover", "drawdown")
    }
    if values["sharpe"] < policy.min_sharpe:
        failures.append("LOW_SHARPE")
    if values["fitness"] < policy.min_fitness:
        failures.append("LOW_FITNESS")
    if values["turnover"] < policy.min_turnover:
        failures.append("LOW_TURNOVER")
    if values["turnover"] > policy.max_turnover:
        failures.append("HIGH_TURNOVER")
    if abs(values["drawdown"]) > policy.max_drawdown:
        failures.append("HIGH_DRAWDOWN")
    for check in metrics.get("checks", []):
        if check.get("result") == "FAIL":
            failures.append(str(check.get("name", "UNKNOWN_CHECK")))
    return {"passed": not failures, "failures": sorted(set(failures))}


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def trajectory_reward(
    metrics: dict[str, Any],
    complexity: dict[str, Any],
    *,
    max_abs_correlation: float | None,
    max_structural_similarity: float | None = None,
    policy: MetricPolicy | None = None,
    gates: GateConfig | None = None,
) -> dict[str, Any]:
    policy = policy or MetricPolicy()
    gates = gates or GateConfig()
    sharpe = float(metrics.get("sharpe") or 0)
    fitness = float(metrics.get("fitness") or 0)
    returns = float(metrics.get("returns") or 0)
    turnover = float(metrics.get("turnover") or 0)
    drawdown = abs(float(metrics.get("drawdown") or 0))
    if max_abs_correlation is not None:
        novelty = 1.0 - _clip(abs(max_abs_correlation), 0, 1)
        novelty_source = "pnl_correlation"
    elif max_structural_similarity is not None:
        novelty = 1.0 - _clip(max_structural_similarity, 0, 1)
        novelty_source = "structural_similarity"
    else:
        # Preserve reproducibility for historical evaluations that predate the
        # structural fallback. New evaluations always pass a structural value.
        novelty = 1.0
        novelty_source = "legacy_unavailable"
    complexity_penalty = (
        0.45 * complexity.get("chars", 0) / gates.max_chars
        + 0.35 * complexity.get("feature_count", 0) / gates.max_features
        + 0.20 * complexity.get("depth", 0) / gates.max_depth
    )
    gate = metric_gate(metrics, policy)
    components = {
        "sharpe": 0.30 * _clip(sharpe / 2.0, -1.0, 1.5),
        "fitness": 0.25 * _clip(fitness / 1.5, -1.0, 1.5),
        "returns": 0.15 * _clip(returns / 0.10, -1.0, 1.5),
        "novelty": 0.10 * novelty,
        "drawdown_penalty": -0.08 * _clip(drawdown / policy.max_drawdown, 0, 2),
        "turnover_penalty": -0.07
        * _clip(max(0.0, turnover - policy.preferred_max_turnover) / 0.50, 0, 2),
        "complexity_penalty": -0.05 * _clip(complexity_penalty, 0, 2),
        "failed_check_penalty": -0.10 * min(2, len(gate["failures"])),
    }
    return {
        "reward": sum(components.values()),
        "components": components,
        "metric_gate": gate,
        "novelty": novelty,
        "novelty_source": novelty_source,
    }


def diagnose_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
    failures = set(evaluation.get("reward", {}).get("metric_gate", {}).get("failures", []))
    failed_checks = {
        str(check.get("name") or "")
        for check in evaluation.get("metrics", {}).get("checks", [])
        if isinstance(check, dict) and str(check.get("result") or "").upper() == "FAIL"
    }
    governance_warnings = set(evaluation.get("governance_warnings", []))
    submission_blockers = set(evaluation.get("submission_blockers", []))
    max_corr = evaluation.get("max_active_correlation")
    if (
        (max_corr is not None and abs(float(max_corr)) >= 0.70)
        or "SELF_CORRELATION" in failed_checks
        or "ACTIVE_EXPRESSION_REDUNDANCY" in governance_warnings
        or "ACTIVE_EXPRESSION_REDUNDANCY" in submission_blockers
    ):
        return {
            "fault": "redundancy",
            "modification_depth": "targeted",
            "freeze": ["market_context", "validated_parent_evidence"],
            "revise": ["one_correlated_signal_leg_or_filter"],
            "instruction": (
                "Make exactly one explicit decorrelation change. Preserve the parent's validated evidence; "
                "change one correlated signal leg, one observable proxy, or one meaningful state filter."
            ),
            "inheritance_contract": (
                "A failed child invalidates only the attempted decorrelation action, not the parent. "
                "Do not rely on window, weight, decay, or neutralization changes alone."
            ),
        }
    if "CONCENTRATED_WEIGHT" in failures:
        return {
            "fault": "implementation",
            "modification_depth": "implementation",
            "freeze": ["economic_mechanism", "observable_proxies"],
            "revise": ["one_of_backfill_ranking_or_truncation"],
            "instruction": "Make one sparsity or outlier repair before changing the hypothesis.",
            "inheritance_contract": "Preserve the parent mechanism and primary proxies; test one implementation repair.",
        }
    if "HIGH_TURNOVER" in failures:
        return {
            "fault": "high_turnover",
            "modification_depth": "realization",
            "freeze": ["economic_mechanism", "expected_sign", "primary_fields"],
            "revise": ["one_of_decay_horizon_or_trade_condition"],
            "instruction": "Make one turnover-reduction change while preserving the parent signal.",
            "inheritance_contract": "Preserve the mechanism and primary fields; test one realization change.",
        }
    if "LOW_TURNOVER" in failures:
        return {
            "fault": "low_turnover",
            "modification_depth": "realization",
            "freeze": ["economic_mechanism", "expected_sign", "primary_fields"],
            "revise": ["one_of_shorter_horizon_or_more_active_proxy"],
            "instruction": "Make one activity-increasing change; do not smooth the signal further.",
            "inheritance_contract": "Preserve the parent idea and test one shorter horizon or more active proxy.",
        }
    if "LOW_SUB_UNIVERSE_SHARPE" in failures:
        return {
            "fault": "exposure",
            "modification_depth": "targeted",
            "freeze": ["economic_mechanism", "expected_sign"],
            "revise": ["one_of_grouping_neutralization_or_liquidity_dependency"],
            "instruction": "Make one exposure repair aimed at small-cap or liquidity dependence.",
            "inheritance_contract": "Preserve the research question and test one exposure-control change.",
        }
    if "LOW_FITNESS" in failures:
        return {
            "fault": "fitness",
            "modification_depth": "targeted",
            "freeze": ["validated_parent_evidence", "expected_sign"],
            "revise": ["one_identified_fitness_cause"],
            "instruction": (
                "Identify whether Fitness is limited by turnover or weak return, then change exactly one cause. "
                "Do not assume that more smoothing is always the answer."
            ),
            "inheritance_contract": "Keep the parent available even if this Fitness repair fails.",
        }
    if "LOW_SHARPE" in failures:
        return {
            "fault": "signal",
            "modification_depth": "targeted",
            "freeze": ["market_context", "validated_parent_evidence"],
            "revise": ["one_of_field_window_or_grouping"],
            "instruction": "Test one signal-strength repair: a field, horizon, or grouping change.",
            "inheritance_contract": "Do not discard the parent because one signal-strength repair fails.",
        }
    if "HIGH_DRAWDOWN" in failures:
        return {
            "fault": "drawdown",
            "modification_depth": "targeted",
            "freeze": ["economic_mechanism", "expected_sign"],
            "revise": ["one_risk_control"],
            "instruction": "Test one risk-control or state-conditioning change.",
            "inheritance_contract": "Preserve the parent signal and evaluate the chosen risk repair separately.",
        }
    return {
        "fault": "risk_or_saturation",
        "modification_depth": "targeted",
        "freeze": ["validated_mechanism", "primary_fields"],
        "revise": ["one_explicit_testable_component"],
        "instruction": "Choose one explicit, testable change supported by the recorded evaluation.",
        "inheritance_contract": "The result judges the attempted change only; it does not retire the parent.",
    }


class ResearchStore:
    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self.path = root / run_id
        self.run_path = self.path / "run.json"
        self.candidates_path = self.path / "candidates.jsonl"
        self.evaluations_path = self.path / "evaluations.jsonl"
        self.events_path = self.path / "events.jsonl"
        self.pool_path = self.path / "factor_pool.json"

    def initialize(
        self,
        *,
        iterations: int = 5,
        max_iterations: int = 15,
        directions: list[dict[str, Any]] | None = None,
        components: dict[str, bool] | None = None,
        budget: dict[str, Any] | None = None,
        gate_config: GateConfig | None = None,
    ) -> dict[str, Any]:
        if self.run_path.exists():
            raise FileExistsError(f"run already exists: {self.run_id}")
        self.path.mkdir(parents=True, exist_ok=False)
        component_config = {
            "diversified_planning": True,
            "mutation": True,
            "crossover": True,
            "semantic_gate": True,
            "complexity_gate": True,
            "redundancy_gate": True,
        }
        component_config.update(components or {})
        gates = gate_config or GateConfig(
            enable_semantic_gate=component_config["semantic_gate"],
            enable_complexity_gate=component_config["complexity_gate"],
            enable_redundancy_gate=component_config["redundancy_gate"],
        )
        budget_config = {
            "max_candidates_per_direction": 3,
            "max_repair_attempts": 2,
            "max_api_requests": 2000,
            "max_elapsed_hours": 24,
        }
        budget_config.update(budget or {})
        run = {
            "schema_version": 1,
            "run_id": self.run_id,
            "created_at": utc_now(),
            "status": "PLANNING",
            "iteration": 0,
            "target_iterations": iterations,
            "max_iterations": max_iterations,
            "early_stop_patience": 3,
            "directions": directions or DEFAULT_DIRECTIONS,
            "components": component_config,
            "budget": budget_config,
            "gate_config": asdict(gates),
            "metric_policy": asdict(MetricPolicy()),
            "test_integrity": {
                "use_hidden_or_submission_outcomes_for_evolution": False,
                "selection_data": (
                    "BRAIN in-sample metrics, ACTIVE daily-PnL correlation, and "
                    "expression redundancy fallback when ACTIVE PnL is unavailable"
                ),
            },
        }
        atomic_write_json(self.run_path, run)
        atomic_write_json(self.pool_path, {"updated_at": utc_now(), "members": []})
        append_jsonl(self.events_path, {"event": "run_initialized", "at": utc_now()})
        return run

    def load_run(self) -> dict[str, Any]:
        run = read_json(self.run_path)
        if not isinstance(run, dict):
            raise FileNotFoundError(f"run not found: {self.run_id}")
        return run

    def candidates(self) -> list[dict[str, Any]]:
        return list(iter_jsonl(self.candidates_path))

    def evaluations(self) -> list[dict[str, Any]]:
        return list(iter_jsonl(self.evaluations_path))

    def register_candidate(self, candidate: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        value = dict(candidate)
        value["candidate_id"] = candidate_id(candidate)
        value.setdefault("created_at", utc_now())
        value.setdefault("iteration", self.load_run().get("iteration", 0))
        value.setdefault("operation", "initialization")
        value.setdefault("parents", [])
        value["validation"] = validation
        existing_ids = {item.get("candidate_id") for item in self.candidates()}
        if value["candidate_id"] in existing_ids:
            raise ValueError(f"candidate already registered: {value['candidate_id']}")
        append_jsonl(self.candidates_path, value)
        append_jsonl(
            self.events_path,
            {
                "event": "candidate_registered",
                "candidate_id": value["candidate_id"],
                "passed": validation.get("passed"),
                "at": utc_now(),
            },
        )
        return value

    def record_evaluation(self, evaluation: dict[str, Any]) -> None:
        value = dict(evaluation)
        value.setdefault("evaluated_at", utc_now())
        append_jsonl(self.evaluations_path, value)
        append_jsonl(
            self.events_path,
            {
                "event": "candidate_evaluated",
                "candidate_id": value.get("candidate_id"),
                "reward": value.get("reward", {}).get("reward"),
                "at": utc_now(),
            },
        )

    def record_event(self, event: dict[str, Any]) -> None:
        value = dict(event)
        value.setdefault("at", utc_now())
        append_jsonl(self.events_path, value)


def latest_evaluations(values: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for value in values:
        candidate = value.get("candidate_id")
        if candidate:
            output[str(candidate)] = value
    return output
