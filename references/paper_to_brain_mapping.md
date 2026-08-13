# QuantaAlpha Paper-to-BRAIN Mapping

## Contents

1. Problem and objective
2. Framework components
3. Evolution mechanics
4. Experimental ideas
5. Case-study lessons
6. Non-transferable components

Use this file when auditing whether a research run preserves the paper's ideas. The mapping covers the paper's substantive claims while correcting ambiguities identified during institutional review.

## 1. Problem and objective

| Paper idea | BRAIN implementation | Control |
|---|---|---|
| Markets are noisy, heavy-tailed, dependent, and non-stationary | Treat one simulation as weak evidence; retain annual/stress diagnostics and repeated runs | Never equate one high Sharpe with a stable alpha |
| Backtest feedback can cause semantic drift | Require structured hypothesis, observable proxies, failure modes, and semantic gate | Reject narratives unsupported by field categories |
| Stochastic regeneration loses validated experience | Archive complete candidate, settings, result, lineage, and fault diagnosis | Keep immutable JSONL events |
| Local exploitation causes crowding | Initialize ten categories/mechanisms and filter structural/PnL redundancy | Parameter changes do not count as new directions |
| Alpha objective is effectiveness minus regularization | Use fixed reward with quality, novelty, risk, turnover, complexity, and failed-check terms | Preserve component breakdown |
| Optimize trajectory-generation policy | Let the AI agent consume deterministic mutation/crossover briefs built from archived outcomes | Do not let the agent redefine evaluation after results |

## 2. Framework components

| Paper component | BRAIN implementation |
|---|---|
| Diversified Planning Initialization | `evolve_skill.py init` creates ten complementary directions and a planning packet |
| Hypothesis generation from observations, priors, and parameters | Candidate schema records mechanism, horizon, sign, proxies, claims, and failure modes |
| Semantic description `d` | `semantic_description` plus proxy roles |
| Operator library `O` | Verified FastExpr allowlist and field-type routing |
| AST intermediate representation | Deterministic token/parenthesis structure, feature extraction, depth, and structural n-grams |
| Compilation to code `c` | Submit expression to BRAIN simulation compiler |
| Implementation repair | Maximum two syntax/unit/operator repairs while hypothesis remains frozen |
| Hypothesis-description-expression consistency | Observable proxy and category-evidence gates |
| Expression-code consistency | The symbolic expression is the submitted FastExpr; returned simulation identifies compilation success |
| Complexity `C(f)` | Character count, field count, depth, and free-parameter ratio with explicit limits |
| Largest-common-subtree redundancy | Weighted abstract token n-gram and field Jaccard similarity; normalized rather than raw subtree size |
| Functional redundancy | Absolute correlation of date-aligned daily PnL changes |
| Evaluation history | Append-only candidates, evaluations, and event files under a private run |
| Final factor pool | Greedy reward-ranked pool with structural and PnL correlation gates |

## 3. Evolution mechanics

| Paper idea | BRAIN implementation | Institutional refinement |
|---|---|---|
| Seed factors grouped by low correlation | Start from distinct BRAIN field categories and later use ACTIVE daily-PnL correlation | Do not assume public seed templates are independent |
| Mutation localizes the most harmful node | `diagnose_evaluation` maps failure type to frozen/revised trajectory segments | Localization is a rule-based diagnosis, not a causal proof |
| Freeze prefix and rewrite a local segment | Mutation packet explicitly lists `freeze` and `revise` | One coherent child hypothesis per brief, with up to three distinct realizations |
| Mechanism-level mutation | Low Sharpe or high correlation requires mechanism/category change | Window-only search is rejected as insufficient |
| Crossover selects high-reward parents | Continuous evolution score selects evaluated positive trajectories; pair score combines fields, structure, direction, failure modes, and PnL complementarity | Near-gate trajectories may be parents; the final pool still requires every metric gate |
| Reuse hypothesis templates, construction, and repair behavior | Crossover packet includes parent hypotheses and metrics | Child must be coherent; no expression concatenation |
| Traceable lineage | Every child records operation and parents | Raw lineage remains private |
| Five-cycle main search | Default target is five iterations | This is a budget, not a performance guarantee |
| Improvement can continue toward 15 iterations | Permit at most fifteen iterations and analyze convergence | Early-stop after saturation; do not target iteration 11-12 mechanically |
| Up to three expressions per hypothesis; Mutation then Crossover per iteration | Initialize planning once; then run fixed 14 Mutation → evaluate → 6 Crossover cycles | The 14/6 split is a 20-simulation BRAIN budget mapping, not a uniquely prescribed paper ratio |

## 4. Experimental ideas

| Paper experiment or claim | Skill treatment |
|---|---|
| IC, ICIR, RankIC, RankICIR | BRAIN does not expose the same factor-panel interface through these scripts; do not fabricate them |
| ARR, IR, MDD | Use BRAIN Returns, Sharpe, Drawdown, Fitness, Turnover, and Margin with their platform meanings |
| Same downstream LightGBM for factor pools | Not reproducible in formula-alpha BRAIN interface; replace with governed alpha pool, not a claim of model equivalence |
| Ablate planning, mutation, crossover, and gates | Run separate configurations with multiple seeds and compare full reward distributions |
| Cross-seed robustness | Create independent run IDs; report between-run dispersion |
| Statistical significance over daily IC | Use daily PnL only for correlation/stability; apply robust inference externally if claiming significance |
| Transaction-cost sensitivity | Use Turnover and Margin as platform proxies; require external execution tests for cost claims |
| Token and compute budget | Record candidate counts, simulations, repairs, iterations, and elapsed time in run events |
| CSI300 to CSI500/S&P500 zero-shot transfer | Freeze expression first, verify target fields, and label any refit or expression edit explicitly |
| Alpha decay by year | `analyze_run.py` reports annual daily-PnL-change diagnostics |
| Regime transition and persistent microstructure channels | Form hypotheses across slow fundamentals, overnight/news, volatility, and price-volume categories; validate rather than assume persistence |
| April 2025 stress period | Pass explicit dates to `analyze_run.py`; report PnL units, observation count, drawdown, and positive-day share |
| Factor-level semantic diagnosis | Compare direction, field categories, failure modes, and annual outcomes |
| Iteration convergence | Report mean, best, and best-so-far reward by iteration |
| Pool size around 50% of mined factors | Default pool fraction is 0.50 with an absolute cap; treat as configurable governance |

## 5. Case-study lessons

The paper's institutional-momentum case is preserved as a negative control:

- Do not infer institutional ownership from price-volume correlation alone.
- Do not infer retail attention from average intraday return alone.
- Do not claim volatility-adaptive weighting if no volatility proxy appears in the expression.
- Do not accept a child whose lineage round precedes a parent round.
- Do not call a child successful when return improves but risk metrics degrade and the deployment decision is rejected.
- Remove tautological terms such as a variable correlated with itself.

These lessons are implemented through observable-proxy requirements, category-evidence claims, explicit lineage, metric gates, and expression review.

## 6. Non-transferable components

The following paper components cannot be honestly reproduced through the current BRAIN formula-alpha interface:

- the CSI300/CSI500/S&P500 datasets and their exact chronological splits;
- next-day close labels and the paper's LightGBM downstream model;
- TopkDropoutStrategy with 50 holdings and five daily replacements;
- the paper's exact transaction-cost model;
- its reported IC, return, drawdown, ablation, and transfer numbers;
- proprietary LLM prompts, trajectory rewards, thresholds, and parent-selection details not disclosed in the PDF.

Do not claim equivalence. Implement the transferable research logic and keep platform-specific metrics explicit.
