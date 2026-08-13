# 本机运行说明

项目目录：`D:\实习工作\因子挖掘\quanta_alpha-mining-main`

当前研究 Run：`qa-batch20-20260803`

## 安全边界

- `credential.txt` 仅保存在本机，并已被 `.gitignore` 排除。
- `private/`、`alpha_db.json` 和批量结果均已被忽略，不应上传。
- 默认命令只做 Dry Run；只有显式加入 `--simulate` 才创建 BRAIN Simulation。
- `--simulate` 默认自动提交 WQ 合格候选；只诊断时必须显式加入 `--no-auto-submit`。
- 自动提交还要求候选与全部 ACTIVE 均可计算至少 50 个对齐日度 PnL 变化，且最大绝对相关性低于 0.70；覆盖不完整时失败关闭。
- BRAIN PnL 端点偶尔以 HTTP 200 空响应实施软限流；程序会重试和节流，不再把空响应保存为有效空 PnL。

## 常用命令

在 PowerShell 中进入项目目录：

```powershell
Set-Location 'D:\实习工作\因子挖掘\quanta_alpha-mining-main'
```

离线自检：

```powershell
python scripts/selftest.py
```

查看当前研究状态：

```powershell
python scripts/evolve_skill.py status --run-id qa-batch20-20260803
```

只读预览账户 Alpha 变化：

```powershell
python scripts/account_sync.py --max-pnl-fetch 50
```

Dry Run（不访问 BRAIN）：

```powershell
python scripts/submit_batch.py --run-id qa-batch20-20260803
```

模拟已登记候选并按默认规则自动提交合格项：

```powershell
python scripts/submit_batch.py --run-id qa-batch20-20260803 --simulate --refresh-active
```

生成下一轮定向 Mutation 任务：

```powershell
python scripts/evolve_skill.py next --run-id qa-batch20-20260803 --phase mutation
```

Mutation 子代登记、模拟并评价完成后，再生成 Crossover 任务：

```powershell
python scripts/evolve_skill.py next --run-id qa-batch20-20260803 --phase crossover
```

治理审计与预算：

```powershell
python scripts/governance.py audit --run-id qa-batch20-20260803
python scripts/governance.py budget --run-id qa-batch20-20260803
```

## 当前兼容性模拟结论

- BRAIN 认证、Simulation 创建、轮询、详情解析均已验证。
- 测试候选 Sharpe 为 1.80，Fitness 为 0.73，Turnover 为 64.09%。
- 因 `LOW_FITNESS` 未通过门控，状态为 `SIMULATED_NOT_SUBMITTED`。
- 下一轮应冻结反转机制和主字段，定向降低换手与路径敏感性。

## 每组 20 个候选

初始化一个干净 Run：

```powershell
python scripts/evolve_skill.py init --run-id <run-id> --directions 10 --iterations 5 --max-iterations 15 --candidates-per-direction 2
```

生成 10 个方向各 2 个候选并批量登记：

```powershell
python scripts/generate_batch20.py --run-id <run-id>
python scripts/evolve_skill.py register-batch --run-id <run-id> --input private/research_runs/<run-id>/initial_batch20.json
```

整组 Dry Run 和真实模拟：

```powershell
python scripts/submit_batch.py --run-id <run-id> --max-candidates 20
python scripts/submit_batch.py --run-id <run-id> --max-candidates 20 --simulate --refresh-active --simulation-timeout 900 --between-candidates 2
```

第一组已完成的 Run 是 `qa-batch20-20260803`。后续组应根据 `iteration_NN_tasks.json` 生成定向变异候选，不应重复运行相同的初始化表达式。

## 后续组：单次修改反馈流程

以下命令保持原来的字段范围和 `14 Mutation + 6 Crossover`。14个Mutation任务各生成一个子代；父代从全部历史选择，不按机制簇、血缘或固定路线比例分配。先刷新ACTIVE快照：

```powershell
$runId = 'qa-batch20-20260803'
python scripts/submit_batch.py --run-id $runId --refresh-active-only
```

生成下一iteration的14张父代反馈卡和14个Mutation子代，先Dry Run，再模拟。将下面的 `<mutation-iteration>` 替换为任务包实际编号：

```powershell
python scripts/evolve_skill.py next --run-id $runId --phase mutation
python scripts/build_mutation_candidates.py --task "private/research_runs/$runId/iteration_<mutation-iteration>_tasks.json" --candidates "private/research_runs/$runId/candidates.jsonl" --output "private/research_runs/$runId/iteration_<mutation-iteration>_mutation_candidates.json"
python scripts/evolve_skill.py register-batch --run-id $runId --input "private/research_runs/$runId/iteration_<mutation-iteration>_mutation_candidates.json"
python scripts/submit_batch.py --run-id $runId --iteration <mutation-iteration> --max-candidates 14
python scripts/submit_batch.py --run-id $runId --iteration <mutation-iteration> --max-candidates 14 --simulate --refresh-active --simulation-timeout 900 --between-candidates 2
```

Mutation全部评价后才生成下一iteration的Crossover。将 `<crossover-iteration>` 替换为实际编号：

```powershell
python scripts/evolve_skill.py next --run-id $runId --phase crossover
python scripts/build_crossover_candidates.py --task "private/research_runs/$runId/iteration_<crossover-iteration>_tasks.json" --candidates "private/research_runs/$runId/candidates.jsonl" --output "private/research_runs/$runId/iteration_<crossover-iteration>_crossover_candidates.json"
python scripts/evolve_skill.py register-batch --run-id $runId --input "private/research_runs/$runId/iteration_<crossover-iteration>_crossover_candidates.json"
python scripts/submit_batch.py --run-id $runId --iteration <crossover-iteration> --max-candidates 6
python scripts/submit_batch.py --run-id $runId --iteration <crossover-iteration> --max-candidates 6 --simulate --refresh-active --simulation-timeout 900 --between-candidates 2
```

Mutation候选会保存具体 `action_id`；Simulation后的 `parent_feedback` 只评价该action。下一组会跳过已使同一父代变差的action，但不会关闭或删除父代。
