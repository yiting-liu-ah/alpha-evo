# FastExpr 构造规范

## 目录

1. 字段类型路由
2. 机制优先的表达式模式
3. 设置政策
4. 反模式
5. 修复顺序

## 1. 字段类型路由

使用字段前检查 `type`、`category`、`coverage`、`dataset` 和描述。

- MATRIX：可直接用于截面和时序算子。
- VECTOR：先用平台已验证的向量算子归约，再执行排序或时序运算。
- GROUP：只作为分组输入，不得作为 Alpha 数值。
- SYMBOL/UNIVERSE：不得当作数值字段。

优先选择覆盖率高于 0.50 的字段。覆盖率 0.20-0.50 时，必须提出明确的缺失机制假设并测试回填。默认拒绝覆盖率低于 0.20 的字段。

使用精确类型过滤搜索 JSON。禁止只根据字段 ID 推断经济含义。

## 2. 机制优先的表达式模式

以下内容仅作为结构示例，不是固定 Alpha 推荐。

### 同类公司中的慢速水平信号

```fastexpr
group_rank(ts_rank(operating_income / equity, 126), subindustry)
```

风险：负值或极小 Equity、阶梯式财报、缺失值和盈利质量拥挤。

### 基本面变化

```fastexpr
group_rank(ts_rank(ts_delta(operating_income / assets, 63), 126), subindustry)
```

必须验证时点可用性，并判断表面变化是否只是财务报告频率造成。

### 分析师修正

```fastexpr
group_rank(ts_rank(ts_delta(est_eps, 21) / close, 63), industry)
```

验证预测口径和单位。只有观察到高换手后再引入 Decay。

### 现金流质量

```fastexpr
group_rank(ts_rank(cashflow_op / assets, 126), subindustry)
```

除非分母是符合经济定义的市场价值，否则禁止把比率称为 Yield。

### 价格压力反转

```fastexpr
group_rank(ts_rank(-(close / open - 1), 5), industry)
```

将其视为高换手 Seed。变异应加入不同的参与度或状态代理，不得只增加 Decay。

### 条件复合信号

```fastexpr
group_rank(ts_rank(operating_income / assets, 126), subindustry) * rank(-ts_std_dev(returns, 20))
```

条件变量必须有经济角色和增量证据。乘法可能意外反转符号，必须声明预期交互方向。

## 3. 设置政策

从以下设置开始：

```json
{
  "instrumentType": "EQUITY",
  "region": "USA",
  "universe": "TOP3000",
  "delay": 1,
  "decay": 4,
  "neutralization": "SUBINDUSTRY",
  "truncation": 0.08,
  "pasteurization": "ON",
  "unitHandling": "VERIFY",
  "nanHandling": "ON",
  "language": "FASTEXPR",
  "visualization": false
}
```

只执行必要的最小变化。把设置作为轨迹的一部分保存，因为 Neutralization、Decay、Truncation 和 NaN 处理都会实质改变 Alpha。

## 4. 反模式

- 无数据支持的故事：禁止把纯 OHLCV 表达式解释为机构持仓、散户关注或基本面。
- 恒等式：拒绝 `ts_corr(returns, returns, 20)` 等自相关项。
- 代数伪装：将 `operating_income / sales * sales / assets` 化简为 `operating_income / assets`。
- 参数喷射：禁止把大量只改窗口的版本登记为差异化假设。
- 隐藏市值/流动性暴露：调查低子样本 Sharpe 和字段覆盖率。
- 无界比率：通过具有经济依据的排序、缩尾或平台行为验证保护分母。
- 叙事性交叉：除非子表达式包含两个父假设的代理，否则禁止声称完成交叉。

## 5. 修复顺序

1. 验证字段存在性、类型、Region、Universe 和 Delay。
2. 验证算子名称、签名和命名参数。
3. 验证单位和分母行为。
4. 验证缺失值和权重集中。
5. 在不修改假设的情况下修复表达式。
6. 两次实现失败后归档轨迹，并重新设计实现。
