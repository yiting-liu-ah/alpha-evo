# QuantaAlpha WQ Research - 中文工作流

将本文件作为完整中文操作规范。代码标识符、JSON 键名、环境变量和 BRAIN 字段 ID 必须保留英文原文。

把 WorldQuant BRAIN 公式因子的每次研究尝试建模为可追溯的完整轨迹。由 AI Agent 负责假设推理，由确定性脚本负责字段验证、复杂度控制、模拟、奖励、谱系、相关性和提交安全。

## 不可违反的规则

1. 将每次回测视为含噪证据，不得视为证明。
2. 记录每个候选与失败，不得只保留赢家。
3. 保持假设、可观测代理、表达式、设置、结果和谱系一致。
4. 只用按日期对齐的累计 PnL 每日变化计算相关性，禁止对累计曲线直接计算；提交前必须覆盖全部 ACTIVE，任一不可比较项均按失败关闭。
5. 隐藏测试、竞赛或提交结果不得进入进化奖励。
6. 解决高相关时必须更换数据来源或经济机制；只调窗口不充分。
7. 禁止在公开 Skill 中保存凭据、Alpha ID、私有表达式、PnL 或账户状态。
8. 只有用户明确授权后才能模拟和提交；本项目已获持续自动提交授权，合格条件由确定性代码执行。
9. 必须确认 `status == ACTIVE`；HTTP 201 只代表请求被受理。
10. 明确披露 BRAIN 无法复现的论文模块，不得声称指标或组合等价。

## 参考资料路由

只读取当前阶段需要的资料：

- 开始或审计完整研究前，阅读 [research_protocol_zh.md](research_protocol_zh.md)。
- 生成候选 JSON 前，阅读 [candidate_schema.json](candidate_schema.json)。Schema 键名保持英文。
- 选择字段、算子、设置或修复表达式时，阅读 [fastexpr_patterns_zh.md](fastexpr_patterns_zh.md)。
- 检查论文覆盖、迁移、消融、收敛、衰减或压力测试时，阅读 [paper_to_brain_mapping_zh.md](paper_to_brain_mapping_zh.md)。
- 搜索 USA TOP3000 Delay 1 字段时，使用 `wq_usa_top3000_delay1_data_fields.json`，先按 `type` 和 `category` 过滤。
- 只有 `validated_lessons.json` 存在已晋升的脱敏经验时才读取它。

## 研究状态

将私有研究保存在 `private/research_runs/<run-id>/`：

```text
run.json                 不可随意改写的政策与当前迭代状态
planning_packet.json     差异化初始化任务包
candidates.jsonl         全部候选及静态门控结果
evaluations.jsonl        模拟、指标、PnL、奖励与相关性
events.jsonl             只追加的审计事件
iteration_NN_tasks.json  变异与交叉任务
factor_pool.json         受控累计因子池
active_snapshot.json     私有 ACTIVE Alpha 指标与 PnL
analysis_report.json     收敛、年度衰减和压力诊断
```

禁止提交 `private/` 目录。

## 强制研究流程

### 1. 明确范围与权限

确认 Region、Universe、Delay、候选预算、迭代预算、允许的数据类别，以及用户是否授权模拟或真实提交。

默认使用 USA TOP3000、Delay 1、10个研究方向、5次迭代；批次模拟后自动提交WQ合格候选。

禁止在对话中索取凭据。使用 `WQ_BRAIN_USERNAME`、`WQ_BRAIN_PASSWORD`，或本地被忽略的 `credential.txt`。

### 2. 初始化差异化规划

运行：

```bash
python scripts/evolve_skill.py init --directions 10 --iterations 5 --max-iterations 15
```

保存返回的 `run_id`。每个方向最多生成 3 个假设。经济机制、信息类别、预测周期和市场状态必须具有实质差异。不得把仅改变窗口的参数网格当作差异化规划。

### 3. 搜索并验证字段

使用结构化命令搜索本地字段目录：

```bash
python scripts/field_catalog.py search operating_income \
  --category fundamental \
  --type MATRIX
```

优先使用覆盖率充足的 MATRIX 字段。VECTOR 字段必须先用经平台验证的向量归约算子处理。GROUP 字段只能作为分组输入。

当 Region、Universe 或 Delay 与内置快照不一致时，从 BRAIN 同步新的私有目录：

```bash
python scripts/field_catalog.py sync \
  --region EUR \
  --universe TOP2500 \
  --delay 1
```

禁止静默复用不兼容的字段元数据。

### 4. 建立候选契约

按照 `candidate_schema.json` 创建一个 JSON 对象，必须包含：

- 可以被证伪的经济机制；
- 预期方向和预测周期；
- 每个可观测代理及其经济角色；
- 有相应数据类别支持的叙事主张；
- 已知失败模式；
- 简洁的语义描述；
- FastExpr 和完整 BRAIN 设置；
- `initialization`、`mutation` 或 `crossover` 操作类型及父节点。

登记候选：

```bash
python scripts/evolve_skill.py register \
  --run-id <run-id> \
  --candidate <candidate.json>
```

禁止模拟未通过静态门控的候选。

### 5. 执行因子实现门控

同时满足以下条件：

- 表达式不超过 250 个字符、6 个字段、12 层括号深度；
- 数值自由参数比例低于 0.50；
- 不含未知字段或算子；
- 字段类型使用正确；
- 表达式中的每个字段均登记为可观测代理；
- 每个必需代理均出现在表达式中；
- 每个叙事主张均由正确的字段类别支持；
- 与已有候选的结构相似度低于 0.90；
- 不含自相关恒等式、可直接约掉的代数伪复杂度或错误谱系。

将 BRAIN 编译视为实现检查。最多允许两次不改变假设的实现修复。修复预算用尽后归档轨迹。

### 6. 在访问 API 前执行 Dry Run

对全部已登记候选执行静态验证：

```bash
python scripts/submit_batch.py --run-id <run-id>
```

检查每个拒绝原因，只修复被定位的局部环节。

### 7. 模拟与评价

获得明确模拟授权后运行：

```bash
python scripts/submit_batch.py \
  --run-id <run-id> \
  --simulate \
  --refresh-active
```

执行器必须：

1. 完成认证且不打印凭据；
2. 刷新 ACTIVE Alpha 和带日期索引的 PnL；
3. 模拟每个通过门控的表达式；
4. 收集顶层grade、Sharpe、Fitness、Returns、Turnover、Drawdown、Margin、多空数量和IS Checks；
5. 计算候选与 ACTIVE Alpha 的按日期对齐日度 PnL 相关性；
6. 计算固定轨迹奖励及其分项；
7. 将 HTTP 200 空 PnL 响应视为瞬时限流并重试、节流；不得静默保存空数组；
8. 仅对Average/Good/Excellent/Spectacular、无FAIL、全部ACTIVE可比较且最大绝对相关性低于0.70的候选自动提交；PENDING允许服务器解析；
9. 将全部结果及相关性/覆盖阻断、ACTIVE成功、拒绝分类写入私有研究运行。

禁止用 LLM 临时生成的评分替代确定性奖励。

### 8. 对轨迹执行变异与交叉

生成下一次迭代任务：

```bash
python scripts/evolve_skill.py next --run-id <run-id>
```

初始多样化规划只执行一次。后续每组20次固定为 `14 Mutation → 评价 → 6 Crossover`。14个Mutation任务各选择一个父代、各生成一个子代，不设置12/2等路线配额。先运行 `next --phase mutation`，完成子代评价后再运行 `next --phase crossover`。

执行Crossover时，从已评价轨迹组合一个连贯的经济机制，不得按机制簇或血缘分配名额，也不得拼接表达式字符串。最终提交和因子池门槛不变。

Mutation父代从全部历史已评价的非ACTIVE候选中按记录奖励直接排序，不限于最近一组，不使用机制簇、血缘、失败距离或使用次数配额。每个任务必须包含父代真实失败、本次唯一修改和过去 `action_id` 结果。候选生成器必须读取反馈卡，禁止按iteration选择预写公式，也不得重复已经使同一父代变差的action。Simulation后保存改善、恶化或混合；该结论只评价本次修改，绝不能关闭或淘汰父代。

重复模拟与进化。默认在第 5 次迭代停止；只有最佳累计奖励和因子池新颖性仍在改善时才延长，且不得超过 15 次。

### 9. 构建因子池

运行：

```bash
python scripts/evolve_skill.py pool --run-id <run-id>
```

只接纳同时通过静态门控和指标门控的候选。按轨迹奖励降序处理。候选与每个已入池成员的绝对 PnL 相关性必须低于 0.70，结构相似度必须低于 0.90。

因子池默认最多接纳合格候选的 50%，且不超过 150 个成员。

评价候选对组合的边际价值，而不只看单因子 Sharpe。检查研究方向、数据类别、字段、周期和中性化方式的集中度。

### 10. 分析衰减、状态、压力与收敛

运行常规诊断：

```bash
python scripts/analyze_run.py --run-id <run-id>
```

需要压力期时，预先指定窗口：

```bash
python scripts/analyze_run.py \
  --run-id <run-id> \
  --stress-start 2025-04-01 \
  --stress-end 2025-04-30
```

报告年度表现、正收益日占比、以 PnL 单位表示的回撤，以及每次迭代的最佳和平均奖励。禁止把 PnL 单位统计写成组合收益率。

执行跨 Universe 或跨 Region 迁移时，先冻结表达式，再验证目标字段，只修改必要设置，并逐项披露适配内容。存在重新拟合或表达式修改时，禁止称为 Zero-shot。

### 11. 自动提交WQ合格候选

自动提交必须同时满足：静态门控已通过；WQ顶层grade为Average/Good/Excellent/Spectacular；IS Checks已返回且没有FAIL；候选与动态参考集均有至少50个对齐日度PnL变化；最大绝对相关性低于0.70。动态参考集由批次开始时的最新ACTIVE、因子池独有成员和同批新ACTIVE组成；每次ACTIVE成功后立即更新，Mutation评价后重建因子池再进入Crossover。PENDING不能豁免相关性门槛。任一参考PnL不可用或对齐不足时失败关闭；相关性达到阈值时禁止提交。结构冗余不替代实际PnL检查。

### 12. 安全晋升研究经验

预览聚合经验：

```bash
python scripts/evolve_skill.py promote --run-id <run-id>
```

人工审阅后，仅追加脱敏聚合结果：

```bash
python scripts/evolve_skill.py promote --run-id <run-id> --apply
```

禁止把原始 Alpha 记录追加到本文件。只有多次独立运行重复支持的规律才能晋升；同时记录样本量和反例。

## 变异决策表

| 失败类型 | 冻结 | 修改 |
|---|---|---|
| 语法、单位、算子 | 假设、代理 | 表达式实现 |
| 权重集中 | 机制、代理 | 回填、排序、缩尾、截断 |
| 高换手、低 Fitness | 机制、主字段 | 周期、Decay、交易条件、实现方式 |
| 低子样本 Sharpe | 研究方向 | 市值/流动性依赖、中性化 |
| 低 Sharpe | 数据可用性契约 | 机制、方向、周期、代理 |
| 高 ACTIVE 相关 | 市场上下文 | 数据类别、机制、代理、表达式 |
| 质量较好但风险高 | 已验证机制 | 状态控制、互补信息 |

## 机构审查清单

- 核对字段的时点含义、覆盖率、类型、Region、Universe 和 Delay。
- 执行代数化简并拒绝恒等式。
- 区分 BRAIN 提交门槛与生产投资标准。
- 记录搜索预算和多重检验风险。
- 在独立运行之间比较消融结果，不得只比较一条轨迹。
- 检查换手、Margin、集中度、子样本表现、衰减和压力窗口。
- 在资本配置前补充外部交易成本和容量分析。
- 保存从假设到最终 ACTIVE 状态的完整审计谱系。

## 离线验证

使用 Python 3.10+ 和 `requests`，所有其他运行依赖均来自标准库。

使用凭据前运行：

```bash
python scripts/selftest.py
```

Self-test 通过只代表软件逻辑验证成功，不代表 Alpha 有效，也不代表当前 BRAIN API 一定兼容。
