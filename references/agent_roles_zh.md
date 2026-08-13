# QuantaAlpha 逻辑 Agent 职责规范

## 目录

1. 共享输入输出契约
2. Planning Agent
3. Idea Agent
4. Factor Agent
5. Verifier
6. Evaluation Agent
7. Evolution Agent
8. Governance Agent
9. 隔离与交接规则

## 1. 共享输入输出契约

所有角色只通过以下受控对象交接：`run.json`、Planning Packet、Candidate JSON、Evaluation JSON、Iteration Task Packet、Factor Pool 和 Governance Report。禁止依赖未归档的聊天记忆。

任何角色不得修改历史 JSONL。修正必须生成新事件或新候选。所有时间使用 UTC ISO-8601。

## 2. Planning Agent

输入：Region、Universe、Delay、允许类别、Seed、预算和已有 ACTIVE 概况。

输出：互补方向、每个方向的经济机制范围、候选数量、允许周期和禁止重复区域。

质量门槛：覆盖慢/快信号、水平/变化、价格/基本面/预期/另类数据和状态条件。只改窗口不算新方向。

## 3. Idea Agent

输入：一个方向、字段目录、市场先验和既有失败模式。

输出：可证伪机制、方向、周期、可观测代理、失败模式和反例。

质量门槛：每项叙事主张必须能被字段类别观测；禁止使用“机构”“散户”“基本面”等没有数据支持的标签。

## 4. Factor Agent

输入：已批准假设、字段元数据、算子 Allowlist 和复杂度预算。

输出：`semantic_description`、FastExpr、完整 Settings 和实现说明。

质量门槛：最多 3 个实现；优先最简单表达式；VECTOR 先归约；Region/Universe/Delay 与目录一致。

## 5. Verifier

输入：完整 Candidate JSON 和已有候选。

输出：字段、类型、语义、复杂度、恒等式、代数化简、结构冗余和谱系结论。

质量门槛：独立于回测结果。即使表达式收益很高，只要语义不一致也必须拒绝。

## 6. Evaluation Agent

输入：BRAIN Alpha 详情、IS Checks、带日期 PnL、ACTIVE Snapshot 和候选复杂度。

输出：平台指标、日期对齐相关性、固定奖励分项、Submission Blockers 和故障定位。

质量门槛：不得修改奖励权重；不得把缺失指标按成功处理；不得使用隐藏结果。

## 7. Evolution Agent

输入：已评价轨迹和确定性 Mutation/Crossover Task Packet。

输出：带 Parent ID、Operation、冻结段和修改说明的新 Candidate JSON。

Mutation：只修改被定位环节，每个任务生成一个子节点。

Crossover：组合互补机制和代理，不得拼接字符串；子节点必须能独立解释。

## 8. Governance Agent

输入：运行配置、全部候选/评价/事件、因子池和预算。

输出：谱系、Hash、奖励、PnL 日期、冗余、预算、隐藏测试、方向覆盖和隐私审计。

质量门槛：存在 CRITICAL Issue 时禁止提交和经验晋升。

## 9. 隔离与交接规则

- 生成角色不得看到隐藏测试或竞赛分数。
- Verifier 不得因收益高而放宽语义门控。
- Evaluation Agent 不得修改表达式。
- Evolution Agent 不得覆盖父轨迹。
- Governance Agent 只审计，不生成 Alpha。
- 多 Agent 并行时，每个角色使用最小必要上下文；最终由单一 ResearchStore 合并事件。
