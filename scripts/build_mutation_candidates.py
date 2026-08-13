#!/usr/bin/env python3
"""Materialize one deterministic Mutation child per task brief."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from feedback_generation import materialize_mutations
from research_core import FieldCatalog


SKILL_DIR = Path(__file__).resolve().parent.parent
FIELD_PATH = SKILL_DIR / "references" / "wq_usa_top3000_delay1_data_fields.json"


SPECS: dict[str, dict[str, Any]] = {
    "a0eaf426352dfe80": {
        "direction_id": "mutation-analyst-profitability-rewrite",
        "expression": "group_rank(ts_rank(anl4_afv4_eps_mean / bookvalue_ps, 126) + ts_rank(operating_income / assets, 63), subindustry)",
        "semantic_description": "在子行业内结合替代预期收益率与经营盈利资产比，降低单一行业规模暴露。",
        "mechanism": "替代分析师预期收益率与经营盈利质量共同确认重估，且子行业中性化降低规模暴露。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("bookvalue_ps", "每股账面价值"), ("operating_income", "经营盈利"), ("assets", "资产规模"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "盈利质量", "required_categories": ["fundamental"]}],
        "neutralization": "SUBINDUSTRY",
    },
    "312b78c3658c3f02": {
        "direction_id": "mutation-capital-efficiency-cash",
        "expression": "group_rank(ts_rank(cashflow_op / assets, 126) - ts_rank(capex / assets, 126), subindustry)",
        "semantic_description": "在子行业内用现金转化与资本开支强度的相对关系刻画资本配置效率。",
        "mechanism": "现金转化较强且资本开支强度较低时，资本配置效率更可能持续改善。",
        "fields": [("cashflow_op", "经营现金流"), ("assets", "资产规模"), ("capex", "资本开支"), ("subindustry", "子行业比较")],
        "claims": [{"name": "资本配置效率", "required_categories": ["fundamental"]}],
        "neutralization": "SUBINDUSTRY",
    },
    "f90fc7f817a2db96": {
        "direction_id": "mutation-option-implied-spread",
        "expression": "group_rank(ts_rank(-implied_volatility_put_30, 20) + ts_rank(implied_volatility_call_30, 20), industry)",
        "semantic_description": "在行业内结合看跌隐含波动率与看涨隐含波动率的相对状态。",
        "mechanism": "期权隐含波动率结构而非单一持仓比反映下行对冲压力与相对强弱。",
        "fields": [("implied_volatility_put_30", "看跌隐含波动率"), ("implied_volatility_call_30", "看涨隐含波动率"), ("industry", "行业比较")],
        "claims": [{"name": "期权隐含波动率", "required_categories": ["option"]}],
        "neutralization": "INDUSTRY",
    },
    "d6f168d3b98a2694": {
        "direction_id": "mutation-analyst-estimate-change",
        "expression": "group_rank(ts_rank(ts_delta(anl4_afv4_eps_mean, 21) / close, 63), subindustry)",
        "semantic_description": "在子行业内排名替代分析师预期的近期变化率。",
        "mechanism": "分析师预期的增量变化比预测区间静态分歧更直接地刻画信息更新。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}],
        "neutralization": "SUBINDUSTRY",
    },
    "ab3d26b71c1cd0fb": {
        "direction_id": "mutation-volume-confirmed-pressure",
        "expression": "group_rank(ts_mean(rank(-(close - vwap) / vwap) * rank(volume / adv20), 10), industry)",
        "semantic_description": "在行业内平滑成交参与度确认的收盘价相对VWAP负压力。",
        "mechanism": "只有成交参与度较高的价格压力才更可能代表可交易的过度反应。",
        "fields": [("close", "收盘价格"), ("vwap", "成交量加权价格"), ("volume", "成交量"), ("adv20", "常态成交量"), ("industry", "行业比较")],
        "claims": [{"name": "价格成交量反转", "required_categories": ["pv"]}],
        "neutralization": "INDUSTRY",
    },
    "7e151a601562b5bc": {
        "direction_id": "mutation-analyst-option-replacement",
        "expression": "group_rank(ts_rank(ts_delta(anl4_afv4_eps_mean, 21) / close, 63) + ts_rank(-implied_volatility_put_30, 20), industry)",
        "semantic_description": "在行业内结合分析师预期变化与看跌隐含波动率缓解。",
        "mechanism": "用分析师预期增量和期权下行风险代理替换重复的预期收益率主干。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("implied_volatility_put_30", "看跌隐含波动率"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}, {"name": "期权风险", "required_categories": ["option"]}],
        "neutralization": "INDUSTRY",
    },
    "58671e0095ed5aa9": {
        "direction_id": "mutation-news-composite-exposure",
        "expression": "group_rank(ts_rank(mean_composite_sentiment_score, 20) - ts_rank(mean_earnings_evaluation_sentiment, 20), subindustry)",
        "semantic_description": "在子行业内比较综合情绪与盈利评价情绪的相对变化。",
        "mechanism": "更换新闻信息来源并使用子行业中性化，降低单一情绪覆盖与规模暴露。",
        "fields": [("mean_composite_sentiment_score", "综合新闻情绪"), ("mean_earnings_evaluation_sentiment", "盈利评价情绪"), ("subindustry", "子行业比较")],
        "claims": [{"name": "新闻情绪", "required_categories": ["news"]}],
        "neutralization": "SUBINDUSTRY",
    },
    "66ec7e1155c6b564": {
        "direction_id": "mutation-analyst-risk-change",
        "expression": "group_rank(ts_rank(ts_delta(anl4_afv4_eps_mean, 21), 63) + ts_rank(-ts_delta(implied_volatility_call_30, 20), 20), industry)",
        "semantic_description": "在行业内联合分析师预期变化与看涨隐含波动率变化。",
        "mechanism": "预期增量与期权风险边际变化共同确认重估，而非复制原有收益率乘风险结构。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("implied_volatility_call_30", "看涨隐含波动率"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}, {"name": "期权风险变化", "required_categories": ["option"]}],
        "neutralization": "INDUSTRY",
    },
    "96f58c8ff6465a6c": {
        "direction_id": "mutation-news-composite-exposure",
        "expression": "group_rank(ts_rank(mean_composite_sentiment_score - mean_earnings_evaluation_sentiment, 63), industry)",
        "semantic_description": "在行业内用综合新闻情绪相对盈利评价情绪的中期差异，降低子行业与规模暴露。",
        "mechanism": "新闻情绪差异在行业内的中期扩散比单一情绪水平更稳健，并通过行业中性化减轻覆盖与规模依赖。",
        "fields": [("mean_composite_sentiment_score", "综合新闻情绪"), ("mean_earnings_evaluation_sentiment", "盈利评价情绪"), ("industry", "行业比较")],
        "claims": [{"name": "新闻情绪差异", "required_categories": ["news"]}],
        "neutralization": "INDUSTRY",
    },
    "86ac2ba869cec2c1": {
        "direction_id": "mutation-option-implied-spread",
        "expression": "group_rank(ts_mean(rank(implied_volatility_call_30) - rank(implied_volatility_put_30), 20), subindustry)",
        "semantic_description": "在子行业内排名看涨与看跌隐含波动率差异的中期状态，减轻行业与规模暴露。",
        "mechanism": "隐含波动率偏斜的中期变化相对单边波动率更直接刻画风险定价，并通过子行业中性化降低覆盖偏差。",
        "fields": [("implied_volatility_call_30", "看涨隐含波动率"), ("implied_volatility_put_30", "看跌隐含波动率"), ("subindustry", "子行业比较")],
        "claims": [{"name": "期权隐含波动率结构", "required_categories": ["option"]}],
        "neutralization": "SUBINDUSTRY",
    },
    "3b217ec935d7d222": {
        "direction_id": "mutation-option-implied-spread-zscore",
        "expression": "group_rank(ts_rank(implied_volatility_call_30 - implied_volatility_put_30, 20), subindustry)",
        "semantic_description": "在子行业内排名看涨与看跌隐含波动率差异的短期状态。",
        "mechanism": "隐含波动率偏斜相对看跌持仓比更直接刻画下行风险定价的变化。",
        "fields": [("implied_volatility_call_30", "看涨隐含波动率"), ("implied_volatility_put_30", "看跌隐含波动率"), ("subindustry", "子行业比较")],
        "claims": [{"name": "期权隐含波动率结构", "required_categories": ["option"]}],
        "neutralization": "SUBINDUSTRY",
    },
}

REALIZATION_SPECS: dict[str, dict[str, Any]] = {
    "6700975a6e5a24f8": {"expression": "group_rank(ts_mean(rank(operating_income / assets), 63) + ts_rank(ts_delta(operating_income / assets, 21), 42), industry)", "decay": 14},
    "7c52eb306f369393": {"expression": "group_rank(ts_rank(ts_mean(mean_composite_sentiment_score, 10), 20), industry)", "decay": 12},
    "9b37e631fab12244": {"expression": "group_rank(ts_mean(rank(-returns) + rank(-(close - vwap) / vwap), 10), industry)", "decay": 16},
    "8183d90090fd2d43": {"expression": "group_rank(rank(operating_income / assets) + ts_mean(rank(operating_income / assets), 40), subindustry)", "decay": 10},
    "c67c294b72dee775": {"expression": "group_rank(rank(ts_delta(operating_income / assets, 63)) + rank(ts_delta(operating_income / assets, 21)), industry)", "decay": 10},
    "d8cdac0df2239d75": {"expression": "group_rank(ts_rank(rank(-(close - vwap) / vwap) + rank(volume / adv20), 42), industry)", "decay": 18},
}

# Group 10 uses fresh realizations so a parent selected again never collapses
# into a previously evaluated child ID.  The task packet still controls which
# depth is allowed; these expressions only instantiate that brief.
ITERATION_17_SPECS: dict[str, dict[str, Any]] = {
    "a0eaf426352dfe80": {"expression": "group_rank(ts_mean(rank(anl4_afv4_eps_mean / close) + rank(fnd6_newa1v1300_gp / sales), 63), industry)", "decay": 12, "neutralization": "INDUSTRY"},
    "6700975a6e5a24f8": {"expression": "group_rank(ts_mean(rank(operating_income / assets), 84) + rank(ts_delta(operating_income / assets, 42)), industry)", "decay": 16, "neutralization": "INDUSTRY"},
    "7c52eb306f369393": {"expression": "group_rank(ts_mean(rank(mean_composite_sentiment_score), 21), industry)", "decay": 16, "neutralization": "INDUSTRY"},
    "d8cdac0df2239d75": {"expression": "group_rank(ts_mean(rank(-(close - vwap) / vwap) + rank(volume / adv20), 42), industry)", "decay": 20, "neutralization": "INDUSTRY"},
    "312b78c3658c3f02": {"expression": "group_rank(ts_mean(rank(-capex / assets), 63), industry)", "decay": 12, "neutralization": "INDUSTRY"},
    "f90fc7f817a2db96": {"expression": "group_rank(ts_mean(rank(implied_volatility_call_30) - rank(implied_volatility_put_30), 30), industry)", "decay": 12, "neutralization": "INDUSTRY", "fields": [("implied_volatility_call_30", "看涨隐含波动率"), ("implied_volatility_put_30", "看跌隐含波动率"), ("industry", "行业比较")]},
    "d6f168d3b98a2694": {"expression": "group_rank(-ts_rank(anl4_afv4_eps_high - anl4_afv4_eps_low, 63), industry)", "decay": 10, "neutralization": "INDUSTRY"},
    "9b37e631fab12244": {"expression": "group_rank(ts_rank(rank(-returns) + rank(-(close - vwap) / vwap), 42), industry)", "decay": 18, "neutralization": "INDUSTRY"},
    "7e151a601562b5bc": {"expression": "group_rank(ts_rank(ts_delta(est_eps, 21) / close, 63) + ts_rank(cashflow_op / sales, 126), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY"},
    "8183d90090fd2d43": {"expression": "group_rank(rank(ts_mean(operating_income / assets, 63)) + rank(ts_delta(operating_income / assets, 21)), subindustry)", "decay": 12, "neutralization": "SUBINDUSTRY"},
    "c67c294b72dee775": {"expression": "group_rank(ts_rank(ts_delta(operating_income / assets, 63), 42) + rank(operating_income / assets), industry)", "decay": 12, "neutralization": "INDUSTRY"},
    "96f58c8ff6465a6c": {"expression": "group_rank(ts_mean(rank(mean_composite_sentiment_score) - rank(mean_earnings_evaluation_sentiment), 42), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY"},
    "86ac2ba869cec2c1": {"expression": "group_rank(ts_rank(implied_volatility_put_30 / implied_volatility_call_30, 42), industry)", "decay": 12, "neutralization": "INDUSTRY"},
    "66ec7e1155c6b564": {"expression": "group_rank(ts_mean(rank(ts_delta(anl4_afv4_eps_mean, 21) / close) + rank(-ts_delta(implied_volatility_call_30, 20)), 20), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY"},
}

ITERATION_19_SPECS: dict[str, dict[str, Any]] = {
    "a0eaf426352dfe80": {"expression": "group_rank(ts_rank(anl4_afv4_eps_mean / close, 84) * rank(fnd6_newa1v1300_gp / sales), industry)", "decay": 12, "neutralization": "INDUSTRY"},
    "eb75919c8babdc50": {"expression": "group_rank(ts_mean(rank(implied_volatility_call_30 / implied_volatility_put_30), 30), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY", "fields": [("implied_volatility_call_30", "看涨隐含波动率"), ("implied_volatility_put_30", "看跌隐含波动率"), ("subindustry", "子行业比较")]},
    "6700975a6e5a24f8": {"expression": "group_rank(ts_rank(operating_income / assets, 63) + ts_mean(rank(ts_delta(operating_income / assets, 21)), 30), industry)", "decay": 16, "neutralization": "INDUSTRY"},
    "7c52eb306f369393": {"expression": "group_rank(ts_rank(ts_delta(mean_composite_sentiment_score, 5), 20), industry)", "decay": 14, "neutralization": "INDUSTRY"},
    "d8cdac0df2239d75": {"expression": "group_rank(ts_zscore((close - vwap) / vwap, 60) * rank(volume / adv20), industry)", "decay": 18, "neutralization": "INDUSTRY"},
    "312b78c3658c3f02": {"expression": "group_rank(ts_rank(-capex / assets, 126) + ts_rank(ts_delta(capex / assets, 63), 63), industry)", "decay": 14, "neutralization": "INDUSTRY"},
    "d6f168d3b98a2694": {"expression": "group_rank(ts_mean(rank(-(anl4_afv4_eps_high - anl4_afv4_eps_low)), 42), industry)", "decay": 12, "neutralization": "INDUSTRY"},
    "9b37e631fab12244": {"expression": "group_rank(ts_mean(rank(-returns) * rank(-(close - vwap) / vwap), 15), industry)", "decay": 16, "neutralization": "INDUSTRY"},
    "7e151a601562b5bc": {"expression": "group_rank(ts_rank(est_eps / close, 84) * rank(cashflow_op / sales), subindustry)", "decay": 12, "neutralization": "SUBINDUSTRY"},
    "8183d90090fd2d43": {"expression": "group_rank(ts_rank(operating_income / assets, 84) + rank(ts_delta(operating_income / assets, 21)), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY"},
    "c67c294b72dee775": {"expression": "group_rank(ts_mean(rank(operating_income / assets) * rank(ts_delta(operating_income / assets, 63)), 30), industry)", "decay": 14, "neutralization": "INDUSTRY"},
    "96f58c8ff6465a6c": {"expression": "group_rank(ts_mean(rank(mean_composite_sentiment_score) + rank(-mean_earnings_evaluation_sentiment), 30), industry)", "decay": 12, "neutralization": "INDUSTRY", "fields": [("mean_composite_sentiment_score", "综合新闻情绪"), ("mean_earnings_evaluation_sentiment", "盈利评价情绪"), ("industry", "行业比较")]},
    "67130ea7162004b9": {"expression": "group_rank(ts_mean(rank(-implied_volatility_put_30) + rank(implied_volatility_call_30), 30), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY", "fields": [("implied_volatility_put_30", "看跌隐含波动率"), ("implied_volatility_call_30", "看涨隐含波动率"), ("subindustry", "子行业比较")]},
    "66ec7e1155c6b564": {"expression": "group_rank(ts_mean(rank(ts_delta(anl4_afv4_eps_mean, 21) / close), 30) + ts_rank(-implied_volatility_call_30, 20), subindustry)", "decay": 16, "neutralization": "SUBINDUSTRY"},
}

# Group 12: fresh mechanism/realization variants for the new mutation packet.
# These deliberately change the operator architecture and, where the task is
# exposure/hypothesis repair, update the observable proxies and neutralization
# together so the child remains semantically coherent.
ITERATION_21_SPECS: dict[str, dict[str, Any]] = {
    "a0eaf426352dfe80": {"expression": "group_rank(ts_zscore(anl4_afv4_eps_mean / bookvalue_ps, 84) + rank(operating_income / assets), subindustry)", "decay": 12, "neutralization": "SUBINDUSTRY", "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("bookvalue_ps", "每股账面价值"), ("operating_income", "经营盈利"), ("assets", "资产规模"), ("subindustry", "子行业比较")]},
    "80f2250df1fd164d": {"expression": "group_rank(ts_mean(rank(implied_volatility_call_30 + implied_volatility_put_30), 45), industry)", "decay": 14, "neutralization": "INDUSTRY", "fields": [("implied_volatility_call_30", "看涨隐含波动率"), ("implied_volatility_put_30", "看跌隐含波动率"), ("industry", "行业比较")]},
    "6700975a6e5a24f8": {"expression": "group_rank(ts_mean(rank(operating_income / assets), 42) * rank(ts_delta(operating_income / assets, 21)), industry)", "decay": 16, "neutralization": "INDUSTRY"},
    "7c52eb306f369393": {"expression": "group_rank(ts_mean(rank(mean_composite_sentiment_score), 30) + ts_rank(mean_composite_sentiment_score, 10), industry)", "decay": 14, "neutralization": "INDUSTRY"},
    "d8cdac0df2239d75": {"expression": "group_rank(ts_mean(rank((close - vwap) / vwap) - rank(volume / adv20), 20), industry)", "decay": 18, "neutralization": "INDUSTRY"},
    "312b78c3658c3f02": {"expression": "group_rank(ts_mean(rank(cashflow_op / assets) - rank(capex / sales), 30), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY", "fields": [("cashflow_op", "经营现金流"), ("assets", "资产规模"), ("capex", "资本开支"), ("sales", "销售规模"), ("subindustry", "子行业比较")]},
    "d6f168d3b98a2694": {"expression": "group_rank(ts_mean(rank(anl4_afv4_eps_mean / close) - rank((anl4_afv4_eps_high - anl4_afv4_eps_low) / close), 30), subindustry)", "decay": 12, "neutralization": "SUBINDUSTRY", "fields": [("anl4_afv4_eps_mean", "分析师一致预期"), ("close", "价格尺度"), ("anl4_afv4_eps_high", "预测上界"), ("anl4_afv4_eps_low", "预测下界"), ("subindustry", "子行业比较")]},
    "9b37e631fab12244": {"expression": "group_rank(ts_rank(rank(-returns) - rank((close - vwap) / vwap), 30), industry)", "decay": 16, "neutralization": "INDUSTRY"},
    "7e151a601562b5bc": {"expression": "group_rank(ts_rank(ts_delta(est_eps, 21) / close, 42) + ts_mean(rank(cashflow_op / assets), 63), industry)", "decay": 12, "neutralization": "INDUSTRY", "fields": [("est_eps", "分析师预期EPS"), ("close", "价格尺度"), ("cashflow_op", "经营现金流"), ("assets", "资产规模"), ("industry", "行业比较")]},
    "8183d90090fd2d43": {"expression": "group_rank(ts_mean(rank(operating_income / assets), 30) + ts_rank(operating_income / assets, 63), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY"},
    "eb75919c8babdc50": {"expression": "group_rank(ts_zscore(implied_volatility_call_30 + implied_volatility_put_30, 60), subindustry)", "decay": 14, "neutralization": "SUBINDUSTRY", "fields": [("implied_volatility_call_30", "看涨隐含波动率"), ("implied_volatility_put_30", "看跌隐含波动率"), ("subindustry", "子行业比较")]},
    "c67c294b72dee775": {"expression": "group_rank(ts_mean(rank(ts_delta(operating_income / assets, 42)), 30) - rank(operating_income / assets), industry)", "decay": 12, "neutralization": "INDUSTRY"},
    "c773a0047f11e629": {"expression": "group_rank(ts_mean(rank(ts_delta(mean_composite_sentiment_score, 10)), 30), industry)", "decay": 14, "neutralization": "INDUSTRY"},
    "66ec7e1155c6b564": {"expression": "group_rank(ts_mean(rank(ts_delta(anl4_afv4_eps_mean, 42) / close) - rank(ts_delta(implied_volatility_put_30, 10)), 30), industry)", "decay": 14, "neutralization": "INDUSTRY", "fields": [("anl4_afv4_eps_mean", "分析师一致预期"), ("close", "价格尺度"), ("implied_volatility_put_30", "看跌隐含波动率变化"), ("industry", "行业比较")]},
}


def _proxy_list(parent: dict[str, Any], fields: list[tuple[str, str]] | None) -> list[dict[str, Any]]:
    if fields is None:
        return copy.deepcopy(parent.get("hypothesis", {}).get("observable_proxies", []))
    return [{"field": field, "role": role, "required": True} for field, role in fields]


def build(task_path: Path, candidates_path: Path, output_path: Path) -> None:
    tasks = json.loads(task_path.read_text(encoding="utf-8"))
    parent_index: dict[str, dict[str, Any]] = {}
    for line in candidates_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            parent_index[str(value.get("candidate_id"))] = value
    if tasks.get("generation_contract", {}).get("feedback_driven_generation"):
        snapshot_path = task_path.parent / "active_snapshot.json"
        snapshot = (
            json.loads(snapshot_path.read_text(encoding="utf-8"))
            if snapshot_path.exists()
            else {"active": []}
        )
        active_expressions = [
            str(item.get("expression") or "")
            for item in snapshot.get("active", [])
            if isinstance(item, dict)
        ]
        output = materialize_mutations(
            tasks,
            parent_index,
            list(parent_index.values()),
            FieldCatalog(FIELD_PATH),
            active_expressions,
        )
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return
    output: list[dict[str, Any]] = []
    iteration = int(tasks.get("iteration", 0))
    iteration_specs = ITERATION_21_SPECS if iteration >= 21 else (ITERATION_19_SPECS if iteration >= 19 else (ITERATION_17_SPECS if iteration >= 17 else {}))
    for task in tasks.get("mutation", []):
        parent_id = str(task["parent"])
        parent = parent_index[parent_id]
        spec = iteration_specs.get(parent_id) or SPECS.get(parent_id) or REALIZATION_SPECS.get(parent_id)
        if not spec:
            raise ValueError(f"no deterministic child spec for {parent_id}")
        child = copy.deepcopy(parent)
        for key in ("candidate_id", "validation", "created_at", "iteration"):
            child.pop(key, None)
        child["operation"] = "mutation"
        child["parents"] = [parent_id]
        child["expression"] = spec["expression"]
        child["direction_id"] = spec.get("direction_id", parent.get("direction_id"))
        child["semantic_description"] = spec.get("semantic_description", parent.get("semantic_description"))
        child["settings"] = copy.deepcopy(parent.get("settings", {}))
        if spec.get("decay") is not None:
            child["settings"]["decay"] = spec["decay"]
        if spec.get("neutralization"):
            child["settings"]["neutralization"] = spec["neutralization"]
        hypothesis = copy.deepcopy(child.get("hypothesis", {}))
        if spec.get("mechanism"):
            hypothesis["mechanism"] = spec["mechanism"]
        if spec.get("fields") is not None:
            hypothesis["observable_proxies"] = _proxy_list(parent, spec["fields"])
        if spec.get("claims") is not None:
            hypothesis["claims"] = spec["claims"]
        child["hypothesis"] = hypothesis
        child["mutation_task_parent"] = parent_id
        output.append(child)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.task, args.candidates, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
