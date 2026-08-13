# QuantaAlpha WQ Enterprise Alpha Research Skill

> Structured playbook: research planning -> falsifiable hypothesis -> observable proxies -> FastExpr -> consistency/complexity/redundancy gates -> BRAIN simulation -> trajectory evaluation -> targeted mutation/complementary crossover -> factor pool -> robustness audit -> guarded submission -> sanitized experience evolution.

Use this as the complete English workflow. Keep code identifiers, JSON keys, environment variables, and BRAIN field IDs unchanged. The Chinese `SKILL.md` is the canonical UI entry; both language versions must call the same scripts and schemas.

## 1. Quick Decision Tree

```text
Start
  |-- Establish authority
  |     |-- Design/audit only -> do not access BRAIN
  |     |-- Design/audit only -> do not simulate
  |     `-- Execute batch -> simulate and auto-submit WQ-eligible candidates
  |-- Establish market contract
  |     |-- USA TOP3000 Delay 1 -> use bundled 4,367-field catalog
  |     `-- Other region/universe/delay -> sync a private catalog first
  |-- Initialize ten complementary research directions
  |-- Generate at most three structured candidates per direction
  |     |-- Invalid field/type -> reject
  |     |-- Narrative lacks observable proxy -> reject
  |     |-- Complexity/identity failure -> simplify or repair locally
  |     `-- Structural duplicate -> change mechanism or data category
  |-- Simulate only after every dry-run gate passes
  |-- Read top-level grade, Sharpe/Fitness/TO/DD/Margin/IS Checks/PnL
  |     |-- Implementation failure -> freeze hypothesis; repair code at most twice
  |     |-- High turnover/low Fitness -> freeze mechanism; revise horizon/decay/realization
  |     |-- Low Sharpe -> mechanism-level mutation
  |     |-- High correlation -> change source data or economic logic
  |     `-- Qualified -> consider crossover and factor-pool admission
  |-- Default to five iterations; stop after three stale rounds; maximum fifteen
  |-- Build a structurally novel, low-daily-PnL-correlation factor pool
  |-- Run decay, stress, ablation, transfer, budget, and governance audits
  `-- Confirm status == ACTIVE after submission
```

## 2. Architecture and Responsibilities

### 2.1 Logical Agent Roles

| Role | Input | Output | Prohibited behavior |
|---|---|---|---|
| Planning Agent | market contract, seeds, field categories | complementary directions | presenting parameter grids as diversity |
| Idea Agent | direction, observations, financial priors | falsifiable hypothesis | stories unsupported by available data |
| Factor Agent | hypothesis, catalog, operators | semantics, FastExpr, settings | inventing fields or operators |
| Verifier | hypothesis, proxies, expression, schema | gate decision | using backtest return as semantic proof |
| Evaluation Agent | BRAIN result, ACTIVE PnL | metrics, reward, fault localization | changing the reward after seeing outcomes |
| Evolution Agent | evaluated trajectories, freeze/revise contract | mutation/crossover tasks | losing lineage or concatenating expressions |
| Governance Agent | events, budget, pool | audit, ablation, transfer reports | using hidden tests to guide evolution |

These are logical responsibilities. One agent may execute them sequentially, or isolated agents may execute them separately, but every role must use the same schema and deterministic controls.

### 2.2 Files

```text
SKILL.md                                  Chinese primary playbook
references/workflow_en.md                 complete English playbook
references/candidate_schema.json          candidate contract
references/quantaalpha_coverage_matrix.md paper coverage matrix
references/*_zh.md / *.md                 bilingual professional references
scripts/field_catalog.py                  typed search and catalog sync
scripts/evolve_skill.py                   planning, registration, evolution, pool, lessons
scripts/submit_batch.py                   validation, simulation, guarded submission
scripts/analyze_run.py                    decay, stress, convergence
scripts/governance.py                     lineage audit, ablation, transfer, budget
scripts/selftest.py                       offline verification
private/research_runs/<run-id>/           private state; never commit
alpha_db.json                             WQ-compatible private account snapshot
```

## 3. Field Lookup and Type Governance

The bundled catalog contains 4,367 USA TOP3000 Delay 1 fields:

| Category | Count | Typical use |
|---|---:|---|
| fundamental | 1,652 | statements, footnotes, quality, investment efficiency |
| analyst | 1,324 | consensus, revisions, targets, forecast changes |
| news | 996 | events, diffusion, attention |
| pv | 195 | price, volume, VWAP, volatility, groups |
| option | 138 | implied volatility, skew, put/call information |
| model | 40 | platform model fields |
| socialmedia | 22 | attention and sentiment |

Types include 2,828 MATRIX, 1,387 VECTOR, 142 GROUP, 4 SYMBOL, and 6 UNIVERSE fields. Never ignore field type.

### 3.1 Search

```bash
python scripts/field_catalog.py search operating_income \
  --category fundamental --type MATRIX --limit 10
```

Inspect `id`, description, type, category, dataset, coverage, alphaCount, and userCount. High alphaCount indicates usage, not low crowding.

### 3.2 Type Rules

| Type | Allowed | Prohibited |
|---|---|---|
| MATRIX | cross-sectional, time-series, group operators | none |
| VECTOR | verified vector reduction first | direct `rank(vector_field)` |
| GROUP | group argument | numeric alpha value |
| SYMBOL/UNIVERSE | platform metadata | numeric operations |

Prefer coverage above 0.50. Require a missingness hypothesis and tested backfill for 0.20-0.50. Reject below 0.20 by default.

### 3.3 Sync a New Catalog

```bash
python scripts/field_catalog.py sync --region EUR --universe TOP2500 --delay 1
```

Write new catalogs under `private/catalogs/`. Never silently overwrite the public baseline.

## 4. Operators, Symbolic Form, and Controlled Realization

### 4.1 Operator Guide

| Type | Operators | Purpose |
|---|---|---|
| Cross-sectional | `rank`, `zscore`, `normalize`, `winsorize` | same-day comparison and outlier control |
| Time-series | `ts_mean`, `ts_std_dev`, `ts_delta`, `ts_rank`, `ts_corr`, `ts_backfill` | historical state and change |
| Group | `group_rank`, `group_neutralize`, `group_zscore`, `group_backfill` | peer comparison and risk control |
| Conditional | `if_else`, `trade_when` | regime triggers and turnover control |
| Vector | `vec_avg`, `vec_sum` | VECTOR reduction; verify current signatures |

### 4.2 Intermediate Representation

Use:

`Hypothesis h -> Semantic Description d -> FastExpr f -> Token/Structure T(f) -> BRAIN Simulation c`

The token structure is the BRAIN adaptation of the paper's AST: fields, operators, parameters, depth, structural n-grams, and field sets. BRAIN Simulation provides the final compilation check.

### 4.3 Consistency Gates

Verify all four relationships:

1. `h <-> d <-> f`: every expression field has a proxy role; every required proxy is used.
2. `f <-> c`: the archived expression equals the submitted FastExpr.
3. Narrative <-> Data: institutional, retail, analyst, option, news, social, or fundamental claims have corresponding categories.
4. Settings <-> Catalog: region, universe, and delay agree with metadata.

### 4.4 Complexity and Redundancy

- At most 250 characters, 6 fields, depth 12, and parameter ratio below 0.50.
- Reject identities such as `ts_corr(returns, returns, 20)`.
- Reject algebraic camouflage such as `A / B * B / C` before simplification.
- Require structural similarity below 0.90.
- Require absolute daily-PnL correlation below 0.70 to ACTIVE and pool members.

Use normalized abstract-token n-grams plus field Jaccard instead of the paper's length-biased raw common-subtree size.

## 5. Diversified Planning and Hypothesis Templates

### 5.1 Ten Initial Directions

| Direction | Mechanism | Horizons |
|---|---|---|
| profitability-quality | persistent quality and underpricing | 63/126/252 |
| fundamental-change | incremental operating change | 21/63/126 |
| cashflow-accrual | cash conversion and accrual quality | 126/252 |
| valuation | fundamental or forecast-yield repricing | 126/252 |
| analyst-revision | slow estimate-revision diffusion | 21/63/126 |
| investment-efficiency | allocation and asset efficiency | 126/252 |
| price-volume-microstructure | pressure, reversal/continuation, participation | 2/5/10/20 |
| volatility-option | volatility state and option information | 5/20/60 |
| news-sentiment | events, attention, sentiment diffusion | 2/5/20 |
| regime-conditioned-composite | slow signal gated by independent fast state | 5/20/126 |

### 5.2 Candidate Contract

Require mechanism, sign, horizon, observable proxies and roles, category-backed claims, failure modes, semantic description, expression, complete settings, operation, and parents. Follow [candidate_schema.json](candidate_schema.json) and [example_candidate.json](example_candidate.json).

### 5.3 Structural Examples

```fastexpr
group_rank(ts_rank(operating_income / equity, 126), subindustry)
group_rank(ts_rank(ts_delta(est_eps, 21) / close, 63), industry)
group_rank(ts_rank(cashflow_op / assets, 126), subindustry)
group_rank(ts_rank(-(close / open - 1), 5), industry)
group_rank(ts_rank(operating_income / assets, 126), subindustry) * rank(-ts_std_dev(returns, 20))
```

Treat these as mechanism templates, not alpha recommendations. Revalidate meaning, point-in-time availability, units, coverage, crowding, and sign.

### 5.4 Default Settings

| Type | Decay start | Neutralization | nanHandling | Main risk |
|---|---:|---|---|---|
| slow fundamental | 0-4 | SUBINDUSTRY | ON | step data, denominators, crowding |
| analyst revision | 0-4 | INDUSTRY/SUBINDUSTRY | ON | horizon and revision frequency |
| technical/microstructure | 10-30 | INDUSTRY | field-dependent | turnover and regimes |
| sentiment/news | 4-10 | INDUSTRY | ON | sparsity and event clustering |
| composite/regime | 4-20 | INDUSTRY/SUBINDUSTRY | ON | sign reversal and false complementarity |

## 6. Metrics, Gates, and Trajectory Reward

### 6.1 Core Metrics

| Metric | Meaning | Default threshold/preference |
|---|---|---|
| Sharpe | platform risk-adjusted return | minimum 1.25; prefer >= 1.5 |
| Fitness | platform composite | minimum 1.0; prefer >= 1.1 |
| Returns | BRAIN annualized convention | interpret with Margin and risk |
| Turnover | daily traded / book size | allow 1%-70%; prefer <= 20% |
| Drawdown | peak-to-trough loss | default absolute < 20%; prefer < 15% |
| Margin | PnL / total traded | higher is better |

### 6.2 IS Checks

| Check | Meaning | First action |
|---|---|---|
| LOW_SHARPE | weak or wrong mechanism | mechanism-level mutation |
| LOW_FITNESS | weak return or high turnover | preserve mechanism; repair realization |
| LOW/HIGH_TURNOVER | signal too slow or too fast | horizon, decay, trigger |
| CONCENTRATED_WEIGHT | sparse/outlier/missingness | rank, backfill, winsorize, truncation |
| LOW_SUB_UNIVERSE_SHARPE | size/liquidity dependence | exposure and neutralization change |
| SELF_CORRELATION | duplicate of existing alpha | new source category or mechanism |

### 6.3 Fixed Reward

Use:

`R(tau) = 0.30 Sharpe + 0.25 Fitness + 0.15 Returns + 0.10 Novelty - 0.08 Drawdown - 0.07 Turnover - 0.05 Complexity - Failed-Gate Penalty`

Scale and clip components using code-defined constants. Use ACTIVE daily-PnL novelty when available and structural AST/field novelty otherwise; never grant full novelty merely because an unsubmitted alpha has no PnL. Preserve the breakdown. Never let an LLM change the reward after observing results.

## 7. Fault Localization, Mutation, and Crossover

| Failure | Freeze | Revise |
|---|---|---|
| syntax/unit/operator | hypothesis, proxies, sign | expression implementation |
| concentration | mechanism, primary proxies | missingness, rank, truncation |
| high turnover | mechanism, primary fields | one of horizon, decay, or trade condition |
| low turnover | mechanism, sign | one of shorter horizon or more active proxy |
| low Fitness | validated parent evidence | one identified cause: turnover or weak return |
| low sub-universe Sharpe | mechanism, sign | one of grouping, neutralization, or liquidity dependence |
| low Sharpe | market context, validated evidence | one of field, window, or grouping |
| high correlation | market context, validated evidence | one correlated leg, proxy, or meaningful state filter |
| return up but risk worse | validated mechanism | regime and risk structure |

Generate exactly one child with one explicit change per mutation task. Select parents from all evaluated history by recorded reward without mechanism-cluster quotas, lineage caps, repair-distance tiers, use-count limits, or fixed route ratios. Record a concrete `action_id` and do not repeat an action that made the same parent worse. A child result evaluates that action only; it never retires the parent. Crossover likewise uses no cluster or lineage quota and must never concatenate code.

Use the paper's institutional-momentum example as a negative test: price-volume data alone do not identify institutional ownership or retail attention; no volatility field means no volatility weighting; children cannot precede parents; a risk-worsening rejected candidate is not a success.

## 8. BRAIN Automation

### 8.1 Credentials

Prefer environment variables:

```bash
export WQ_BRAIN_USERNAME="..."
export WQ_BRAIN_PASSWORD="..."
```

An ignored `credential.txt` may contain `["username", "password"]`. Never commit credentials, cookies, sessions, alpha databases, or private results.

### 8.2 Initialize, Register, Dry Run

WQ-compatible interface:

```bash
# Preview account changes and ACTIVE daily-PnL correlations; write nothing
python scripts/evolve_skill.py

# After review, update private alpha_db.json and sanitized aggregate lessons
python scripts/evolve_skill.py --apply

# Select the latest run and perform a safe local dry run
python scripts/submit_batch.py
```

Full QuantaAlpha trajectory interface:

```bash
python scripts/evolve_skill.py init --directions 10 --iterations 5 --max-iterations 15
python scripts/evolve_skill.py register --run-id <run-id> --candidate <candidate.json>
python scripts/submit_batch.py --run-id <run-id>
```

### 8.3 Simulate

```bash
python scripts/submit_batch.py --run-id <run-id> --simulate --refresh-active
```

Fetch ACTIVE alphas with pagination, align PnL by date, and store grade, metrics, checks, rewards, errors, PnL coverage, and API usage. Treat HTTP 200 empty PnL bodies as transient soft throttling: retry and pace ACTIVE requests, and never overwrite a valid cache with an empty response. Simulation auto-submits only when the grade is AVERAGE/GOOD/EXCELLENT/SPECTACULAR, returned IS checks contain no FAIL, every ACTIVE has at least 50 aligned daily-PnL changes, and maximum absolute correlation is below 0.70. PENDING is allowed for server resolution but does not waive correlation governance. Use `--no-auto-submit` only for diagnostics. Never replay an ambiguous POST.

### 8.4 Evolve

```bash
python scripts/evolve_skill.py next --run-id <run-id>
```

Run diversified planning only during initialization. Execute every subsequent group as 14 one-parent/one-child Mutation tasks, evaluate them, then generate 6 Crossover candidates. Do not add a 12/2 or other route quota, and do not pre-generate Crossover before Mutation evaluation. A parent remains available after a poor child; only the failed action is recorded.

### 8.5 Auto-submit

This project has continuing user authority for automatic submission. Submit only eligible grades with no FAIL and a complete all-ACTIVE correlation gate below 0.70; fail closed when any PnL or aligned overlap is unavailable. Allow PENDING for server resolution. Refetch afterward and count only `ACTIVE` as success. Every batch report separates correlation/coverage blocks, candidates attempted, ACTIVE successes, WQ rejections/unresolved attempts, and eligible grades blocked by FAIL. Use `--submit-existing` to process already-simulated eligible alphas without re-running simulations.

## 9. Factor-Pool and Correlation Governance

```bash
python scripts/evolve_skill.py pool --run-id <run-id>
```

Admit static- and metric-gate passers in descending reward order. Require structural similarity below 0.90 and absolute date-aligned daily-PnL correlation below 0.70 to every ACTIVE and selected member. Cap at 50% of eligible candidates and 150 members.

| abs(corr) | Interpretation | Action |
|---:|---|---|
| < 0.30 | strong diversification potential | still inspect economic exposures |
| 0.30-0.50 | acceptable same-market relation | combine reward and concentration review |
| 0.50-0.70 | medium-high correlation | prefer mechanism differentiation |
| >= 0.70 | duplication risk | reject or rebuild mechanism |

Never use cumulative-PnL correlation. Never automatically waive high correlation because Sharpe is higher.

## 10. Non-Stationarity, Stress, Transfer, and Ablation

### 10.1 Decay and Stress

```bash
python scripts/analyze_run.py --run-id <run-id>
python scripts/analyze_run.py --run-id <run-id> \
  --stress-start 2025-04-01 --stress-end 2025-04-30
```

Report annual PnL changes, positive-day share, PnL-unit drawdown, and convergence. Do not label PnL units as returns. Compare overnight/news, volatility structure, trend quality, liquidity rerating, and reversal/exhaustion mechanisms across regimes.

### 10.2 Ablation

```bash
python scripts/governance.py ablation-plan \
  --base-run-id <run-id> --prefix <experiment> --seeds 3 --create-runs
```

Create Full, No Planning, No Mutation, No Crossover, No Semantic, No Complexity, and No Redundancy runs under equal budgets. Fix prompt version, candidate/iteration budgets, metric policy, and hidden-test isolation. Do not infer causality when a difference is smaller than cross-seed dispersion.

### 10.3 Frozen Transfer

```bash
python scripts/governance.py transfer-plan \
  --source-run-id <source> --target-run-id <target> \
  --target-catalog <catalog.json> \
  --region EUR --universe TOP2500 --delay 1
```

Freeze source hypotheses and expressions before seeing target outcomes. Any target optimization invalidates the zero-shot label.

### 10.4 Costs and Capacity

BRAIN formula interfaces do not reproduce the paper's TopkDropout cost model. Use Turnover and Margin as platform proxies, then require external cost, slippage, capacity, crowding, and execution analysis before allocating capital.

## 11. Enterprise Governance, Budget, and Audit

```bash
python scripts/governance.py audit --run-id <run-id>
python scripts/governance.py budget --run-id <run-id>
```

Audit candidate hashes, lineage counts and time order, reproducible gates and rewards, PnL dates, pool eligibility and redundancy, planning coverage, API budget, and hidden-test isolation.

Default limits: three candidates per direction, two implementation repairs, 2,000 API requests, and 24 hours per run. Stop and record `budget_stop` when a limit is reached.

## 12. Pre-Submission Checklist

- [ ] Region, universe, delay, budget, and authority are explicit.
- [ ] Every candidate and failure is stored.
- [ ] Fields exist; types and coverage are acceptable.
- [ ] Hypothesis, proxies, expression, and settings are consistent.
- [ ] No identity, algebraic camouflage, or invalid lineage remains.
- [ ] Top-level grade is Average, Good, Excellent, or Spectacular.
- [ ] IS checks are present and contain no FAIL; PENDING is marked for server resolution.
- [ ] Sharpe >= 1.25, Fitness >= 1.0, and turnover is permitted.
- [ ] Correlation uses date-aligned daily PnL against every ACTIVE alpha.
- [ ] ACTIVE and pool correlations are below 0.70.
- [ ] Annual decay, stress, and concentration checks are complete.
- [ ] `governance.py audit` returns PASS.
- [ ] Multiple testing, costs, capacity, and external tradability are disclosed.
- [ ] Post-submit status is confirmed as ACTIVE.

## 13. Core Lessons

1. Define mechanism and proxies before writing an expression.
2. Diversity comes from sources and economic logic, not windows.
3. Correlation must use date-aligned daily PnL changes.
4. Mutation localizes failure before modifying validated segments.
5. Crossover reuses complementary mechanisms, not code strings.
6. Complex expressions require stronger evidence and must be simplified when possible.
7. Higher return with worse drawdown/IR may still require rejection.
8. Factor pools optimize incremental portfolio value, not only individual Sharpe.
9. Iterations 5, 11, or 12 are not inherently optimal; stop from convergence evidence.
10. HTTP 201 is not ACTIVE, and hidden tests never guide evolution.

## 14. Experience Evolution and Empirical Records

Trigger experience review after a simulation batch, status change, new field failure, ablation, transfer, or stress audit.

Use WQ-compatible account sync for full private account memory and run-specific `promote` for sanitized trajectory lessons.

```bash
python scripts/evolve_skill.py promote --run-id <run-id>
python scripts/evolve_skill.py promote --run-id <run-id> --apply
```

Promote only aggregate, sanitized, repeatedly supported rules with sample sizes and counterevidence. Keep IDs, expressions, PnL, status, and lineage under `private/`. Never append raw records to the Skill.

## 15. References and Offline Verification

- Research protocol: [research_protocol.md](research_protocol.md)
- Paper mapping: [paper_to_brain_mapping.md](paper_to_brain_mapping.md)
- FastExpr rules: [fastexpr_patterns.md](fastexpr_patterns.md)
- Agent roles: [agent_roles_en.md](agent_roles_en.md)
- Enterprise controls: [enterprise_controls_en.md](enterprise_controls_en.md)
- BRAIN API contract: [brain_api_contract_en.md](brain_api_contract_en.md)
- Full coverage matrix: [quantaalpha_coverage_matrix.md](quantaalpha_coverage_matrix.md)

Use Python 3.10+ and `requests`. Before credentials, run:

```bash
python scripts/selftest.py
```

A passing self-test validates software behavior only, not alpha quality or current BRAIN API compatibility.
