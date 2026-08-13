# QuantaAlpha WQ Research Protocol

## Contents

1. Research objective and boundaries
2. Trajectory contract
3. Planning and factor realization
4. Deterministic gates
5. Evaluation and reward
6. Mutation and crossover
7. Factor-pool governance
8. Non-stationarity, transfer, and stress tests
9. Statistical and operational controls

## 1. Research objective and boundaries

Treat one end-to-end research attempt as a trajectory:

`market context -> hypothesis -> semantic specification -> FastExpr -> settings -> simulation -> evaluation -> decision`

Optimize the expected terminal reward of trajectories, not a single backtest metric. Use BRAIN in-sample metrics and ACTIVE self-correlation for evolution. Do not feed hidden test, competition, or submission outcome metrics back into candidate search. Preserve those outcomes for final audit only.

This skill produces formula alphas for BRAIN. It does not reproduce the paper's LightGBM factor-pool model or TopkDropout portfolio because those are not BRAIN FastExpr interfaces. Map those concepts to a governed alpha pool, platform neutralization, truncation, turnover, margin, and self-correlation.

## 2. Trajectory contract

Represent every candidate with `candidate_schema.json`. Require:

- an economic mechanism that could be false;
- an expected sign and horizon;
- observable field proxies for every narrative claim;
- explicit failure modes;
- one FastExpr expression and complete simulation settings;
- operation type and parent lineage.

Store private trajectories under `private/research_runs/<run-id>/`. Never write raw alpha IDs, expressions, PnL, credentials, or account status into `SKILL.md` or public references.

## 3. Planning and factor realization

Initialize ten complementary directions: profitability, fundamental change, cash-flow/accrual, valuation, analyst revisions, investment efficiency, price-volume microstructure, volatility/options, news/sentiment, and regime-conditioned composites.

Generate at most three expressions for one hypothesis. Vary mechanisms, categories, horizons, and regime assumptions. Do not count parameter-only variations as diversified planning.

Realize each hypothesis in four stages:

1. Select fields from the local USA TOP3000 Delay 1 catalog.
2. State how each field observes a component of the mechanism.
3. Construct a bounded FastExpr and settings object.
4. Run deterministic validation before any API request.

Treat the parsed token structure as the BRAIN-compatible symbolic representation. Compilation occurs through the BRAIN simulation endpoint. Permit at most two implementation-repair attempts for syntax, operator signature, or unit errors. Do not use a compile error as permission to change the economic hypothesis.

## 4. Deterministic gates

Apply all gates before simulation:

- Expression length: at most 250 characters.
- Base fields: at most 6.
- Parenthesis depth: at most 12.
- Free numeric parameter ratio: below 50% of numeric parameters plus operator calls.
- Field existence: every identifier must resolve to a catalog field, verified operator, or reserved keyword.
- Type safety: VECTOR fields require a verified vector reduction.
- Semantic consistency: every expression field must appear in `observable_proxies`; every required proxy must appear in the expression.
- Claim evidence: claims about analyst, option, news, social, or fundamental information require at least one field from the corresponding category.
- Structural novelty: weighted token-structure and field Jaccard similarity must remain below 0.90.

After simulation, apply functional redundancy on date-aligned daily PnL changes. Before submission, require every ACTIVE alpha to have at least 50 aligned daily changes and fail closed when any PnL or overlap is unavailable. Reject candidates with absolute correlation at or above 0.70 to an ACTIVE alpha or selected pool member. Window, weight, decay, or neutralization changes alone do not establish novelty.

## 5. Evaluation and reward

Evaluate predictive quality and trading quality with BRAIN metrics:

- Sharpe and Fitness for risk-adjusted effectiveness;
- Returns and Margin for payoff and trading efficiency;
- Turnover for friction sensitivity;
- Drawdown for path risk;
- IS checks for concentration, sub-universe robustness, turnover, and self-correlation;
- ACTIVE daily-PnL correlation for incremental portfolio value;
- expression complexity for interpretability and overfitting control.

Use the deterministic reward in `research_core.trajectory_reward`:

`0.30 Sharpe + 0.25 Fitness + 0.15 Returns + 0.10 Novelty - 0.08 Drawdown - 0.07 Turnover - 0.05 Complexity - 0.10 per failed-gate tier`

Each component is clipped and scaled by documented thresholds. Novelty uses ACTIVE daily-PnL correlation when available and falls back to AST/field structural novelty otherwise; unsubmitted candidates must not receive an automatic full novelty score. Always retain the component breakdown. Never allow an LLM to rewrite the reward after seeing results.

## 6. Mutation and crossover

### Mutation

Localize the failure before changing a candidate:

- Syntax/unit error: freeze hypothesis and proxies; repair implementation only.
- Concentration: freeze mechanism; repair backfill, ranking, winsorization, or truncation.
- High turnover: change one of horizon, decay, or trade condition.
- Low turnover: shorten the horizon or use one more active proxy.
- Low Fitness: identify turnover versus weak return first, then change one cause.
- Low sub-universe Sharpe: change one of grouping, neutralization, or liquidity dependence.
- Low Sharpe: change one of field, window, or grouping.
- High correlation: change one correlated leg, proxy, or meaningful state filter; parameter-only tuning is insufficient.

Select non-ACTIVE parents from all evaluated history by recorded reward, without mechanism-cluster quotas, lineage caps, repair-distance tiers, use-count limits, or fixed route ratios. Generate exactly one child per mutation task. Record a concrete `action_id`; do not repeat an action that already made the same parent worse.

A child result evaluates only that concrete action. Never close, retire, or invalidate the parent because one child is worse; the same parent may later receive a different mutation.

### Crossover

Select evaluated trajectories without mechanism-cluster or lineage quotas. Synthesize one coherent child hypothesis; do not concatenate or average expressions mechanically. Final static and PnL-correlation gates remain unchanged.

Run diversified planning only during initialization. Split every subsequent 20-simulation group into 14 one-parent/one-child Mutation tasks, evaluation, and 6 Crossover candidates. Generate Crossover only after the Mutation children have been registered, simulated, and evaluated. Do not add a 12/2 or any other route quota.

## 7. Factor-pool governance

Maintain a cumulative pool after each iteration:

1. Keep only candidates passing static and metric gates.
2. Sort by deterministic trajectory reward.
3. Greedily admit candidates with structural similarity below 0.90 and absolute date-aligned PnL correlation below 0.70 to every pool member.
4. Cap the pool at 50% of eligible mined candidates and 150 members by default.

Default to five iterations. Permit up to fifteen for convergence research. Stop early after three iterations without material best-so-far improvement or when added candidates degrade drawdown/novelty. Treat the paper's 11th-12th iteration observation as a hypothesis, not a universal stopping rule.

## 8. Non-stationarity, transfer, and stress tests

Run annual PnL-change diagnostics to identify alpha decay and regime dependence. Use `analyze_run.py` for annual and user-specified stress windows. PnL-unit diagnostics are not returns; label them correctly.

For universe or region transfer:

1. Freeze the source expression and hypothesis before viewing target results.
2. Verify every field and operator in the target region/universe/delay.
3. Change only required platform settings.
4. Record transferred and retrained components separately.
5. Do not call a result zero-shot when fields, expression, or model weights were re-optimized on the target.

Assess transaction-cost sensitivity through Turnover and Margin because BRAIN formula simulations do not expose the paper's TopkDropout cost model. Do not claim cost robustness without explicit platform metrics or an external execution backtest.

## 9. Statistical and operational controls

- Record every attempted candidate, including gate and simulation failures.
- Record the search budget: directions, candidates, iterations, API calls, and repair attempts.
- Compare ablations across repeated seeds/runs; do not interpret a single-run delta below run-to-run variability.
- Use date-aligned PnL, never cumulative-PnL correlation.
- Treat an HTTP 200 empty PnL body as transient soft throttling: retry with pacing, retain the last valid private cache, and never use an empty array to bypass submission governance.
- Keep a final untouched evaluation stage and report multiple-testing risk.
- Require explicit authorization before live submission.
- Confirm `status == ACTIVE`; HTTP 201 alone is not success.
- Keep credentials and private records ignored by version control.
- Promote only aggregate, sanitized, repeatedly observed lessons into public references.
