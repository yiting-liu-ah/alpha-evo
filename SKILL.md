---
name: quantaalpha-wq-research
description: "Use for enterprise-grade WorldQuant BRAIN alpha research driven by QuantaAlpha trajectory evolution: diversified hypothesis planning, typed field search, FastExpr construction, semantic/complexity/redundancy verification, BRAIN simulation and IS diagnosis, deterministic trajectory rewards, fixed mutation-then-crossover cycles, grade-aware automatic submission, governed factor pools, ACTIVE-alpha daily-PnL correlation control, robustness analysis, research-budget auditing, and sanitized experience evolution. Also use for 中文 requests about QuantaAlpha、WorldQuant BRAIN、WQ Alpha、AI因子挖掘、因子表达式、轨迹进化、回测诊断、IS Summary、Average、Good、Sharpe、Fitness、Self-correlation、变异、交叉、因子池、自动提交或可审计量化投研."
---

# QuantaAlpha WQ 企业级因子研究 Skill

> 结构化 Playbook：研究规划 → 可证伪假设 → 可观测代理 → FastExpr → 一致性/复杂度/冗余门控 → BRAIN 模拟 → 轨迹评价 → 定向变异/互补交叉 → 因子池 → 稳健性审计 → 受控提交 → 脱敏经验进化。

本 Skill 将 QuantaAlpha 论文的轨迹级自进化思想映射到 WorldQuant BRAIN 公式 Alpha 接口。AI Agent 负责研究推理，确定性脚本负责字段、表达式、评分、谱系、相关性、预算和权限控制。不得把单次高 Sharpe 当作可交易结论。

英文请求必须完整阅读 [workflow_en.md](references/workflow_en.md)。论文观点到实现的逐项映射见 [quantaalpha_coverage_matrix.md](references/quantaalpha_coverage_matrix.md)。

---

## 1. 快速决策树

```text
开始
  ├── 明确权限
  │    ├── 只设计/审计 ──→ 不访问 BRAIN
  │    ├── 仅设计/审计 ──→ 不创建 Simulation
  │    └── 执行批次 ─────→ 模拟后按 WQ grade/IS Tests 自动提交
  ├── 明确市场契约
  │    ├── USA TOP3000 Delay 1 ──→ 使用内置 4,367 字段目录
  │    └── 其他 Region/Universe/Delay ──→ 先同步私有字段目录
  ├── 先同步账户记忆，读取已验证经验与 ACTIVE 避免清单
  ├── 初始化 10 个互补研究方向
  ├── 每个方向生成最多 3 个结构化候选
  │    ├── 字段/类型无效 ────────→ 拒绝
  │    ├── 叙事无可观测代理 ────→ 拒绝
  │    ├── 复杂度/恒等式失败 ───→ 化简或局部修复
  │    ├── 结构重复 ─────────────→ 更换机制或数据类别
  │    └── 保留 ACTIVE 全部核心字段 → 拒绝薄包装，重新选代理
  ├── Dry Run 全部通过后模拟
  ├── 读取顶层 grade、Sharpe/Fitness/TO/DD/Margin/IS Checks/PnL
  │    ├── 实现错误 ───────→ 冻结假设，只修代码，最多 2 次
  │    ├── 高换手/低 Fitness → 冻结机制，修改周期/Decay/实现
  │    ├── 低 Sharpe ───────→ 从字段、窗口或分组三者中只试一种修复
  │    ├── 高相关 ──────────→ 只做一次明确的信号腿、代理或状态过滤修改
  │    ├── grade < Average ───→ 不提交，保留为可再次尝试的 Mutation 父代
  │    ├── grade ≥ Average 且有 FAIL → 不提交，优先故障定位 Mutation
  │    └── grade ≥ Average 且无 FAIL → PENDING 可放行，自动尝试提交
  ├── 默认 5 次迭代；无改进连续 3 次则停止；上限 15 次
  ├── 构建低结构重复、低日度 PnL 相关的因子池
  ├── 执行年度衰减、压力期、消融、迁移与治理审计
  └── 提交后确认 status == ACTIVE；否则记录明确终态
```

## 2. Skill 架构与职责

### 2.1 逻辑 Agent 角色

| 角色 | 输入 | 输出 | 禁止事项 |
|---|---|---|---|
| Planning Agent | 市场契约、Seed、字段类别 | 互补研究方向 | 参数网格冒充多样性 |
| Idea Agent | 方向、市场观测、金融先验 | 可证伪假设 | 使用无数据支持的故事 |
| Factor Agent | 假设、字段目录、算子库 | 语义说明、FastExpr、设置 | 自由生成未知字段/算子 |
| Verifier | 假设、代理、表达式、Schema | 一致性与复杂度结论 | 用回测收益替代语义检查 |
| Evaluation Agent | BRAIN 结果、ACTIVE PnL | 指标、奖励、故障定位 | 修改预先定义的奖励 |
| Evolution Agent | 已评价轨迹、冻结/修改段 | Mutation/Crossover 子任务 | 丢失谱系或机械拼接表达式 |
| Governance Agent | 全部事件、预算、因子池 | 审计、消融、迁移报告 | 使用隐藏测试指导进化 |

这些是逻辑职责。可以由一个 Agent 按阶段执行，也可以由多个隔离 Agent 执行；无论实现方式如何，都必须使用相同 Schema 和确定性门控。

### 2.2 文件结构

```text
SKILL.md                              中文主 Playbook
references/workflow_en.md             完整英文 Playbook
references/candidate_schema.json      候选数据契约
references/quantaalpha_coverage_matrix.md 论文全观点覆盖矩阵
references/*_zh.md / *.md             中英文专业参考
scripts/field_catalog.py              字段搜索与目录同步
scripts/evolve_skill.py               规划、登记、变异、交叉、建池、经验晋升
scripts/feedback_generation.py        按父代反馈卡生成子代并检查修改是否落实
scripts/submit_batch.py               静态检查、模拟、受控提交
scripts/analyze_run.py                衰减、压力、收敛分析
scripts/governance.py                 谱系审计、消融、冻结迁移、预算报告
scripts/selftest.py                   离线验证
private/research_runs/<run-id>/       私有研究状态，禁止提交
alpha_db.json                         WQ 兼容的私有账户快照，禁止提交
```

## 3. 字段速查与类型治理

内置字段目录覆盖 USA TOP3000、Delay 1，共 4,367 个字段：

| 类别 | 数量 | 典型用途 |
|---|---:|---|
| fundamental | 1,652 | 财务报表、附注、盈利质量、投资效率 |
| analyst | 1,324 | 一致预期、修正、目标价与预测变化 |
| news | 996 | 新闻、事件、信息扩散与注意力 |
| pv | 195 | 价格、成交量、VWAP、波动率与分组字段 |
| option | 138 | 隐含波动率、偏度、Put/Call 信息 |
| model | 40 | 平台模型字段 |
| socialmedia | 22 | 社交媒体关注与情绪 |

字段类型包括 2,828 个 MATRIX、1,387 个 VECTOR、142 个 GROUP、4 个 SYMBOL 和 6 个 UNIVERSE。禁止忽略类型直接套用表达式。

### 3.1 本地搜索

```bash
python scripts/field_catalog.py search operating_income \
  --category fundamental \
  --type MATRIX \
  --limit 10
```

优先检查：`id`、`description`、`type`、`category`、`dataset`、`coverage`、`alphaCount` 和 `userCount`。高 `alphaCount` 表明常用，不代表具有低拥挤度。

### 3.2 类型规则

| 类型 | 允许用法 | 禁止用法 |
|---|---|---|
| MATRIX | 截面、时序、分组算子 | 无 |
| VECTOR | 先经已验证 `vec_*` 归约 | 直接 `rank(vector_field)` |
| GROUP | `group_rank` 等的 Group 参数 | 作为 Alpha 数值 |
| SYMBOL/UNIVERSE | 平台元信息 | 数值运算 |

覆盖率优先高于 0.50；0.20-0.50 必须提出缺失机制并测试 Backfill；低于 0.20 默认拒绝。

### 3.3 重新同步字段

更换 Region、Universe、Delay 或发现平台字段更新时运行：

```bash
python scripts/field_catalog.py sync \
  --region EUR \
  --universe TOP2500 \
  --delay 1
```

新目录默认写入 `private/catalogs/`，不得静默覆盖公开基准快照。

## 4. 算子、符号表示与可控因子实现

### 4.1 算子速查

| 类型 | 代表算子 | 研究用途 |
|---|---|---|
| 截面 | `rank`, `zscore`, `normalize`, `winsorize` | 同日股票间比较与极值控制 |
| 时序 | `ts_mean`, `ts_std_dev`, `ts_delta`, `ts_rank`, `ts_corr`, `ts_backfill` | 单只股票历史状态与变化 |
| 分组 | `group_rank`, `group_neutralize`, `group_zscore`, `group_backfill` | 行业/子行业内比较和风险控制 |
| 条件 | `if_else`, `trade_when` | 状态触发与换手控制 |
| 向量 | `vec_avg`, `vec_sum` | VECTOR 字段归约；签名必须经平台验证 |

### 4.2 中间表示

将候选拆成：

`Hypothesis h → Semantic Description d → FastExpr f → Token/Structure T(f) → BRAIN Simulation c`

Token 结构承担论文 AST 的 BRAIN 适配职责：提取字段、算子、数值参数、括号深度、结构 n-gram 和字段集合。BRAIN Simulation 承担最终编译检查。

### 4.3 一致性门控

同时验证：

1. `h ↔ d ↔ f`：每个表达式字段均有代理角色，每个必需代理均进入表达式。
2. `f ↔ c`：实际提交给 BRAIN 的 FastExpr 必须与存档表达式完全相同。
3. Narrative ↔ Data：机构、散户、分析师、期权、新闻、社媒或基本面主张必须有相应类别字段。
4. Settings ↔ Catalog：Region、Universe、Delay 与字段元数据必须一致。

### 4.4 复杂度与冗余门控

默认约束：

- 字符数 ≤ 250；基础字段 ≤ 6；括号深度 ≤ 12；自由参数比例 < 0.50。
- 禁止 `ts_corr(returns, returns, 20)` 等恒等式。
- 禁止 `A / B * B / C` 等可直接约掉的代数伪复杂度。
- 结构相似度 < 0.90。
- 与 ACTIVE Alpha 或池内成员的绝对日度 PnL 相关性 < 0.70。
- 当 ACTIVE PnL 暂不可用时，启用保守替代门控：若候选保留某个 ACTIVE 表达式至少 80% 的核心信号字段，且结构相似度至少 0.35，视为 `ACTIVE_EXPRESSION_REDUNDANCY`。GROUP/SYMBOL/UNIVERSE 字段不计入核心信号字段。该规则用于阻止“已提交主干 + 一个装饰字段”的薄包装，不替代最终 PnL 相关检查。

结构相似度使用抽象 Token n-gram 与字段 Jaccard 的加权值，避免论文未归一化公共子树规模对长表达式的偏置。

## 5. 差异化规划与假设模板

### 5.1 十个初始研究方向

| 方向 | 核心机制 | 典型周期 |
|---|---|---|
| profitability-quality | 盈利质量持续性与低估 | 63/126/252 |
| fundamental-change | 经营变化的增量信息 | 21/63/126 |
| cashflow-accrual | 现金转化与应计质量 | 126/252 |
| valuation | 基本面或预期收益率重估 | 126/252 |
| analyst-revision | 预期修正信息缓慢扩散 | 21/63/126 |
| investment-efficiency | 资本配置与资产效率 | 126/252 |
| price-volume-microstructure | 价格压力、反转/延续与参与度 | 2/5/10/20 |
| volatility-option | 波动状态和期权隐含信息 | 5/20/60 |
| news-sentiment | 事件、关注与情绪扩散 | 2/5/20 |
| regime-conditioned-composite | 慢信号与独立快速状态代理结合 | 5/20/126 |

### 5.2 候选假设契约

每个候选必须包含：机制、预期方向、预期周期、可观测代理、代理角色、叙事所需类别、失败模式、语义说明、表达式、完整设置、Operation 和 Parents。

参考 [example_candidate_zh.json](references/example_candidate_zh.json)，并使用 [candidate_schema.json](references/candidate_schema.json) 的英文键名。

### 5.3 结构示例

```fastexpr
group_rank(ts_rank(operating_income / equity, 126), subindustry)
group_rank(ts_rank(ts_delta(est_eps, 21) / close, 63), industry)
group_rank(ts_rank(cashflow_op / assets, 126), subindustry)
group_rank(ts_rank(-(close / open - 1), 5), industry)
group_rank(ts_rank(operating_income / assets, 126), subindustry) * rank(-ts_std_dev(returns, 20))
```

这些是机制模板，不是保证有效的 Alpha。必须重新验证字段含义、时点性、单位、覆盖率、拥挤和方向。

### 5.4 默认设置

| 因子类型 | Decay 起点 | Neutralization | nanHandling | 风险重点 |
|---|---:|---|---|---|
| 慢速基本面 | 0-4 | SUBINDUSTRY | ON | 阶梯数据、负分母、拥挤 |
| 分析师修正 | 0-4 | INDUSTRY/SUBINDUSTRY | ON | 预测口径、修正频率 |
| 技术/微观结构 | 10-30 | INDUSTRY | OFF/按字段 | 高换手、状态依赖 |
| 情绪/新闻 | 4-10 | INDUSTRY | ON | 稀疏、覆盖率、事件聚集 |
| 复合/状态因子 | 4-20 | INDUSTRY/SUBINDUSTRY | ON | 符号翻转、伪互补 |

## 6. 指标、门控与轨迹奖励

### 6.1 BRAIN 核心指标

| 指标 | 含义 | 默认门槛/偏好 |
|---|---|---|
| Sharpe | 平台风险调整收益 | 最低 1.25，偏好 ≥ 1.5 |
| Fitness | Sharpe、Returns、Turnover 的平台综合指标 | 最低 1.0，偏好 ≥ 1.1 |
| Returns | BRAIN 平台年化收益口径 | 结合 Margin/风险解释 |
| Turnover | 每日交易额 / Book Size | 允许 1%-70%，偏好 ≤ 20% |
| Drawdown | 峰谷损失 | 默认绝对值 < 20%，偏好 < 15% |
| Margin | PnL / 总交易额 | 越高越好 |

### 6.2 IS Checks

| 检查 | 失败含义 | 首要动作 |
|---|---|---|
| LOW_SHARPE | 信号强度不足 | 从字段、窗口、分组中只改一项 |
| LOW_FITNESS | 可能是换手高，也可能是收益弱 | 先识别原因，再只改一项；不得默认继续平滑 |
| LOW_TURNOVER | 信号过慢 | 缩短周期或换更活跃代理，只选一项 |
| HIGH_TURNOVER | 信号过快 | Decay、周期、Trade Condition 只选一项 |
| CONCENTRATED_WEIGHT | 稀疏、极值或缺失 | Rank、Backfill、Winsorize、Truncation |
| LOW_SUB_UNIVERSE_SHARPE | 小盘/流动性依赖 | 分组、中性化、流动性依赖只修一项 |
| SELF_CORRELATION | 与已有 Alpha 重复 | 改一个相关信号腿、代理或有效状态过滤；不得只调参数 |

### 6.3 固定奖励

使用：

`R(τ) = 0.30 Sharpe + 0.25 Fitness + 0.15 Returns + 0.10 Novelty - 0.08 Drawdown - 0.07 Turnover - 0.05 Complexity - Failed-Gate Penalty`

所有分项按代码中的固定阈值缩放与截断，保存完整分解。Novelty 优先使用 ACTIVE 日度 PnL 相关性；未提交候选没有 PnL 时，必须退化为 AST/字段结构新颖性，禁止无条件记满分。LLM 无权在看到结果后改变奖励。

## 7. 故障定位、Mutation 与 Crossover

| 故障 | 冻结 | 修改 |
|---|---|---|
| 语法/单位/算子 | 假设、代理、方向 | 表达式实现 |
| 权重集中 | 经济机制、主代理 | 缺失处理、Rank、Truncation |
| 高换手/低 Fitness | 机制、主字段 | 周期、Decay、Trade Condition |
| 低子样本 Sharpe | 研究方向 | 市值/流动性依赖、中性化 |
| 低 Sharpe | 数据可用性契约 | 机制、方向、周期、代理 |
| 高相关 | 市场上下文 | 数据类别、机制、代理、表达式 |
| 收益提高但风险恶化 | 已验证机制 | 状态控制与风险结构 |

WQ 平台资格、研究治理资格与进化父代资格必须分离。WQ 平台资格要求顶层 `grade ∈ {AVERAGE, GOOD, EXCELLENT, SPECTACULAR}`、IS Tests 不含 `FAIL` 且 Checks 已返回；`PENDING` 可由服务器解析。自动提交还必须通过动态研究治理硬门槛：批次开始刷新全部 ACTIVE，并合并当前因子池中尚未 ACTIVE 的成员；候选与每个参考成员都必须有至少 50 个对齐日度 PnL 变化，且最大绝对相关性 < 0.70。每个新 ACTIVE 必须立即加入同批后续候选的参考集；Mutation 阶段结束后重建因子池，再生成 Crossover。任一参考 PnL 不可用、对齐不足或相关性 ≥ 0.70 时禁止提交。只有最终 `status == ACTIVE` 才算成功。

Mutation 排除 ACTIVE，父代从全部历史已评价的非 ACTIVE 轨迹中按已记录奖励直接排序；不再使用机制簇配额、血缘上限、失败距离、选择档位或父代使用次数决定资格。父代可以在以后再次被选中，一次子代变差不得删除、关闭或降格父代。

每个 Mutation 任务只生成一个子代，并附带机器可读反馈卡：`真实失败原因 / 本次保留内容 / 本次唯一修改 / 已失败 action_id`。生成器必须读取反馈卡，禁止按 iteration 读取预写公式，也不得重复已使同一父代变差的具体 action。Simulation 后把改善、恶化或混合写回该 action；结论只评价本次修改，不评价父代是否有用。

高相关不会自动把局部修复升级成全面更换机制。指标合格但相关性过高时，保留父代已有的有效证据，只选择一个相关信号腿、一个代理或一个有实际含义的状态过滤进行修改；若子代变差，父代仍保留，可换另一种修改继续验证。Crossover 同样不使用机制簇/血缘硬配额，最终仍接受静态门控与实际 PnL 相关性检查。

论文案例中的 Institutional Momentum 作为反面测试：只有价量字段时，禁止解释为机构持仓/散户关注；没有波动字段时，禁止声称动态波动加权；子节点不得早于父节点；风险恶化且结论为 Rejected 时不得称为成功。

## 8. BRAIN 自动化执行

### 8.1 凭据

优先设置：

```bash
export WQ_BRAIN_USERNAME="..."
export WQ_BRAIN_PASSWORD="..."
```

也可在 Skill 根目录创建被忽略的 `credential.txt`：

```json
["username", "password"]
```

禁止提交凭据、Cookie、Session、Alpha 数据库或私有结果。

### 8.2 初始化、登记和 Dry Run

WQ 原项目兼容接口采用两层记忆：`alpha_db.json` 保存账户级私有基线与增量事件，`references/validated_lessons.json` 只保存达到最小重复证据的脱敏机制规律。首次运行建立全量基线；后续只重点处理新增、状态/指标变化和消失记录。

```bash
# 预览账户 Alpha、指标变化和 ACTIVE 日度 PnL 高相关对，不写文件
python scripts/account_sync.py

# 每个新 Cycle 前执行；人工审阅后更新私有 alpha_db.json；默认至少 3 个重复观测才晋升公共经验
python scripts/account_sync.py --apply

# 提高公共经验的证据门槛
python scripts/account_sync.py --apply --min-public-support 5

# 自动选择最新 Run，执行安全 Dry Run；不访问 BRAIN、不提交
python scripts/submit_batch.py
```

完整 QuantaAlpha 轨迹接口：

```bash
python scripts/evolve_skill.py init --directions 10 --iterations 5 --max-iterations 15
python scripts/evolve_skill.py register --run-id <run-id> --candidate <candidate.json>
python scripts/submit_batch.py --run-id <run-id>
```

### 8.3 模拟

```bash
python scripts/submit_batch.py --run-id <run-id> --simulate --refresh-active
```

执行器分页拉取 ACTIVE Alpha，以日期对齐累计 PnL 后先差分为每日 PnL，再计算相关；不同日期长度不得按数组位置硬对齐。PnL 端点出现 HTTP 200 空响应时按瞬时限流重试并在 ACTIVE 之间节流，不得把空响应解释为零 PnL；刷新失败时只能保留上次有效缓存并标记来源。记录顶层 `grade`、全部指标、Checks、奖励、错误、PnL 覆盖和 API 预算。默认单线程，候选间隔 2 秒；GET 遇空响应、429/5xx执行有限重试，Simulation POST 和 Submission POST 均不在不确定状态下自动重发。`--simulate` 只有在 WQ 平台资格和 ACTIVE 相关性治理同时通过时才自动提交；仅诊断时显式加 `--no-auto-submit`。

### 8.4 下一次进化

初始多样化规划只执行一次。后续每组 20 次固定分为 `14 Mutation → 评价 → 6 Crossover`，禁止预生成 Crossover。14个Mutation任务各选择一个父代、各生成一个子代；不设12/2等路线配额，也不按机制簇或血缘分配名额。Crossover必须等待本轮Mutation完成评价。

```bash
# 先刷新 ACTIVE 表达式与 PnL，避免用过期记忆生成薄包装
python scripts/submit_batch.py --run-id <run-id> --refresh-active-only

# 生成14张父代反馈卡并据此生成子代；登记、模拟并评价后再做Crossover
python scripts/evolve_skill.py next --run-id <run-id> --phase mutation
python scripts/build_mutation_candidates.py --task private/research_runs/<run-id>/iteration_NN_tasks.json --candidates private/research_runs/<run-id>/candidates.jsonl --output private/research_runs/<run-id>/iteration_NN_mutation_candidates.json
python scripts/evolve_skill.py next --run-id <run-id> --phase crossover
python scripts/build_crossover_candidates.py --task private/research_runs/<run-id>/iteration_MM_tasks.json --candidates private/research_runs/<run-id>/candidates.jsonl --output private/research_runs/<run-id>/iteration_MM_crossover_candidates.json
```

Mutation任务的 `expression_budget` 固定为1。Crossover仍遵守阶段总预算。详细流程见 [efficient_search_zh.md](references/efficient_search_zh.md)。

### 8.5 自动提交

批次执行已获用户持续授权：每次 Simulation 后，程序先检查 `Average/Good/Excellent/Spectacular + 无 FAIL`，再检查候选对动态参考集（最新 ACTIVE、因子池独有成员和同批新 ACTIVE）的 PnL 覆盖完整且绝对相关性 < 0.70；两层均通过才调用提交接口。`PENDING` 允许服务器解析，但不能豁免相关性或覆盖门槛。提交后再次拉取 Alpha，只有 `ACTIVE` 才算成功，并立即更新同批参考集。HTTP 200/201、等级合格或提交请求已受理都不得单独记为成功。

对历史已模拟但尚未提交的合格Alpha，不重跑Simulation：

```bash
python scripts/submit_batch.py --run-id <run-id> --submit-existing
```

## 9. 因子池与相关性治理

```bash
python scripts/evolve_skill.py pool --run-id <run-id>
```

规则：通过静态与指标门控 → 全部 IS Checks 为 `PASS`（或已确认 `ACTIVE`）→ 排除 ACTIVE 薄包装 → 按奖励降序 → 逐个检查结构相似度 < 0.90 → 检查池内和 ACTIVE 绝对日度 PnL 相关性 < 0.70 → 最多保留合格候选的 50% 和 150 个成员。指标合格但 `SELF_CORRELATION=PENDING` 的候选保留在评价记录中，不进入最终因子池。

相关性判断：

| abs(corr) | 解释 | 动作 |
|---:|---|---|
| < 0.30 | 较强分散潜力 | 继续审查经济暴露 |
| 0.30-0.50 | 可接受的同市场相关 | 结合奖励与类别集中度 |
| 0.50-0.70 | 中高相关 | 谨慎；优先机制差异 |
| ≥ 0.70 | 重复风险 | 不提交；记录后尝试一个明确的去相关修改 |

禁止使用累计 PnL 相关性。结构冗余只能用于候选生成、故障诊断和 PnL 暂缺时的保守筛选，不能替代提交前对全部 ACTIVE 的实际 PnL 相关检查。禁止以更高 Sharpe 为由自动豁免高相关提交。

## 10. 非平稳性、压力、迁移与消融

### 10.1 年度衰减与压力期

```bash
python scripts/analyze_run.py --run-id <run-id>
python scripts/analyze_run.py --run-id <run-id> \
  --stress-start 2025-04-01 --stress-end 2025-04-30
```

报告年度 PnL 变化、正收益日占比、PnL 单位回撤和迭代收敛。PnL 单位不是收益率。关注隔夜/新闻、波动结构、趋势质量、流动性重估、反转/衰竭等机制在不同状态下的相对表现。

### 10.2 消融实验

```bash
python scripts/governance.py ablation-plan \
  --base-run-id <run-id> --prefix <experiment> --seeds 3 --create-runs
```

创建 Full、No Planning、No Mutation、No Crossover、No Semantic、No Complexity、No Redundancy 七组同预算运行。固定 Prompt 版本、候选预算、迭代预算、指标政策和隐藏测试规则。差异小于跨 Seed 波动时禁止作因果结论。

### 10.3 冻结迁移

```bash
python scripts/governance.py transfer-plan \
  --source-run-id <source> --target-run-id <target> \
  --target-catalog <catalog.json> \
  --region EUR --universe TOP2500 --delay 1
```

查看目标结果前冻结源假设与表达式。若字段、表达式或权重在目标市场重新优化，禁止称为 Zero-shot。

### 10.4 交易成本与容量

BRAIN 公式接口无法复现论文的 TopkDropout 和明确买卖成本。使用 Turnover 与 Margin 作为平台代理，但资本配置前必须补充外部成本、滑点、容量、拥挤和成交限制分析。

## 11. 企业治理、预算与审计

```bash
python scripts/governance.py audit --run-id <run-id>
python scripts/governance.py budget --run-id <run-id>
```

审计必须验证：候选 Hash、谱系父节点数量、父子时间顺序、静态门控可重算、奖励可重算、PnL 日期完整性、因子池成员资格、池内冗余、规划方向覆盖、API 预算和隐藏测试隔离。

默认预算：初始化每方向最多3个候选；后续每20次固定为 `14 Mutation → 评价 → 6 Crossover`。每个Mutation任务只生成1个子代；每次实现最多修复2次、最多2,000次API请求、单运行最长24小时。达到预算必须停止并记录 `budget_stop`。

## 12. 提交前 Checklist

- [ ] 已明确 Region、Universe、Delay、预算和权限
- [ ] 已保存全部候选和失败
- [ ] 字段存在、类型正确、覆盖率可接受
- [ ] 假设、代理、表达式和设置语义一致
- [ ] 不含恒等式、代数伪复杂度或错误谱系
- [ ] 顶层 grade 为 Average/Good/Excellent/Spectacular
- [ ] IS Checks 已返回且不存在 FAIL；PENDING 已标记为服务器待解析
- [ ] Sharpe ≥ 1.25，Fitness ≥ 1.0，Turnover 在允许范围
- [ ] 已与全部 ACTIVE Alpha 按日期对齐计算每日 PnL 相关
- [ ] ACTIVE PnL 覆盖完整；任一空响应、缓存缺失或对齐不足均已阻止提交
- [ ] 与 ACTIVE 和因子池成员绝对相关性 < 0.70
- [ ] 已完成年度衰减、压力期和集中度检查
- [ ] 已运行 `governance.py audit` 且结果为 PASS
- [ ] 已评估多重检验、成本、容量与外部可交易性
- [ ] 提交后再次确认 `status == ACTIVE`

---

## 13. 核心经验

1. 先定义机制和可观测代理，再写表达式。
2. 多样性来自数据来源与经济逻辑，不来自窗口变化。
3. 相关性必须基于按日期对齐的每日 PnL 变化。
4. Mutation 先定位真实故障，每次只改一项；子代结果只评价这次修改，不决定父代生死。
5. 近门槛轨迹可用于进化，但不能因此绕过最终提交门槛。
6. Crossover 复用父代的有效决策，不拼接代码，也不使用机制簇或血缘配额。
7. 复杂表达式默认需要更强证据；能够化简时必须化简。
8. 收益提高但 Drawdown/IR 恶化时，结论可能仍是拒绝。
9. 因子池关注边际组合价值，不只关注单因子 Sharpe。
10. 第 5、11 或 12 次迭代都不是天然最优，必须用收敛证据停止。
11. HTTP 201 不等于 ACTIVE；隐藏测试结果不得进入进化。

---

## 14. 经验进化与实证记录

完成批量模拟、状态变化、消融、迁移或压力审计后，账户级接口维护完整私有快照，`promote` 只晋升至少 3 个同类观测支持的脱敏规则。下一轮规划和进化任务会自动读取这些已晋升规则，但运行模型本身不会因使用次数自动更新参数；未执行账户同步、未晋升或证据不足的结果不会自动变成通用经验。单例、冲突结果、精确表达式、ID、PnL 和状态不得进入公共经验；隐藏测试不得指导进化。详细协议见 [research_protocol_zh.md](references/research_protocol_zh.md)。

```bash
python scripts/evolve_skill.py promote --run-id <run-id>
python scripts/evolve_skill.py promote --run-id <run-id> --apply
```

---

## 15. 深入参考与离线验证

- 完整研究协议：[research_protocol_zh.md](references/research_protocol_zh.md)
- 高效 20 次 Cycle：[efficient_search_zh.md](references/efficient_search_zh.md)
- 论文逐项映射：[paper_to_brain_mapping_zh.md](references/paper_to_brain_mapping_zh.md)
- FastExpr 规范：[fastexpr_patterns_zh.md](references/fastexpr_patterns_zh.md)
- 多代理职责：[agent_roles_zh.md](references/agent_roles_zh.md)
- 企业控制标准：[enterprise_controls_zh.md](references/enterprise_controls_zh.md)
- BRAIN 接口契约：[brain_api_contract_zh.md](references/brain_api_contract_zh.md)

使用 Python 3.10+ 和 `requests`。使用凭据前运行：

```bash
python scripts/selftest.py
```

Self-test 通过仅代表软件逻辑可用，不代表 Alpha 有效或当前 BRAIN API 一定兼容。
