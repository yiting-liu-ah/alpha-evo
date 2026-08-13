#!/usr/bin/env python3
"""Feedback-driven candidate materialization for future evolution cycles.

The task packet decides what must be preserved, changed, and forbidden.  This
module turns those contracts into candidates from a small, reusable research
prior library.  It intentionally does not key behavior off an iteration
number; historical candidates are used to reject repeated realizations.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Any, Iterable

from research_core import (
    FieldCatalog,
    GateConfig,
    active_expression_similarity,
    core_signal_fields,
    referenced_fields,
    validate_candidate,
)


FIELD_ROLES = {
    "adv20": "常态成交量",
    "anl4_afv4_eps_mean": "替代分析师一致预期",
    "assets": "资产规模",
    "capex": "资本开支",
    "cashflow_op": "经营现金流",
    "close": "收盘价格尺度",
    "est_eps": "分析师一致预期EPS",
    "fnd6_newa1v1300_gp": "毛利润代理",
    "implied_volatility_call_30": "看涨隐含波动率",
    "implied_volatility_put_30": "看跌隐含波动率",
    "mean_composite_sentiment_score": "综合新闻情绪",
    "mean_earnings_evaluation_sentiment": "盈利评价情绪",
    "open": "开盘价格",
    "operating_income": "经营利润",
    "returns": "短期收益冲击",
    "sales": "销售规模",
    "volume": "成交参与度",
    "vwap": "成交量加权价格",
    "industry": "行业比较",
    "subindustry": "子行业比较",
}


# These are research priors, not iteration-specific answers.  A recipe is only
# usable when it satisfies the selected parent's repair card and is not already
# present in the full run history.
SIGNALS: list[dict[str, Any]] = [
    {
        "id": "analyst-level-est",
        "cluster": "analyst-level",
        "leg": "est_eps / close",
        "fields": ["est_eps", "close"],
        "categories": ["analyst"],
        "mechanism": "行业内较高的分析师预期收益率可能反映尚未充分定价的盈利预期。",
        "semantic": "对分析师预期收益率进行稳健的时序与行业内比较。",
        "sign": "positive",
        "horizon": 126,
    },
    {
        "id": "analyst-level-alt",
        "cluster": "analyst-level",
        "leg": "anl4_afv4_eps_mean / close",
        "fields": ["anl4_afv4_eps_mean", "close"],
        "categories": ["analyst"],
        "mechanism": "替代分析师预期相对价格较高时，中期估值修复可能尚未完成。",
        "semantic": "对替代分析师预期相对价格的水平进行平滑比较。",
        "sign": "positive",
        "horizon": 126,
    },
    {
        "id": "analyst-change-est",
        "cluster": "analyst-change",
        "leg": "ts_delta(est_eps, 21) / close",
        "fields": ["est_eps", "close"],
        "categories": ["analyst"],
        "mechanism": "分析师预期的近期改善可能因信息扩散缓慢而形成中期延续。",
        "semantic": "比较价格尺度调整后的分析师预期变化。",
        "sign": "positive",
        "horizon": 63,
    },
    {
        "id": "analyst-change-alt",
        "cluster": "analyst-change",
        "leg": "ts_delta(anl4_afv4_eps_mean, 21) / close",
        "fields": ["anl4_afv4_eps_mean", "close"],
        "categories": ["analyst"],
        "mechanism": "替代分析师预期的增量变化比静态水平更直接地刻画新信息。",
        "semantic": "比较替代分析师预期近期变化的中期状态。",
        "sign": "positive",
        "horizon": 63,
    },
    {
        "id": "fundamental-profitability",
        "cluster": "fundamental-level",
        "leg": "operating_income / assets",
        "fields": ["operating_income", "assets"],
        "categories": ["fundamental"],
        "mechanism": "经营利润相对资产较高的公司具有更稳定的经营质量。",
        "semantic": "比较经营利润资产比的持续水平。",
        "sign": "positive",
        "horizon": 126,
    },
    {
        "id": "fundamental-cash",
        "cluster": "fundamental-level",
        "leg": "cashflow_op / assets",
        "fields": ["cashflow_op", "assets"],
        "categories": ["fundamental"],
        "mechanism": "经营现金流相对资产较高时，盈利质量和现金转化更可靠。",
        "semantic": "比较经营现金流资产比的持续水平。",
        "sign": "positive",
        "horizon": 126,
    },
    {
        "id": "fundamental-margin",
        "cluster": "fundamental-level",
        "leg": "fnd6_newa1v1300_gp / sales",
        "fields": ["fnd6_newa1v1300_gp", "sales"],
        "categories": ["fundamental"],
        "mechanism": "较高毛利率可能反映定价能力和持续经营质量。",
        "semantic": "比较毛利润相对销售规模的稳健水平。",
        "sign": "positive",
        "horizon": 126,
    },
    {
        "id": "fundamental-change-profit",
        "cluster": "fundamental-change",
        "leg": "ts_delta(operating_income / assets, 21)",
        "fields": ["operating_income", "assets"],
        "categories": ["fundamental"],
        "mechanism": "经营利润资产比的改善包含区别于静态盈利水平的增量信息。",
        "semantic": "比较经营盈利效率的近期变化。",
        "sign": "positive",
        "horizon": 63,
    },
    {
        "id": "fundamental-change-cash",
        "cluster": "fundamental-change",
        "leg": "ts_delta(cashflow_op / assets, 21)",
        "fields": ["cashflow_op", "assets"],
        "categories": ["fundamental"],
        "mechanism": "现金转化效率的改善可能先于市场对经营质量的重新定价。",
        "semantic": "比较经营现金流资产比的近期改善。",
        "sign": "positive",
        "horizon": 63,
    },
    {
        "id": "investment-discipline",
        "cluster": "fundamental-change",
        "leg": "cashflow_op / assets - capex / sales",
        "fields": ["cashflow_op", "assets", "capex", "sales"],
        "categories": ["fundamental"],
        "mechanism": "现金转化较强且资本开支强度较低时，资本配置更可能保持纪律性。",
        "semantic": "比较现金转化与资本开支强度之间的差异。",
        "sign": "positive",
        "horizon": 126,
    },
    {
        "id": "price-reversal-return",
        "cluster": "price-reversal",
        "leg": "-ts_sum(returns, 5)",
        "fields": ["returns"],
        "categories": ["pv"],
        "mechanism": "短期负收益冲击可能包含暂时性过度反应并在随后修复。",
        "semantic": "比较短期负收益冲击的反转强度。",
        "sign": "positive",
        "horizon": 20,
    },
    {
        "id": "price-reversal-intraday",
        "cluster": "price-reversal",
        "leg": "-(close / open - 1)",
        "fields": ["close", "open"],
        "categories": ["pv"],
        "mechanism": "日内负价格压力可能代表短期流动性冲击后的反转机会。",
        "semantic": "比较日内负价格压力。",
        "sign": "positive",
        "horizon": 20,
    },
    {
        "id": "price-reversal-vwap",
        "cluster": "price-reversal",
        "leg": "-(close - vwap) / vwap",
        "fields": ["close", "vwap"],
        "categories": ["pv"],
        "mechanism": "收盘价低于VWAP的压力可能包含可修复的短期失衡。",
        "semantic": "比较收盘价相对VWAP的负压力。",
        "sign": "positive",
        "horizon": 20,
    },
    {
        "id": "price-volume-participation",
        "cluster": "price-volume",
        "leg": "volume / adv20",
        "fields": ["volume", "adv20"],
        "categories": ["pv"],
        "mechanism": "异常成交参与度可用于识别信息冲击而非普通价格噪声。",
        "semantic": "比较成交参与度相对常态水平的变化。",
        "sign": "conditional",
        "horizon": 20,
    },
    {
        "id": "option-downside",
        "cluster": "option-volatility",
        "leg": "-implied_volatility_put_30",
        "fields": ["implied_volatility_put_30"],
        "categories": ["option"],
        "mechanism": "较低的看跌隐含波动率压力可能反映下行风险定价缓解。",
        "semantic": "比较看跌隐含波动率压力。",
        "sign": "positive",
        "horizon": 60,
    },
    {
        "id": "option-upside",
        "cluster": "option-volatility",
        "leg": "-implied_volatility_call_30",
        "fields": ["implied_volatility_call_30"],
        "categories": ["option"],
        "mechanism": "看涨隐含波动率的相对缓和可作为整体风险状态的单边代理。",
        "semantic": "比较看涨隐含波动率压力。",
        "sign": "positive",
        "horizon": 60,
    },
    {
        "id": "option-skew",
        "cluster": "option-volatility",
        "leg": "implied_volatility_call_30 - implied_volatility_put_30",
        "fields": ["implied_volatility_call_30", "implied_volatility_put_30"],
        "categories": ["option"],
        "mechanism": "看涨与看跌隐含波动率差异刻画相对风险偏好和下行对冲压力。",
        "semantic": "比较看涨与看跌隐含波动率之间的偏斜。",
        "sign": "positive",
        "horizon": 60,
    },
    {
        "id": "option-downside-change",
        "cluster": "option-volatility",
        "leg": "-ts_delta(implied_volatility_put_30, 20)",
        "fields": ["implied_volatility_put_30"],
        "categories": ["option"],
        "mechanism": "看跌隐含波动率的边际下降可能比静态风险水平更及时地反映下行压力缓解。",
        "semantic": "比较看跌隐含波动率压力的近期变化。",
        "sign": "positive",
        "horizon": 20,
    },
    {
        "id": "option-upside-change",
        "cluster": "option-volatility",
        "leg": "-ts_delta(implied_volatility_call_30, 20)",
        "fields": ["implied_volatility_call_30"],
        "categories": ["option"],
        "mechanism": "看涨隐含波动率的边际下降可作为风险状态缓和的单边变化代理。",
        "semantic": "比较看涨隐含波动率压力的近期变化。",
        "sign": "positive",
        "horizon": 20,
    },
    {
        "id": "news-composite",
        "cluster": "news-attention",
        "leg": "mean_composite_sentiment_score",
        "fields": ["mean_composite_sentiment_score"],
        "categories": ["news"],
        "mechanism": "综合新闻情绪的持续改善可能通过缓慢信息扩散影响相对收益。",
        "semantic": "比较综合新闻情绪的持续状态。",
        "sign": "positive",
        "horizon": 20,
    },
    {
        "id": "news-earnings",
        "cluster": "news-attention",
        "leg": "mean_earnings_evaluation_sentiment",
        "fields": ["mean_earnings_evaluation_sentiment"],
        "categories": ["news"],
        "mechanism": "盈利评价情绪的改善可能在事件后逐步反映到价格中。",
        "semantic": "比较盈利评价情绪的持续状态。",
        "sign": "positive",
        "horizon": 20,
    },
    {
        "id": "news-relative",
        "cluster": "news-attention",
        "leg": "mean_composite_sentiment_score - mean_earnings_evaluation_sentiment",
        "fields": ["mean_composite_sentiment_score", "mean_earnings_evaluation_sentiment"],
        "categories": ["news"],
        "mechanism": "综合情绪相对盈利评价情绪的差异可能识别尚未被盈利叙事解释的注意力变化。",
        "semantic": "比较综合新闻情绪与盈利评价情绪的相对差异。",
        "sign": "conditional",
        "horizon": 20,
    },
]


ALTERNATIVE_CLUSTERS = {
    "analyst-level": ["fundamental-change", "price-reversal", "option-volatility", "news-attention"],
    "analyst-change": ["fundamental-level", "price-reversal", "option-volatility", "news-attention"],
    "fundamental-level": ["analyst-change", "price-reversal", "option-volatility", "news-attention"],
    "fundamental-change": ["analyst-level", "price-reversal", "option-volatility", "news-attention"],
    "price-reversal": ["analyst-change", "fundamental-level", "option-volatility", "news-attention"],
    "price-volume": ["analyst-change", "fundamental-level", "price-reversal", "option-volatility"],
    "option-volatility": ["analyst-change", "fundamental-level", "price-reversal", "news-attention"],
    "news-attention": ["analyst-change", "fundamental-level", "price-reversal", "option-volatility"],
    "other": ["analyst-change", "fundamental-level", "price-reversal", "option-volatility"],
}


def _stable_offset(*values: object) -> int:
    material = "|".join(str(value) for value in values)
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:8], 16)


def _rotate(values: list[Any], offset: int) -> list[Any]:
    if not values:
        return []
    position = offset % len(values)
    return values[position:] + values[:position]


def _split_group_rank(expression: str) -> tuple[str, str] | None:
    value = expression.strip()
    prefix = "group_rank("
    if not value.lower().startswith(prefix) or not value.endswith(")"):
        return None
    content = value[len(prefix) : -1]
    depth = 0
    commas: list[int] = []
    for index, character in enumerate(content):
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
        elif character == "," and depth == 0:
            commas.append(index)
    if len(commas) != 1:
        return None
    index = commas[0]
    return content[:index].strip(), content[index + 1 :].strip()


def _proxies(fields: Iterable[str]) -> list[dict[str, Any]]:
    return [
        {"field": field, "role": FIELD_ROLES.get(field, field), "required": True}
        for field in dict.fromkeys(fields)
    ]


def _claims(categories: Iterable[str], label: str) -> list[dict[str, Any]]:
    return [
        {"name": f"{label}-{category}", "required_categories": [category]}
        for category in dict.fromkeys(categories)
    ]


def _settings(parent: dict[str, Any], *, decay: int, neutralization: str) -> dict[str, Any]:
    settings = copy.deepcopy(parent.get("settings", {}))
    settings["decay"] = decay
    settings["neutralization"] = neutralization
    return settings


def _active_adjacent(
    expression: str,
    active_expressions: Iterable[str],
    catalog: FieldCatalog,
) -> bool:
    for active_expression in active_expressions:
        if not active_expression:
            continue
        similarity = active_expression_similarity(expression, active_expression, catalog)
        if (
            similarity["active_core_field_containment"] >= 0.80
            and similarity["structural_similarity"] >= 0.35
        ):
            return True
    return False


def _recipe_expressions(signal: dict[str, Any], group: str, offset: int) -> list[tuple[str, str]]:
    horizon = int(signal["horizon"])
    smooth = 42 if horizon >= 63 else 20
    leg = str(signal["leg"])
    variants = [
        ("ranked", f"group_rank(ts_rank({leg}, {horizon}), {group})"),
        ("smoothed", f"group_rank(ts_mean(rank({leg}), {smooth}), {group})"),
        ("zscored", f"group_rank(ts_zscore({leg}, {horizon}), {group})"),
    ]
    return _rotate(variants, offset)


def _candidate_from_signal(
    parent: dict[str, Any],
    task: dict[str, Any],
    signal: dict[str, Any],
    expression: str,
    architecture: str,
    group: str,
) -> dict[str, Any]:
    card = copy.deepcopy(task.get("repair_card", {}))
    fields = list(signal["fields"]) + [group]
    fault = str(card.get("fault") or task.get("fault_localization", {}).get("fault") or "feedback")
    return {
        "direction_id": f"feedback-{fault}-{signal['id']}",
        "hypothesis": {
            "mechanism": signal["mechanism"],
            "expected_horizon": int(signal["horizon"]),
            "expected_sign": signal["sign"],
            "observable_proxies": _proxies(fields),
            "failure_modes": [
                "字段覆盖或更新频率可能削弱信号",
                "市场状态变化可能导致机制阶段性失效",
                "行业内商业模式差异可能残留风险暴露",
            ],
            "claims": _claims(signal["categories"], str(signal["id"])),
        },
        "semantic_description": signal["semantic"],
        "expression": expression,
        "settings": _settings(
            parent,
            decay=max(8, min(20, int(parent.get("settings", {}).get("decay", 8) or 8) + 2)),
            neutralization=group.upper(),
        ),
        "operation": "mutation",
        "parents": [str(task["parent"])],
        "mutation_task_parent": str(task["parent"]),
        "repair_card": card,
        "generation_trace": {
            "mode": "feedback_driven",
            "source": "research_prior",
            "recipe_id": signal["id"],
            "architecture": architecture,
            "fault": fault,
            "action_id": f"research_prior:{signal['id']}:{architecture}",
        },
    }


def _candidate_from_parent_realization(
    parent: dict[str, Any], task: dict[str, Any], expression: str, architecture: str, group: str
) -> dict[str, Any]:
    child = copy.deepcopy(parent)
    for key in ("candidate_id", "validation", "created_at", "iteration"):
        child.pop(key, None)
    card = copy.deepcopy(task.get("repair_card", {}))
    child["direction_id"] = f"feedback-{card.get('fault', 'repair')}-{parent.get('direction_id', 'parent')}"
    child["expression"] = expression
    child["operation"] = "mutation"
    child["parents"] = [str(task["parent"])]
    child["mutation_task_parent"] = str(task["parent"])
    child["repair_card"] = card
    parent_decay = int(parent.get("settings", {}).get("decay", 8) or 8)
    target_decay = (
        max(0, parent_decay - 4)
        if str(card.get("fault") or "") == "low_turnover"
        else max(10, min(30, parent_decay + 4))
        if str(card.get("fault") or "") == "high_turnover"
        else parent_decay
    )
    child["settings"] = _settings(
        parent,
        decay=target_decay,
        neutralization=group.upper(),
    )
    fields = referenced_fields(expression, task["catalog"])
    roles = {
        str(item.get("field")): str(item.get("role") or item.get("field"))
        for item in parent.get("hypothesis", {}).get("observable_proxies", [])
        if isinstance(item, dict) and item.get("field")
    }
    hypothesis = copy.deepcopy(parent.get("hypothesis", {}))
    hypothesis["observable_proxies"] = [
        {"field": field, "role": roles.get(field, FIELD_ROLES.get(field, field)), "required": True}
        for field in fields
    ]
    child["hypothesis"] = hypothesis
    child["semantic_description"] = (
        f"{parent.get('semantic_description', '')} 本次仅按反馈调整平滑或风险暴露，不改变原始信号方向。"
    ).strip()
    child["generation_trace"] = {
        "mode": "feedback_driven",
        "source": "parent_realization",
        "architecture": architecture,
        "fault": card.get("fault"),
        "action_id": f"parent_realization:{card.get('fault')}:{architecture}",
    }
    return child


def _parent_realizations(
    parent: dict[str, Any], task: dict[str, Any], catalog: FieldCatalog
) -> list[dict[str, Any]]:
    parsed = _split_group_rank(str(parent.get("expression", "")))
    if not parsed:
        return []
    signal, parent_group = parsed
    card = task.get("repair_card", {})
    fault = str(card.get("fault") or "")
    group = "subindustry" if fault == "exposure" else parent_group
    if fault == "low_turnover":
        variants = [
            ("short_rank_parent_signal", f"group_rank(ts_rank({signal}, 20), {group})"),
            ("delta_parent_signal", f"group_rank(ts_delta({signal}, 10), {group})"),
            ("short_zscore_parent_signal", f"group_rank(ts_zscore({signal}, 20), {group})"),
        ]
    elif fault == "exposure":
        variants = [
            ("subindustry_grouping", f"group_rank({signal}, subindustry)"),
        ]
    elif fault == "redundancy":
        parent_core_fields = [
            str(value) for value in card.get("parent_core_fields", []) if value
        ]
        leg_replacements = [
            (
                "analyst_alt_zscore_level_to_smoothed_change",
                "ts_zscore(anl4_afv4_eps_mean / close, 60)",
                "ts_mean(rank(ts_delta(anl4_afv4_eps_mean, 21) / close), 42)",
            ),
            (
                "cash_cross_section_to_ranked_change",
                "rank(cashflow_op / assets)",
                "ts_rank(ts_delta(cashflow_op / assets, 21), 42)",
            ),
            (
                "profitability_level_to_smoothed_change",
                "ts_rank(operating_income / assets, 42)",
                "ts_mean(rank(ts_delta(operating_income / assets, 21)), 42)",
            ),
            (
                "analyst_alt_rank_level_to_smoothed_change",
                "ts_rank(anl4_afv4_eps_mean / close, 126)",
                "ts_mean(rank(ts_delta(anl4_afv4_eps_mean, 21) / close), 42)",
            ),
            (
                "cash_level_to_smoothed_change",
                "ts_rank(cashflow_op / assets, 126)",
                "ts_mean(rank(ts_delta(cashflow_op / assets, 21)), 42)",
            ),
            (
                "vwap_rank_to_return_cross_section",
                "ts_rank(-(close - vwap) / vwap, 20)",
                "rank(-ts_sum(returns, 5))",
            ),
            (
                "analyst_alt_level_to_change",
                "anl4_afv4_eps_mean / close",
                "ts_delta(anl4_afv4_eps_mean, 21) / close",
            ),
            (
                "analyst_est_level_to_change",
                "est_eps / close",
                "ts_delta(est_eps, 21) / close",
            ),
            (
                "return_reversal_to_intraday_pressure",
                "-ts_sum(returns, 5)",
                "-(close / open - 1)",
            ),
            (
                "vwap_pressure_to_return_reversal",
                "-(close - vwap) / vwap",
                "-ts_sum(returns, 5)",
            ),
        ]
        variants = [
            (
                f"correlated_leg_replacement_{name}",
                f"group_rank({signal.replace(old, new, 1)}, {group})",
            )
            for name, old, new in leg_replacements
            if old in signal
        ]
        state_fields = parent_core_fields or [signal]
        for state_field in state_fields:
            field_tag = state_field.replace("-", "_")
            variants.extend(
                [
                    (
                        f"parent_proxy_volatility_filter_{field_tag}",
                        f"group_rank(({signal}) * rank(-ts_std_dev({state_field}, 20)), {group})",
                    ),
                    (
                        f"parent_proxy_change_filter_{field_tag}",
                        f"group_rank(({signal}) * rank(ts_delta({state_field}, 20)), {group})",
                    ),
                    (
                        f"parent_proxy_state_filter_{field_tag}",
                        f"group_rank(({signal}) * rank(ts_zscore({state_field}, 60)), {group})",
                    ),
                ]
            )
    else:
        variants = [
            ("smooth_parent_signal", f"group_rank(ts_mean(rank({signal}), 42), {group})"),
            ("decay_parent_signal", f"group_rank(ts_decay_linear(rank({signal}), 20), {group})"),
            ("two_stage_parent_signal", f"group_rank(ts_rank(ts_mean({signal}, 20), 63), {group})"),
        ]
    output = []
    for architecture, expression in _rotate(
        variants, _stable_offset(task.get("parent"), task.get("iteration"), fault)
    ):
        task_with_catalog = dict(task)
        task_with_catalog["catalog"] = catalog
        output.append(
            _candidate_from_parent_realization(
                parent, task_with_catalog, expression, architecture, group
            )
        )
    return output


def _mutation_signal_order(task: dict[str, Any]) -> list[dict[str, Any]]:
    fault = str(task.get("repair_card", {}).get("fault") or task.get("fault_localization", {}).get("fault") or "")
    return _rotate(
        list(SIGNALS),
        _stable_offset(task.get("parent"), task.get("iteration"), fault),
    )


def materialize_mutations(
    tasks: dict[str, Any],
    parents: dict[str, dict[str, Any]],
    existing: list[dict[str, Any]],
    catalog: FieldCatalog,
    active_expressions: Iterable[str] = (),
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    gate = GateConfig()
    iteration = int(tasks.get("iteration", 0))
    for task_index, task in enumerate(tasks.get("mutation", []), 1):
        task = dict(task)
        task["iteration"] = iteration
        parent_id = str(task["parent"])
        parent = parents[parent_id]
        card = task.get("repair_card", {})
        fault = str(card.get("fault") or "")
        budget = 1 if int(card.get("version", 1)) >= 2 else int(task.get("expression_budget", 1))
        failed_action_ids = {
            str(value) for value in card.get("failed_action_ids", []) if value
        }
        attempts: list[dict[str, Any]] = []
        if fault in {
            "implementation",
            "realization",
            "high_turnover",
            "low_turnover",
            "exposure",
            "fitness",
            "signal",
            "drawdown",
            "redundancy",
            "risk_or_saturation",
        }:
            attempts.extend(_parent_realizations(parent, task, catalog))
        if fault != "redundancy":
            for signal in _mutation_signal_order(task):
                group = "subindustry" if fault == "exposure" else (
                    "subindustry" if _stable_offset(parent_id, signal["id"]) % 2 else "industry"
                )
                for architecture, expression in _recipe_expressions(
                    signal, group, _stable_offset(parent_id, iteration, signal["id"])
                ):
                    attempts.append(
                        _candidate_from_signal(
                            parent, task, signal, expression, architecture, group
                        )
                    )
        produced = 0
        rejection_diagnostics: list[dict[str, Any]] = []
        for child in attempts:
            if produced >= budget:
                break
            if str(child.get("generation_trace", {}).get("action_id") or "") in failed_action_ids:
                continue
            validation = validate_candidate(
                child, catalog, existing=[*existing, *output], config=gate
            )
            if validation["passed"]:
                child["generation_trace"]["preflight"] = {
                    "passed": True,
                    "nearest_similarity": (
                        validation.get("nearest_structure") or {}
                    ).get("similarity"),
                    "repair_contract": validation.get("repair_contract"),
                }
                produced += 1
                child["mutation_task_index"] = task_index
                child["mutation_realization_index"] = produced
                output.append(child)
            elif len(rejection_diagnostics) < 30:
                rejection_diagnostics.append(
                    {
                        "action_id": child.get("generation_trace", {}).get("action_id"),
                        "errors": validation.get("errors", []),
                        "nearest_similarity": (
                            validation.get("nearest_structure") or {}
                        ).get("similarity"),
                    }
                )
        if produced < budget:
            raise ValueError(
                f"Mutation task {task_index} for parent {parent_id} produced "
                f"{produced}/{budget} feedback-compliant children; review the repair "
                "card instead of falling back to an unrelated formula; "
                f"rejections={rejection_diagnostics}"
            )
    return output


def _signals_for_cluster(cluster: str, offset: int) -> list[dict[str, Any]]:
    values = [signal for signal in SIGNALS if signal["cluster"] == cluster]
    if not values:
        values = [signal for signal in SIGNALS if signal["cluster"] in ALTERNATIVE_CLUSTERS["other"]]
    return _rotate(values, offset)


def _signals_for_parent_decision(
    profile: dict[str, Any],
    hypothesis: dict[str, Any],
    offset: int,
    *,
    prefer_complement: bool = False,
) -> list[dict[str, Any]]:
    """Return recipes that represent the parent's full validated decision.

    A mechanism profile has one dominant cluster, but a crossover parent can
    contain additional validated legs (for example analyst + cash + VWAP).
    Restricting selection to the dominant cluster makes different parents look
    identical and can leave a crossover task without enough distinct children.
    Observable proxies and claim categories retain those non-dominant legs.
    """
    cluster = str(profile.get("cluster") or "other")
    proxy_fields = {
        str(item.get("field"))
        for item in hypothesis.get("observable_proxies", [])
        if isinstance(item, dict) and item.get("field")
    }
    categories = {
        str(category)
        for item in hypothesis.get("claims", [])
        if isinstance(item, dict)
        for category in item.get("required_categories", [])
    }
    categories.update(str(value) for value in profile.get("categories", []) if value)

    dominant = [signal for signal in SIGNALS if signal["cluster"] == cluster]
    contextual = [
        signal
        for signal in SIGNALS
        if signal["cluster"] != cluster
        and set(signal["fields"]).issubset(proxy_fields)
        and bool(set(signal["categories"]) & categories)
    ]
    dominant_fields = {str(value) for value in profile.get("dominant_fields", []) if value}
    novel_contextual = [
        signal
        for signal in contextual
        if set(signal["fields"]) - dominant_fields - {"close"}
    ]
    adjacent_contextual = [signal for signal in contextual if signal not in novel_contextual]
    rotated_dominant = _rotate(dominant, offset)
    rotated_contextual = [
        *_rotate(novel_contextual, offset),
        *_rotate(adjacent_contextual, offset),
    ]
    values = (
        [*rotated_contextual, *rotated_dominant]
        if prefer_complement
        else [*rotated_dominant, *rotated_contextual]
    )
    if not values:
        return _signals_for_cluster(cluster, offset)
    return values


def _crossover_candidate(
    parent: dict[str, Any],
    task: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
    expression: str,
    architecture: str,
    group: str,
    task_index: int,
) -> dict[str, Any]:
    categories = list(dict.fromkeys([*left["categories"], *right["categories"]]))
    fields = list(dict.fromkeys([*left["fields"], *right["fields"], group]))
    return {
        "direction_id": f"feedback-crossover-{left['id']}-{right['id']}-{architecture}",
        "hypothesis": {
            "mechanism": (
                f"{left['mechanism']} 同时，{right['mechanism']}；两类信息共同出现时，"
                "相对定价信号更可能具有基本面或状态支持。"
            ),
            "expected_horizon": max(int(left["horizon"]), int(right["horizon"])),
            "expected_sign": "conditional",
            "observable_proxies": _proxies(fields),
            "failure_modes": [
                "两个信息来源可能并非真正互补",
                "字段覆盖差异可能造成条件样本偏移",
                "组合在市场状态切换时可能失效",
            ],
            "claims": _claims(categories, "feedback-crossover"),
        },
        "semantic_description": f"{left['semantic']} 并由另一条独立信息腿确认：{right['semantic']}",
        "expression": expression,
        "settings": _settings(parent, decay=10, neutralization=group.upper()),
        "operation": "crossover",
        "parents": list(task["parents"]),
        "crossover_task_index": task_index,
        "generation_card": copy.deepcopy(task.get("generation_card", {})),
        "generation_trace": {
            "mode": "feedback_driven",
            "source": "parent_decision_segments",
            "left_recipe": left["id"],
            "right_recipe": right["id"],
            "architecture": architecture,
        },
    }


def materialize_crossovers(
    tasks: dict[str, Any],
    parents: dict[str, dict[str, Any]],
    existing: list[dict[str, Any]],
    catalog: FieldCatalog,
    active_expressions: Iterable[str] = (),
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    gate = GateConfig()
    iteration = int(tasks.get("iteration", 0))
    for task_index, task in enumerate(tasks.get("crossover", []), 1):
        rejection_diagnostics: list[str] = []
        profiles = task.get("parent_mechanism_profiles", [])
        if len(profiles) < 2:
            raise ValueError("feedback-driven Crossover requires two parent mechanism profiles")
        hypotheses = task.get("parent_hypotheses", [])
        left_hypothesis = hypotheses[0] if len(hypotheses) > 0 else {}
        right_hypothesis = hypotheses[1] if len(hypotheses) > 1 else {}
        same_dominant_cluster = str(profiles[0].get("cluster") or "other") == str(
            profiles[1].get("cluster") or "other"
        )
        left_signals = _signals_for_parent_decision(
            profiles[0],
            left_hypothesis,
            _stable_offset(task.get("parents", [""])[0], iteration),
        )
        right_signals = _signals_for_parent_decision(
            profiles[1],
            right_hypothesis,
            _stable_offset(task.get("parents", ["", ""])[1], iteration),
            prefer_complement=same_dominant_cluster,
        )
        parent = parents[str(task["parents"][0])]
        budget = int(task.get("expression_budget", 1))
        attempts: list[dict[str, Any]] = []
        for left in left_signals:
            for right in right_signals:
                if left["id"] == right["id"]:
                    continue
                if len(set(left["fields"]) | set(right["fields"])) > 5:
                    continue
                group = "subindustry" if _stable_offset(left["id"], right["id"], iteration) % 2 else "industry"
                pairs = [
                    (
                        "smoothed_confirmation",
                        f"group_rank(ts_mean(rank({left['leg']}) + rank({right['leg']}), 42), {group})",
                    ),
                    (
                        "dual_rank",
                        f"group_rank(ts_rank({left['leg']}, 63) + ts_rank({right['leg']}, 63), {group})",
                    ),
                    (
                        "conditional_interaction",
                        f"group_rank(ts_rank({left['leg']}, 63) * rank({right['leg']}), {group})",
                    ),
                    (
                        "joint_change",
                        f"group_rank(ts_decay_linear(rank(ts_delta({left['leg']}, 21)) + rank(ts_delta({right['leg']}, 21)), 20), {group})",
                    ),
                    (
                        "joint_change_interaction",
                        f"group_rank(ts_decay_linear(rank(ts_delta({left['leg']}, 21)) * rank(ts_delta({right['leg']}, 21)), 20), {group})",
                    ),
                    (
                        "relative_change",
                        f"group_rank(ts_rank(ts_delta({left['leg']}, 21) - ts_delta({right['leg']}, 21), 63), {group})",
                    ),
                    (
                        "state_conditioned",
                        f"group_rank(ts_rank({left['leg']}, 63) * rank(-ts_std_dev({right['leg']}, 20)), {group})",
                    ),
                    (
                        "co_movement",
                        f"group_rank(ts_corr({left['leg']}, {right['leg']}, 60), {group})",
                    ),
                    (
                        "co_dispersion",
                        f"group_rank(ts_covariance({left['leg']}, {right['leg']}, 60), {group})",
                    ),
                    (
                        "relative_state",
                        f"group_rank(ts_zscore({left['leg']}, 60) - ts_zscore({right['leg']}, 60), {group})",
                    ),
                ]
                for architecture, expression in _rotate(
                    pairs, _stable_offset(left["id"], right["id"], iteration)
                ):
                    attempts.append(
                        _crossover_candidate(
                            parent,
                            task,
                            left,
                            right,
                            expression,
                            architecture,
                            group,
                            task_index,
                        )
                    )
        for child in attempts:
            if len([item for item in output if item.get("crossover_task_index") == task_index]) >= budget:
                break
            if _active_adjacent(str(child["expression"]), active_expressions, catalog):
                if len(rejection_diagnostics) < 30:
                    rejection_diagnostics.append(
                        f"{child['direction_id']}: ACTIVE_ADJACENCY"
                    )
                continue
            validation = validate_candidate(
                child, catalog, existing=[*existing, *output], config=gate
            )
            if not validation["passed"]:
                if len(rejection_diagnostics) < 30:
                    rejection_diagnostics.append(
                        f"{child['direction_id']}: "
                        + "; ".join(str(error) for error in validation.get("errors", []))
                    )
                continue
            child["generation_trace"]["preflight"] = {
                "passed": True,
                "nearest_similarity": (
                    validation.get("nearest_structure") or {}
                ).get("similarity"),
                "repair_contract": validation.get("repair_contract"),
            }
            output.append(child)
        produced = len(
            [item for item in output if item.get("crossover_task_index") == task_index]
        )
        if produced < budget:
            accepted_ids = [
                str(item.get("direction_id"))
                for item in output
                if item.get("crossover_task_index") == task_index
            ]
            raise ValueError(
                f"Crossover task {task_index} produced {produced}/{budget} "
                f"feedback-compliant children; accepted={accepted_ids}; "
                f"rejections={rejection_diagnostics}"
            )
    return output
