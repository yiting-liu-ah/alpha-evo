# FastExpr Construction Reference

## Contents

1. Field-type routing
2. Mechanism-first patterns
3. Settings policy
4. Anti-patterns
5. Repair order

## 1. Field-type routing

Inspect `type`, `category`, `coverage`, `dataset`, and description before using a field.

- MATRIX: use directly with cross-sectional and time-series operators.
- VECTOR: reduce with a platform-verified vector operator before ranking or time-series operations.
- GROUP: use as grouping input, not as an alpha value.
- SYMBOL/UNIVERSE: do not treat as numeric fields.

Prefer coverage above 0.50. Permit 0.20-0.50 only with an explicit missingness hypothesis and tested backfill. Reject coverage below 0.20 by default.

Search JSON with exact type filters. Do not infer field meaning from its ID alone.

## 2. Mechanism-first patterns

Use these as structural examples, not fixed alpha recommendations.

### Slow level within peers

```fastexpr
group_rank(ts_rank(operating_income / equity, 126), subindustry)
```

Risks: negative/small equity, stepwise filings, missingness, profitability crowding.

### Fundamental change

```fastexpr
group_rank(ts_rank(ts_delta(operating_income / assets, 63), 126), subindustry)
```

Require point-in-time availability and verify whether the apparent change reflects reporting cadence.

### Analyst revision

```fastexpr
group_rank(ts_rank(ts_delta(est_eps, 21) / close, 63), industry)
```

Verify estimate horizon and units. Use decay only after observing turnover.

### Cash-flow quality

```fastexpr
group_rank(ts_rank(cashflow_op / assets, 126), subindustry)
```

Do not call a ratio a yield unless the denominator is a market value with the intended economic interpretation.

### Price-pressure reversal

```fastexpr
group_rank(ts_rank(-(close / open - 1), 5), industry)
```

Treat this as a high-turnover seed. Mutation should add a distinct participation or regime proxy, not merely increase decay.

### Conditional composite

```fastexpr
group_rank(ts_rank(operating_income / assets, 126), subindustry) * rank(-ts_std_dev(returns, 20))
```

The condition must have an economic role and incremental evidence. Multiplication can unintentionally reverse signs; state the expected interaction.

## 3. Settings policy

Start from:

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

Use the minimum necessary change. Record settings as part of the trajectory because neutralization, decay, truncation, and NaN handling materially alter the alpha.

## 4. Anti-patterns

- Unsupported stories: do not label OHLCV-only expressions as institutional ownership, retail attention, or fundamentals.
- Tautologies: reject self-correlations such as `ts_corr(returns, returns, 20)`.
- Algebraic camouflage: simplify `operating_income / sales * sales / assets` to `operating_income / assets`.
- Parameter spray: do not register many window-only variants as diversified hypotheses.
- Hidden size/liquidity bets: investigate low sub-universe Sharpe and field coverage.
- Unbounded ratios: protect denominators through economically justified ranking, winsorization, or verified platform behavior.
- Narrative crossover: do not combine two parent stories unless the child expression contains proxies for both.

## 5. Repair order

1. Verify field existence, type, region, universe, and delay.
2. Verify operator name, signature, and named parameters.
3. Verify units and denominator behavior.
4. Verify missingness and concentration.
5. Repair expression without changing the hypothesis.
6. After two implementation failures, archive the trajectory and start a new realization.
