#!/usr/bin/env python3
"""Generate one reproducible 20-candidate initialization batch."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from brain_client import default_settings


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_RUN_ROOT = SKILL_DIR / "private" / "research_runs"


def candidate(
    direction: str,
    mechanism: str,
    horizon: int,
    sign: str,
    proxies: list[tuple[str, str]],
    categories: list[str],
    semantic: str,
    expression: str,
    specific_failure: str,
    **setting_overrides: Any,
) -> dict[str, Any]:
    settings = default_settings()
    settings.update(setting_overrides)
    return {
        "direction_id": direction,
        "hypothesis": {
            "mechanism": mechanism,
            "expected_horizon": horizon,
            "expected_sign": sign,
            "observable_proxies": [
                {"field": field, "role": role, "required": True}
                for field, role in proxies
            ],
            "claims": [
                {"name": f"{direction} observable mechanism", "required_categories": categories}
            ],
            "failure_modes": [
                specific_failure,
                "字段缺失或更新频率可能造成权重集中",
                "市场状态切换可能使该机制阶段性失效",
            ],
        },
        "semantic_description": semantic,
        "expression": expression,
        "settings": settings,
        "operation": "initialization",
        "parents": [],
    }


def build_candidates() -> list[dict[str, Any]]:
    return [
        candidate(
            "profitability-quality",
            "资产创造经营利润的持续能力会被市场缓慢定价，并预测同类公司的相对表现。",
            126,
            "positive",
            [("operating_income", "经营利润分子"), ("assets", "总资产规模分母"), ("subindustry", "同类公司分组")],
            ["fundamental"],
            "计算经营利润资产比的126日时序排名，再进行子行业内排名。",
            "group_rank(ts_rank(operating_income / assets, 126), subindustry)",
            "资产与经营利润的财报时点不同可能产生阶梯信号",
            decay=4,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "profitability-quality",
            "较高的经营现金流销售比反映利润兑现质量，并可能获得行业内持续溢价。",
            126,
            "positive",
            [("cashflow_op", "经营现金流分子"), ("sales", "销售规模分母"), ("industry", "行业内比较分组")],
            ["fundamental"],
            "计算经营现金流销售比的126日时序排名，再在行业内排名。",
            "group_rank(ts_rank(cashflow_op / sales, 126), industry)",
            "销售接近零或现金流异常会放大比率",
            decay=4,
            neutralization="INDUSTRY",
        ),
        candidate(
            "fundamental-change",
            "销售增长的持续改善包含尚未完全进入价格的经营增量信息。",
            126,
            "positive",
            [("sales_growth", "季度销售增长代理"), ("subindustry", "同类公司分组")],
            ["fundamental"],
            "提取销售增长63日变化，并对其126日时序排名后进行子行业排名。",
            "group_rank(ts_rank(ts_delta(sales_growth, 63), 126), subindustry)",
            "季度数据更新可能使63日变化集中在少数报告日",
            decay=4,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "fundamental-change",
            "资产标准化后的经营利润改善会比静态盈利水平提供更及时的增量信息。",
            126,
            "positive",
            [("operating_income", "经营利润"), ("assets", "规模标准化分母"), ("industry", "行业分组")],
            ["fundamental"],
            "计算经营利润资产比的63日变化，再取126日时序排名和行业排名。",
            "group_rank(ts_rank(ts_delta(operating_income / assets, 63), 126), industry)",
            "利润改善可能只是一次性会计项目",
            decay=4,
            neutralization="INDUSTRY",
        ),
        candidate(
            "cashflow-accrual",
            "经营现金流相对经营利润越强，盈利兑现质量越高且未来表现更稳健。",
            126,
            "positive",
            [("cashflow_op", "现金兑现分子"), ("operating_income", "应计盈利参照"), ("subindustry", "子行业分组")],
            ["fundamental"],
            "对经营现金流与经营利润之比做126日时序排名和子行业排名。",
            "group_rank(ts_rank(cashflow_op / operating_income, 126), subindustry)",
            "经营利润为负或接近零时比率不稳定",
            decay=4,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "cashflow-accrual",
            "现金流超过经营利润的资产标准化差额反映较低应计依赖和更高盈利质量。",
            252,
            "positive",
            [("cashflow_op", "现金流"), ("operating_income", "会计利润"), ("assets", "资产标准化分母"), ("industry", "行业分组")],
            ["fundamental"],
            "计算现金流减经营利润的资产比，进行252日时序排名和行业排名。",
            "group_rank(ts_rank((cashflow_op - operating_income) / assets, 252), industry)",
            "现金流与利润口径差异可能引入非经营噪声",
            decay=4,
            neutralization="INDUSTRY",
        ),
        candidate(
            "valuation",
            "分析师预期每股收益相对股价形成的预测收益率会驱动中长期相对重估。",
            126,
            "positive",
            [("est_eps", "预期每股收益"), ("close", "股价分母"), ("subindustry", "子行业分组")],
            ["analyst"],
            "计算预期每股收益价格比的126日时序排名，再在子行业内排名。",
            "group_rank(ts_rank(est_eps / close, 126), subindustry)",
            "亏损公司负预期收益会改变收益率解释",
            decay=4,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "valuation",
            "每股销售额相对股价的高水平可能代表行业内较低的销售估值。",
            252,
            "positive",
            [("sales_ps", "每股销售额"), ("close", "股价分母"), ("industry", "行业分组")],
            ["fundamental"],
            "计算每股销售额价格比的252日时序排名，再进行行业排名。",
            "group_rank(ts_rank(sales_ps / close, 252), industry)",
            "低利润率行业中的销售估值可能缺乏可比性",
            decay=4,
            neutralization="INDUSTRY",
        ),
        candidate(
            "analyst-revision",
            "每股收益预期上调的信息会缓慢扩散，并带来中期价格延续。",
            63,
            "positive",
            [("est_eps", "分析师平均每股收益预期"), ("close", "价格尺度"), ("industry", "行业分组")],
            ["analyst"],
            "将21日预期收益变化除以股价，做63日时序排名和行业排名。",
            "group_rank(ts_rank(ts_delta(est_eps, 21) / close, 63), industry)",
            "拆股或预测口径变化可能造成虚假修正",
            decay=4,
            neutralization="INDUSTRY",
        ),
        candidate(
            "analyst-revision",
            "覆盖公司销售预测的分析师数量上升反映新增关注，并可能带来信息扩散。",
            63,
            "positive",
            [("sales_estimate_count", "销售预测覆盖数量"), ("subindustry", "子行业分组")],
            ["analyst"],
            "提取销售预测数量21日变化，进行63日时序排名和子行业排名。",
            "group_rank(ts_rank(ts_delta(sales_estimate_count, 21), 63), subindustry)",
            "覆盖数量上升可能集中在事件期并伴随反向选择",
            decay=4,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "investment-efficiency",
            "较高的资产周转率反映资本使用效率，并可能预测更好的经营结果。",
            126,
            "positive",
            [("sales", "资产产生的销售额"), ("assets", "投入资产规模"), ("subindustry", "子行业分组")],
            ["fundamental"],
            "计算销售资产比的126日时序排名，再进行子行业排名。",
            "group_rank(ts_rank(sales / assets, 126), subindustry)",
            "轻资产与重资产商业模式仍可能无法完全可比",
            decay=4,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "investment-efficiency",
            "较低的资本开支资产比可能代表更克制的资本配置和更高自由现金流潜力。",
            252,
            "negative",
            [("capex", "资本开支"), ("assets", "资产规模"), ("industry", "行业分组")],
            ["fundamental"],
            "对负资本开支资产比做252日时序排名，再进行行业排名。",
            "group_rank(ts_rank(-capex / assets, 252), industry)",
            "成长公司必要投资可能被错误惩罚",
            decay=4,
            neutralization="INDUSTRY",
        ),
        candidate(
            "price-volume-microstructure",
            "短期收益冲击可能过度反应，并在行业内出现数日均值回归。",
            5,
            "negative",
            [("returns", "日收益冲击"), ("industry", "行业分组")],
            ["pv"],
            "对负日收益做5日时序排名，再在行业内排名。",
            "group_rank(ts_rank(-returns, 5), industry)",
            "趋势状态下短期反转可能持续亏损",
            decay=20,
            neutralization="INDUSTRY",
            nanHandling="OFF",
        ),
        candidate(
            "price-volume-microstructure",
            "由异常成交参与确认的短期收益延续比无量价格变化更可能持续。",
            5,
            "positive",
            [("returns", "短期方向"), ("volume", "交易参与度"), ("subindustry", "子行业分组")],
            ["pv"],
            "将5日收益排名与相对20日均量排名结合，再进行子行业排名。",
            "group_rank(ts_rank(returns, 5) * rank(volume / ts_mean(volume, 20)), subindustry)",
            "事件性放量可能代表价格衰竭而非延续",
            decay=10,
            neutralization="SUBINDUSTRY",
            nanHandling="OFF",
        ),
        candidate(
            "volatility-option",
            "较低的20日期权看跌看涨持仓比反映较少下行对冲需求，并可能预示相对强势。",
            20,
            "negative",
            [("pcr_oi_20", "短期限看跌看涨持仓比"), ("industry", "行业分组")],
            ["option"],
            "对负20日期权持仓比做20日时序排名和行业排名。",
            "group_rank(ts_rank(-pcr_oi_20, 20), industry)",
            "期权覆盖集中于大盘高流动性股票",
            decay=8,
            neutralization="INDUSTRY",
        ),
        candidate(
            "volatility-option",
            "中短期限看跌看涨持仓比的期限差在低实现波动状态中更可能包含方向信息。",
            20,
            "conditional",
            [("pcr_oi_60", "中期限期权定位"), ("pcr_oi_20", "短期限期权定位"), ("returns", "实现波动来源"), ("subindustry", "子行业分组")],
            ["option", "pv"],
            "对子期限持仓比差做20日排名，并以低20日收益波动排名调节。",
            "group_rank(ts_rank(pcr_oi_60 - pcr_oi_20, 20), subindustry) * rank(-ts_std_dev(returns, 20))",
            "期限差可能主要反映合约流动性差异",
            decay=12,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "news-sentiment",
            "新闻综合情绪冲击会缓慢扩散，并预测行业内短期相对表现。",
            5,
            "positive",
            [("mean_composite_sentiment_score", "新闻综合情绪"), ("industry", "行业分组")],
            ["news"],
            "对新闻综合情绪做5日时序排名，再进行行业排名。",
            "group_rank(ts_rank(mean_composite_sentiment_score, 5), industry)",
            "新闻聚集可能导致信号在事件后快速衰减",
            decay=6,
            neutralization="INDUSTRY",
        ),
        candidate(
            "news-sentiment",
            "高社交媒体参与确认的情绪信号更可能代表可持续的投资者关注。",
            5,
            "conditional",
            [("snt_social_value", "社交情绪强度"), ("snt_social_volume", "社交讨论量"), ("subindustry", "子行业分组")],
            ["socialmedia"],
            "将社交情绪与讨论量排名结合，做5日时序排名和子行业排名。",
            "group_rank(ts_rank(snt_social_value * rank(snt_social_volume), 5), subindustry)",
            "社交讨论量可能受机器人或非投资事件干扰",
            decay=8,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "regime-conditioned-composite",
            "经营盈利质量在低实现波动状态中更容易稳定兑现为中期相对收益。",
            126,
            "conditional",
            [("operating_income", "慢速盈利质量分子"), ("assets", "规模分母"), ("returns", "快速波动状态"), ("subindustry", "子行业分组")],
            ["fundamental", "pv"],
            "将经营利润资产比的慢速排名与低20日波动状态排名相乘。",
            "group_rank(ts_rank(operating_income / assets, 126), subindustry) * rank(-ts_std_dev(returns, 20))",
            "低波动条件可能隐含防御性行业暴露",
            decay=8,
            neutralization="SUBINDUSTRY",
        ),
        candidate(
            "regime-conditioned-composite",
            "分析师预测收益率在正面新闻状态中更可能得到催化并触发中期重估。",
            126,
            "conditional",
            [("est_eps", "慢速分析师收益预期"), ("close", "价格尺度"), ("mean_composite_sentiment_score", "快速新闻状态"), ("industry", "行业分组")],
            ["analyst", "news"],
            "将预期每股收益价格比的慢速排名与5日新闻情绪均值排名结合。",
            "group_rank(ts_rank(est_eps / close, 126), industry) * rank(ts_mean(mean_composite_sentiment_score, 5))",
            "新闻状态可能只是对同期价格变化的滞后反映",
            decay=10,
            neutralization="INDUSTRY",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a governed 20-candidate batch")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument("--output")
    args = parser.parse_args()
    run_path = Path(args.run_root).expanduser().resolve() / args.run_id
    if not (run_path / "run.json").exists():
        raise FileNotFoundError(f"run not found: {args.run_id}")
    values = build_candidates()
    counts = Counter(item["direction_id"] for item in values)
    if len(values) != 20 or len(counts) != 10 or set(counts.values()) != {2}:
        raise ValueError(f"invalid batch composition: total={len(values)}, directions={counts}")
    output = Path(args.output).expanduser().resolve() if args.output else run_path / "initial_batch20.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"run_id": args.run_id, "candidates": values}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "total": len(values), "directions": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
