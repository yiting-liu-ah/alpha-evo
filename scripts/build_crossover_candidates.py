#!/usr/bin/env python3
"""Materialize deterministic Crossover children from the current task packet."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from feedback_generation import materialize_crossovers
from research_core import FieldCatalog


SKILL_DIR = Path(__file__).resolve().parent.parent
FIELD_PATH = SKILL_DIR / "references" / "wq_usa_top3000_delay1_data_fields.json"


SPECS: list[dict[str, Any]] = [
    {
        "direction_id": "crossover2-forecast-cash-product",
        "expression": "group_rank(ts_mean(rank(est_eps / bookvalue_ps) * rank(cashflow_op / sales), 63), industry)",
        "semantic": "在行业内平滑分析师预期价值与现金转化质量的乘积。",
        "mechanism": "预期收益率与现金转化质量同时较高时，估值重估更可能持续。",
        "fields": [("est_eps", "分析师预期每股收益"), ("bookvalue_ps", "每股账面价值"), ("cashflow_op", "经营现金流"), ("sales", "收入规模"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "现金转化质量", "required_categories": ["fundamental"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover2-analyst-cash-level",
        "expression": "group_rank(ts_rank(anl4_afv4_eps_mean / close, 63) + ts_rank(cashflow_op / sales, 126), subindustry)",
        "semantic": "在子行业内合并替代预期收益率和经营现金流收入比。",
        "mechanism": "替代预期收益率在现金转化支持下更可能形成持续重估。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("cashflow_op", "经营现金流"), ("sales", "收入规模"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "现金质量", "required_categories": ["fundamental"]}],
        "neutralization": "SUBINDUSTRY",
    },
    {
        "direction_id": "crossover2-forecast-cash-interaction",
        "expression": "group_rank(ts_rank(est_eps / close, 126) * rank(cashflow_op / assets), subindustry)",
        "semantic": "在子行业内用现金质量确认分析师预期收益率。",
        "mechanism": "预期收益率只有在经营现金流资产比支持时才形成可信重估。",
        "fields": [("est_eps", "分析师预期每股收益"), ("close", "价格尺度"), ("cashflow_op", "经营现金流"), ("assets", "资产规模"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "经营现金流质量", "required_categories": ["fundamental"]}],
        "neutralization": "SUBINDUSTRY",
    },
    {
        "direction_id": "crossover2-forecast-reversal-product",
        "expression": "group_rank(ts_rank(est_eps / bookvalue_ps, 126) * rank(-ts_mean(returns, 5)), subindustry)",
        "semantic": "在子行业内用短期负收益冲击确认分析师预期价值。",
        "mechanism": "预期价值较高且短期负收益冲击较强时，过度反应修复更可信。",
        "fields": [("est_eps", "分析师预期每股收益"), ("bookvalue_ps", "每股账面价值"), ("returns", "短期收益冲击"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期价值", "required_categories": ["analyst"]}, {"name": "短期反转", "required_categories": ["pv"]}],
        "neutralization": "SUBINDUSTRY",
    },
    {
        "direction_id": "crossover2-analyst-volume-reversal",
        "expression": "group_rank(ts_mean(rank(anl4_afv4_eps_mean / close) * rank(volume / adv20), 63) + ts_rank(-ts_sum(returns, 5), 20), industry)",
        "semantic": "在行业内将替代预期、成交参与度和短期负收益冲击形成条件重估信号。",
        "mechanism": "高成交确认的短期负收益冲击在预期收益率支持下更可能修复。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("volume", "成交量"), ("adv20", "常态成交量"), ("returns", "短期收益冲击"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "成交确认反转", "required_categories": ["pv"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover2-analyst-intraday-reversal",
        "expression": "group_rank(ts_rank(ts_delta(est_eps, 21), 63) + rank(-(close / open - 1)), industry)",
        "semantic": "在行业内结合分析师预期变化与日内负价格压力。",
        "mechanism": "预期增量与日内负冲击共同出现时，估值修复更可能具有信息支持。",
        "fields": [("est_eps", "分析师预期每股收益"), ("close", "收盘价格"), ("open", "开盘价格"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}, {"name": "日内价格反转", "required_categories": ["pv"]}],
        "neutralization": "INDUSTRY",
    },
]

ITERATION_18_SPECS: list[dict[str, Any]] = [
    {
        "direction_id": "crossover3-forecast-profitability-smoothing",
        "expression": "group_rank(ts_mean(rank(est_eps / close) + rank(operating_income / assets), 63), subindustry)",
        "semantic": "在子行业内平滑分析师预期收益率与经营盈利质量。",
        "mechanism": "预期收益率与经营盈利质量共同确认重估，并以子行业中性化降低规模依赖。",
        "fields": [("est_eps", "分析师预期每股收益"), ("close", "价格尺度"), ("operating_income", "经营盈利"), ("assets", "资产规模"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "盈利质量", "required_categories": ["fundamental"]}],
        "neutralization": "SUBINDUSTRY",
    },
    {
        "direction_id": "crossover3-forecast-cash-confirmation",
        "expression": "group_rank(ts_rank(est_eps / close, 126) * rank(cashflow_op / assets), industry)",
        "semantic": "在行业内用经营现金流资产比确认分析师预期收益率。",
        "mechanism": "只有在现金转化质量支持下的预期收益率才更可能形成持续重估。",
        "fields": [("est_eps", "分析师预期每股收益"), ("close", "价格尺度"), ("cashflow_op", "经营现金流"), ("assets", "资产规模"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "现金质量", "required_categories": ["fundamental"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover3-forecast-reversal-shock",
        "expression": "group_rank(ts_rank(ts_delta(est_eps, 21) / close, 63) + rank(-ts_sum(returns, 5)), industry)",
        "semantic": "在行业内结合预期增量与短期负收益冲击。",
        "mechanism": "预期改善与短期负冲击共同出现时，估值修复更可能具有信息支持。",
        "fields": [("est_eps", "分析师预期每股收益"), ("close", "价格尺度"), ("returns", "短期收益冲击"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}, {"name": "短期反转", "required_categories": ["pv"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover3-alternative-forecast-change",
        "expression": "group_rank(ts_mean(rank(anl4_afv4_eps_mean / close) + rank(ts_delta(est_eps, 21) / close), 63), industry)",
        "semantic": "在行业内融合替代预期收益率与一致预期变化。",
        "mechanism": "静态预期收益率与预期增量相互确认，减少单一预期来源依赖。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("est_eps", "分析师预期每股收益"), ("close", "价格尺度"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期水平", "required_categories": ["analyst"]}, {"name": "分析师预期变化", "required_categories": ["analyst"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover3-alternative-intraday-pressure",
        "expression": "group_rank(ts_rank(anl4_afv4_eps_mean / close, 126) * rank(-(close / open - 1)), industry)",
        "semantic": "在行业内用日内负价格压力确认替代预期收益率。",
        "mechanism": "预期收益率与日内负冲击共同出现时，估值修复更可能具有信息支持。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "收盘价格"), ("open", "开盘价格"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "日内反转", "required_categories": ["pv"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover3-alternative-forecast-blend",
        "expression": "group_rank(ts_rank(ts_delta(anl4_afv4_eps_mean, 21) / close, 63) + ts_rank(est_eps / close, 126), subindustry)",
        "semantic": "在子行业内结合替代预期变化与一致预期收益率。",
        "mechanism": "两种分析师信息源的水平与变化共同确认中期重估，并以子行业中性化减轻暴露。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("est_eps", "分析师预期每股收益"), ("close", "价格尺度"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}, {"name": "分析师预期水平", "required_categories": ["analyst"]}],
        "neutralization": "SUBINDUSTRY",
    },
]

ITERATION_20_SPECS: list[dict[str, Any]] = [
    {
        "direction_id": "crossover4-analyst-profitability",
        "expression": "group_rank(ts_mean(rank(anl4_afv4_eps_mean / close) + rank(operating_income / assets), 63), industry)",
        "semantic": "在行业内平滑替代预期收益率与经营盈利质量。",
        "mechanism": "替代预期与盈利质量共同确认中期重估，避免只依赖单一分析师信息源。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("operating_income", "经营盈利"), ("assets", "资产规模"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "盈利质量", "required_categories": ["fundamental"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover4-analyst-cash-intraday",
        "expression": "group_rank(ts_rank(anl4_afv4_eps_mean / close, 126) * rank(cashflow_op / assets) + rank(-(close / open - 1)), industry)",
        "semantic": "在行业内用现金质量与日内负冲击确认替代预期收益率。",
        "mechanism": "预期收益率在现金转化支持且伴随短期负冲击时，估值修复更可信。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "收盘价格"), ("open", "开盘价格"), ("cashflow_op", "经营现金流"), ("assets", "资产规模"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "现金质量", "required_categories": ["fundamental"]}, {"name": "日内反转", "required_categories": ["pv"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover4-analyst-fundamental-shock",
        "expression": "group_rank(ts_rank(ts_delta(anl4_afv4_eps_mean, 21) / close, 63) + rank(operating_income / assets) * rank(-ts_sum(returns, 5)), subindustry)",
        "semantic": "在子行业内结合预期变化、盈利质量与短期负收益冲击。",
        "mechanism": "预期增量与基本面支撑下的短期过度反应更可能发生修复。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("operating_income", "经营盈利"), ("assets", "资产规模"), ("returns", "短期收益冲击"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}, {"name": "盈利质量", "required_categories": ["fundamental"]}, {"name": "短期反转", "required_categories": ["pv"]}],
        "neutralization": "SUBINDUSTRY",
    },
    {
        "direction_id": "crossover4-analyst-volume-reversal",
        "expression": "group_rank(ts_rank(rank(anl4_afv4_eps_mean / close) + rank(-returns), 42) * rank(volume / adv20), industry)",
        "semantic": "在行业内将替代预期与成交确认的短期反转结合。",
        "mechanism": "高成交参与的负收益冲击在预期收益率支持下更可能代表可交易修复。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("returns", "短期收益冲击"), ("volume", "成交量"), ("adv20", "常态成交量"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "成交确认反转", "required_categories": ["pv"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover4-analyst-vwap-pressure",
        "expression": "group_rank(ts_rank(anl4_afv4_eps_mean / close, 126) * rank(-(close - vwap) / vwap) + rank(volume / adv20), industry)",
        "semantic": "在行业内用VWAP压力和成交参与度确认替代预期收益率。",
        "mechanism": "预期价值与成交确认的价格压力共同识别估值修复，而非简单拼接父代表达式。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "收盘价格"), ("vwap", "成交量加权价格"), ("volume", "成交量"), ("adv20", "常态成交量"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "VWAP压力", "required_categories": ["pv"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover4-analyst-return-regime",
        "expression": "group_rank(ts_zscore(anl4_afv4_eps_mean / close, 60) + ts_rank(-ts_sum(returns, 5), 20), subindustry)",
        "semantic": "在子行业内结合替代预期收益率与短期收益状态。",
        "mechanism": "预期收益率在短期负收益状态下更可能反映过度反应后的修复机会。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("returns", "短期收益冲击"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "收益状态", "required_categories": ["pv"]}],
        "neutralization": "SUBINDUSTRY",
    },
]

ITERATION_22_SPECS: list[dict[str, Any]] = [
    {
        "direction_id": "crossover5-forecast-profitability-cash",
        "expression": "group_rank(ts_mean(rank(anl4_afv4_eps_mean / close) * rank(operating_income / assets), 42) + rank(cashflow_op / assets), industry)",
        "semantic": "在行业内以预期收益率与盈利质量的交互，并由现金转化确认。",
        "mechanism": "预期收益率只有在经营盈利和现金转化共同支持时才形成可信重估。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("operating_income", "经营盈利"), ("assets", "资产规模"), ("cashflow_op", "经营现金流"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "盈利与现金质量", "required_categories": ["fundamental"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover5-forecast-change-profitability",
        "expression": "group_rank(ts_rank(ts_delta(anl4_afv4_eps_mean, 21) / close, 63) + ts_mean(rank(operating_income / assets), 63), subindustry)",
        "semantic": "在子行业内结合预期增量与经营盈利的平滑水平。",
        "mechanism": "分析师预期改善在盈利质量锚定下更可能代表持续重估。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("operating_income", "经营盈利"), ("assets", "资产规模"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}, {"name": "盈利质量", "required_categories": ["fundamental"]}],
        "neutralization": "SUBINDUSTRY",
    },
    {
        "direction_id": "crossover5-forecast-cash-level",
        "expression": "group_rank(ts_zscore(anl4_afv4_eps_mean / close, 60) * rank(cashflow_op / assets) + ts_rank(operating_income / assets, 42), industry)",
        "semantic": "在行业内用现金转化确认预期收益率并叠加盈利水平。",
        "mechanism": "现金转化对预期收益率的条件确认与盈利水平共同提供基本面锚。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("cashflow_op", "经营现金流"), ("assets", "资产规模"), ("operating_income", "经营盈利"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "现金与盈利质量", "required_categories": ["fundamental"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover5-forecast-option-skew",
        "expression": "group_rank(ts_mean(rank(anl4_afv4_eps_mean / close) + rank(-implied_volatility_put_30), 42), subindustry)",
        "semantic": "在子行业内结合预期收益率与下行期权风险。",
        "mechanism": "预期收益率在较低下行隐含波动率压力下更可能代表相对重估。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("implied_volatility_put_30", "看跌隐含波动率"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "期权风险", "required_categories": ["option"]}],
        "neutralization": "SUBINDUSTRY",
    },
    {
        "direction_id": "crossover5-forecast-option-change",
        "expression": "group_rank(ts_rank(ts_delta(anl4_afv4_eps_mean, 21) / close, 63) * rank(implied_volatility_call_30 - implied_volatility_put_30), industry)",
        "semantic": "在行业内以期权偏斜确认分析师预期变化。",
        "mechanism": "预期增量与看涨看跌隐含波动率差共同刻画风险偏好驱动的重估。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("implied_volatility_call_30", "看涨隐含波动率"), ("implied_volatility_put_30", "看跌隐含波动率"), ("industry", "行业比较")],
        "claims": [{"name": "分析师预期变化", "required_categories": ["analyst"]}, {"name": "期权偏斜", "required_categories": ["option"]}],
        "neutralization": "INDUSTRY",
    },
    {
        "direction_id": "crossover5-forecast-option-regime",
        "expression": "group_rank(ts_zscore(anl4_afv4_eps_mean / close, 60) - ts_rank(implied_volatility_call_30 + implied_volatility_put_30, 30), subindustry)",
        "semantic": "在子行业内用期权总风险状态调节预期收益率。",
        "mechanism": "预期收益率在整体隐含波动率压力较低时更可能转化为相对收益。",
        "fields": [("anl4_afv4_eps_mean", "替代分析师预期"), ("close", "价格尺度"), ("implied_volatility_call_30", "看涨隐含波动率"), ("implied_volatility_put_30", "看跌隐含波动率"), ("subindustry", "子行业比较")],
        "claims": [{"name": "分析师预期", "required_categories": ["analyst"]}, {"name": "期权波动率状态", "required_categories": ["option"]}],
        "neutralization": "SUBINDUSTRY",
    },
]


def build(task_path: Path, candidates_path: Path, output_path: Path) -> None:
    tasks = json.loads(task_path.read_text(encoding="utf-8"))
    parents: dict[str, dict[str, Any]] = {}
    for line in candidates_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            parents[str(value.get("candidate_id"))] = value
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
        output = materialize_crossovers(
            tasks,
            parents,
            list(parents.values()),
            FieldCatalog(FIELD_PATH),
            active_expressions,
        )
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return
    output = []
    iteration = int(tasks.get("iteration", 0))
    specs = ITERATION_22_SPECS if iteration >= 22 else (ITERATION_20_SPECS if iteration >= 20 else (ITERATION_18_SPECS if iteration >= 18 else SPECS))
    for index, spec in enumerate(specs):
        task = tasks["crossover"][index // 3]
        parent_id = str(task["parents"][0])
        parent = parents[parent_id]
        child = copy.deepcopy(parent)
        for key in ("candidate_id", "validation", "created_at", "iteration"):
            child.pop(key, None)
        child["direction_id"] = spec["direction_id"]
        child["expression"] = spec["expression"]
        child["semantic_description"] = spec["semantic"]
        child["operation"] = "crossover"
        child["parents"] = list(task["parents"])
        child["crossover_task_index"] = index // 3 + 1
        child["settings"] = copy.deepcopy(parent.get("settings", {}))
        child["settings"]["neutralization"] = spec["neutralization"]
        hypothesis = copy.deepcopy(child.get("hypothesis", {}))
        hypothesis["mechanism"] = spec["mechanism"]
        hypothesis["observable_proxies"] = [
            {"field": field, "role": role, "required": True}
            for field, role in spec["fields"]
        ]
        hypothesis["claims"] = spec["claims"]
        child["hypothesis"] = hypothesis
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
