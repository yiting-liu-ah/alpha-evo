# 反馈驱动的20次因子挖掘 Cycle

## 固定顺序

后续每组固定执行：

`14 Mutation → 完成评价 → 6 Crossover`

Crossover 必须等待14个Mutation子代完成登记、Simulation和评价，不能提前生成。

## Mutation的唯一反馈原则

父代从全部历史已评价的非 ACTIVE 候选中选择，不限于上一组。父代按已记录的轨迹奖励直接排序，不再设置机制簇配额、血缘上限、失败距离、选择档位、父代使用次数或12/2等路线配额。

每个Mutation任务只生成一个子代，并执行：

1. 读取父代真实的IS失败、指标和相关性结果。
2. 选择一个明确修改，不同时改多个原因。
3. 读取该父代过去子代的 `action_id` 和结果。
4. 不重复已经使同一父代变差的具体 action。
5. Simulation后只判断本次action是改善、恶化还是混合。

一次子代变差只说明本次修改失败。不得删除、关闭、永久降格或停止使用父代；以后可以对同一父代尝试不同修改。

## 失败原因与单次修改

| 失败原因 | 单次只选择一种修改 |
|---|---|
| LOW_SHARPE | 字段、窗口或分组 |
| LOW_FITNESS | 先判断换手还是收益弱，再修一个原因 |
| LOW_TURNOVER | 缩短窗口或换活跃代理 |
| HIGH_TURNOVER | Decay、周期或Trade Condition |
| CONCENTRATED_WEIGHT | Backfill、Rank或Truncation |
| LOW_SUB_UNIVERSE_SHARPE | 分组、中性化或流动性依赖 |
| SELF_CORRELATION / ACTIVE相关性≥0.70 | 一个相关信号腿、一个代理或一个有效状态过滤 |
| HIGH_DRAWDOWN | 一个风险控制或状态条件 |

高相关不得自动升级为全面更换机制，也不得只调整窗口、权重、Decay或Neutralization。修改失败后保留父代，下一次换另一种去相关方法。

## 任务与历史

未来Cycle必须设置 `feedback_driven_generation=true` 和 `feedback_generation_version=2`。禁止按iteration编号读取预写公式。

反馈卡至少保存：

- 父代ID和真实失败原因；
- 本次必须保留和唯一修改；
- 过去尝试及其 `action_id`；
- 已经使该父代变差的 `failed_action_ids`；
- “结果只评价action，不淘汰父代”的解释。

若生成器找不到未重复且能通过静态门控的修改，应报告该任务无法生成，不得用无关公式填满预算，也不得因此宣布父代无用。

## 运行命令

```bash
python scripts/evolve_skill.py next --run-id <run-id> --phase mutation
# 生成、登记并评价14个一父一子的Mutation候选
python scripts/evolve_skill.py next --run-id <run-id> --phase crossover
# Mutation评价完成后再生成6个Crossover候选
```

每轮报告Mutation与Crossover的模拟数、指标结果、WQ grade、ACTIVE成功数，以及每个mutation action相对父代的Sharpe、Fitness、Turnover和失败项变化。
