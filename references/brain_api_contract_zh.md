# WorldQuant BRAIN 接口契约

## 目录

1. 适用范围
2. 认证与安全
3. 端点与状态
4. PnL Recordset
5. 重试与限流
6. 提交状态机
7. 兼容性验证

## 1. 适用范围

本契约描述 Skill 当前代码所依赖的 BRAIN 行为，不代表 WorldQuant 的官方稳定 API 保证。平台字段、Schema、状态名或端点变化时，先更新私有兼容性测试，再修改公开 Skill。

## 2. 认证与安全

- 从 `WQ_BRAIN_USERNAME` 和 `WQ_BRAIN_PASSWORD` 读取凭据；否则读取被忽略的 `credential.txt`。
- 使用 HTTP Basic Auth 创建 Session，并 `POST /authentication`。
- 认证成功期望 HTTP 201；失败时不得输出密码或完整响应中的敏感信息。
- 禁止提交 Cookie、Token、Session、Credential 或账号关联结果。

## 3. 端点与状态

| 功能 | 方法与端点 | 预期 |
|---|---|---|
| 认证 | `POST /authentication` | 201 |
| 字段目录 | `GET /data-fields` | 分页对象列表 |
| 用户 Alpha | `GET /users/self/alphas` | 分页对象列表 |
| Alpha 详情 | `GET /alphas/{id}` | 指标、状态、Checks |
| PnL | `GET /alphas/{id}/recordsets/pnl` | Schema + Records |
| 模拟 | `POST /simulations` | 201 + Location |
| 模拟轮询 | `GET <Location>` | COMPLETE/FAILED 等状态 |
| 提交 | `POST /alphas/{id}/submit` | 请求受理，不等于 ACTIVE |

Simulation POST 返回不确定结果时禁止自动重发，避免重复创建。轮询必须有总超时。

## 4. PnL Recordset

`schema.properties` 可能是 List 或 Dict；Records 可能为普通 Row 或单层嵌套 Row。解析时：

1. 先展开嵌套 Row。
2. 根据 Schema 定位 Date 和 PnL 列。
3. 转换类型并按日期去重、排序。
4. 将累计 PnL 转为每日差分。
5. 对两个 Alpha 按日期 Inner Join 后计算相关性。
6. 将 HTTP 200 但响应体为空视为瞬时软限流，有限重试并在 ACTIVE 请求之间节流。
7. 刷新失败时保留上次有效私有缓存并标记来源，不得以空数组覆盖。

禁止仅按数组长度对齐，禁止直接计算累计曲线相关性。

## 5. 重试与限流

- GET 的 ConnectionError、Timeout、429、500、502、503、504 允许有限重试。
- 优先读取 `Retry-After` 秒数或 HTTP Date；否则指数退避，上限 30 秒。
- POST 默认只发送一次；不确定时先查询平台状态。
- 默认串行执行，候选间隔 2 秒；达到运行 API 预算立即停止。

## 6. 提交状态机

```text
SIMULATED
  |-- metric/static blocker -> SIMULATED_NOT_ELIGIBLE
  |-- ACTIVE PnL coverage incomplete -> SIMULATED_ELIGIBLE_NOT_SUBMITTED
  |-- abs(ACTIVE daily-PnL correlation) >= 0.70 -> SIMULATED_ELIGIBLE_NOT_SUBMITTED
  `-- explicit submission
        |-- HTTP failure -> SUBMIT_FAILED
        |-- SELF_CORRELATION FAIL -> NOT_ACTIVE_AFTER_SUBMIT
        |-- timeout/review -> NOT_ACTIVE_AFTER_SUBMIT
        `-- status ACTIVE -> ACTIVE
```

必须分别记录 `UNSUBMITTED`、Self-correlation 失败、超时和其他拒绝。禁止把 HTTP 201 记为 ACTIVE。

## 7. 兼容性验证

账户同步兼容原 WQ Skill：`python scripts/evolve_skill.py` 为预览，`--apply` 更新私有 `alpha_db.json`。预览模式不得修改数据库；公开经验只能包含脱敏聚合统计。

真实运行前：

1. 运行 `selftest.py` 验证本地逻辑。
2. 使用一个低风险字段执行 Dry Run。
3. 获得模拟授权后，以一个候选验证认证、Location、轮询、Alpha 详情和 PnL Schema。
4. 不得用兼容性测试候选自动提交。
5. API 变化时保存脱敏错误类型，不保存账号数据。
