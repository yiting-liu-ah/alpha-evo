# QuantaAlpha Full Coverage Matrix / 论文全观点覆盖矩阵

This matrix is the acceptance checklist for paper coverage. `Direct` means executable on BRAIN, `Adapted` means the research idea is preserved with a platform-specific implementation, and `Disclosure` means the paper component cannot be reproduced honestly through the formula-alpha interface.

本矩阵是论文覆盖验收清单。`Direct` 表示可在 BRAIN 直接执行，`Adapted` 表示保留研究思想但使用平台代理实现，`Disclosure` 表示无法通过公式 Alpha 接口诚实复现。

| ID | PDF | Paper idea / 论文观点 | Status | Skill implementation / Skill 实现 | Verification / 验证 |
|---|---:|---|---|---|---|
| QA-001 | 1-2 | Markets are noisy and non-stationary / 市场含噪且非平稳 | Adapted | repeated runs, annual decay, stress windows | `analyze_run.py` |
| QA-002 | 2 | Heavy tails, time-varying volatility, cross-sectional dependence | Adapted | outlier controls, regime hypotheses, group neutralization | gates + yearly diagnostics |
| QA-003 | 2 | Existing agents suffer fragile controllability | Direct | immutable hypothesis/proxy/expression/settings contracts | candidate schema + audit |
| QA-004 | 2 | Existing agents lack trustworthy inheritance | Direct | append-only candidates, evaluations, events, parent lineage | `governance.py audit` |
| QA-005 | 2 | Existing search over-exploits local neighborhoods | Direct | ten mechanism/category directions, max three candidates each | planning packet coverage |
| QA-006 | 1-3 | Treat end-to-end mining as a trajectory | Direct | market context -> hypothesis -> semantics -> code -> evaluation -> decision | private run store |
| QA-007 | 3 | Alpha objective balances utility and regularization | Adapted | fixed quality/novelty/risk/turnover/complexity reward | reward recomputation audit |
| QA-008 | 3 | Terminal trajectory reward | Direct | deterministic `trajectory_reward` with component breakdown | `REWARD_NOT_REPRODUCIBLE` check |
| QA-009 | 3 | Optimize expected trajectory-generation policy | Adapted | AI consumes deterministic planning/mutation/crossover packets | task packet lineage |
| QA-010 | 4 | Framework has planning, realization, self-evolution, final pool | Direct | four stages exposed by CLI and run state | end-to-end self-test |
| QA-011 | 4 | Hypothesis uses observations, domain priors, parameters | Direct | mechanism, horizon, sign, proxies, failure modes | candidate schema |
| QA-012 | 4-5 | Use standardized operator library | Direct | verified FastExpr allowlist and field-type routing | static validation |
| QA-013 | 4-5 | Use AST intermediate representation | Adapted | token/parenthesis structure, feature set, n-grams, depth | complexity output |
| QA-014 | 5 | Leaf nodes are fields; internal nodes are operators | Direct | tokenizer resolves catalog fields and verified operators | unknown identifier gate |
| QA-015 | 5 | Compile symbolic expression into executable code | Direct | archived FastExpr sent unchanged to BRAIN Simulation | simulation record |
| QA-016 | 5 | Repair implementation while preserving semantics | Direct | two repair attempts; freeze hypothesis/proxies | budget + mutation contract |
| QA-017 | 5 | Verify hypothesis-description-expression alignment | Direct | required proxies and category-backed claims | semantic gate |
| QA-018 | 5 | Verify expression-code faithfulness | Direct | candidate hash and submitted expression contract | governance hash audit |
| QA-019 | 5 | Complexity uses symbolic length | Direct | maximum 250 characters | complexity gate |
| QA-020 | 5 | Complexity counts free parameters | Direct | numeric parameter ratio below 0.50 | complexity gate |
| QA-021 | 5 | Complexity penalizes number of features | Direct | maximum 6 fields plus reward penalty | complexity gate/reward |
| QA-022 | 5 | Structural redundancy uses common substructure | Adapted | normalized abstract-token n-gram plus field Jaccard | structural similarity audit |
| QA-023 | 5 | Functional redundancy uses output correlation | Direct | absolute date-aligned daily-PnL correlation | `aligned_correlation` |
| QA-024 | 5 | Keep better candidate when functionally equivalent | Adapted | greedy reward-ranked admission, not paper RankIC | pool manifest disclosure |
| QA-025 | 5 | Evaluation covers prediction, return, and risk | Adapted | Sharpe, Fitness, Returns, Margin, Turnover, Drawdown, IS checks | evaluation JSON |
| QA-026 | 5 | Maintain success/failure history | Direct | save every gate and simulation outcome | append-only JSONL |
| QA-027 | 5-6 | Start from low-correlation diverse seeds | Adapted | distinct data categories plus ACTIVE PnL novelty | planning + active snapshot |
| QA-028 | 6 | Initialization varies sources, scales, mechanisms, regimes | Direct | ten directions and explicit horizons | planning packet |
| QA-029 | 6 | Evolved trajectories act as demonstrations/priors | Adapted | AI receives archived parent hypotheses, metrics, and repair behavior | next-iteration packet |
| QA-030 | 6 | Mutation localizes the failure-causing node | Direct | rule-based fault diagnosis with freeze/revise segments | diagnosis table + audit |
| QA-031 | 6 | Mutation freezes prefix and regenerates suffix coherently | Direct | one child per mutation; explicit frozen payload | lineage audit |
| QA-032 | 6 | Mutation can change time scale or add regime conditions | Direct | horizon/decay/regime fields in mutation instructions | task packet |
| QA-033 | 6 | Imperfect localization still expands search | Adapted | store failed child and preserve alternative region | all failures retained |
| QA-034 | 6 | Crossover selects high-reward parents | Direct | continuous evolution score over complete positive trajectories; final pool gate remains separate | crossover selector + offline replay |
| QA-035 | 6 | Crossover reuses complementary validated segments | Direct | pair score uses fields, structure, direction, PnL | crossover packet |
| QA-036 | 6 | Crossover must form a coherent trajectory | Direct | narrative/proxy gate; no string concatenation | semantic validation |
| QA-037 | 6-7 | Use chronological train/validation/test discipline | Adapted | hidden outcomes excluded from evolution; source/target freeze | test-integrity audit |
| QA-038 | 6-8 | Evaluate IC/ICIR/RankIC/RankICIR | Disclosure | current BRAIN client lacks equivalent factor-panel output | explicit non-equivalence |
| QA-039 | 6-8 | Evaluate ARR/IR/MDD | Adapted | use BRAIN Returns/Sharpe/Drawdown with platform meanings | metric labels |
| QA-040 | 7-8 | Compare methods with same downstream LightGBM and ~150 factors | Disclosure | formula-alpha pool only; no LightGBM equivalence claim | disclosure reference |
| QA-041 | 7-8 | Compare multiple LLM backbones | Adapted | record prompt/runtime version externally; equal-budget runs | ablation control contract |
| QA-042 | 14 | Report compute and token consumption | Adapted | candidate/API/time budgets; token usage reported when runtime exposes it | `governance.py budget` |
| QA-043 | 7-9 | Ablate planning, mutation, crossover | Direct | Full/No Planning/No Mutation/No Crossover runs | ablation manifest |
| QA-044 | 7-9 | Ablate consistency, complexity, redundancy | Direct | No Semantic/No Complexity/No Redundancy runs | component switches |
| QA-045 | 15 | Test cross-seed variance | Direct | independent seed run IDs with equal contracts | ablation seeds |
| QA-046 | 15 | Use statistical evidence across daily observations | Adapted | PnL stability only; robust significance must be external | disclosure in reports |
| QA-047 | 15 | Rule out data snooping | Adapted | log every candidate, fixed reward, hidden-stage isolation, search budget | governance audit |
| QA-048 | 8-9 | Zero-shot transfer across markets | Direct/Adapted | freeze source hypothesis/expression; verify target fields/settings | transfer manifest |
| QA-049 | 9 | Cross-sectional normalization aids transfer | Adapted | BRAIN rank/group operators and neutralization | settings + expression audit |
| QA-050 | 9-10 | Diagnose alpha decay by year and regime | Direct | annual daily-PnL-change diagnostics | `analyze_run.py` |
| QA-051 | 9,20-22 | Overnight/auction information can persist | Direct hypothesis | news/open/close/volume fields if available; must be validated | direction-specific candidates |
| QA-052 | 9,20-22 | Volatility/range structure can persist | Direct hypothesis | pv/option regime directions | annual/stress comparison |
| QA-053 | 20-21 | Trend quality should be conditioned on noise/liquidity | Direct hypothesis | regime-conditioned composite direction | proxy and interaction gate |
| QA-054 | 20-21 | Exhaustion/reversal can fail under liquidity rotation | Direct hypothesis | failure modes and regime diagnostics | yearly factor comparison |
| QA-055 | 9-10 | Track quality distribution across iterations | Direct | mean, best, best-so-far reward by iteration | convergence report |
| QA-056 | 10,22-23 | Evolution may simplify overengineered expressions | Direct | complexity gate, algebraic simplification, mutation diagnosis | static rejection tests |
| QA-057 | 10,23 | Later iterations may add participant-differentiated information | Direct with evidence | require actual analyst/news/social/option fields | category-claim gate |
| QA-058 | 10,22 | Performance eventually saturates or degrades | Direct | patience 3, maximum 15, pool novelty/convergence | stopping policy |
| QA-059 | 13-14 | Define IC and RankIC formulas | Disclosure | retained as paper context; not fabricated from BRAIN PnL | mapping note |
| QA-060 | 14 | Paper label is close[t+2]/close[t+1] and uses CSRankNorm | Disclosure | BRAIN owns target/backtest internals | API boundary statement |
| QA-061 | 14 | Paper baselines include ML/DL/libraries/agents | Disclosure | no false baseline reproduction | experiment disclosure |
| QA-062 | 16 | Use transaction-cost sensitivity | Adapted | Turnover/Margin proxy plus mandatory external execution study | enterprise checklist |
| QA-063 | 16 | Use 10 directions, 5 iterations, up to 3 expressions/hypothesis | Direct/adapted budget | Initialize 10 directions once; subsequent 20-simulation cycles use fixed 14 Mutation then 6 Crossover after evaluation | task packet audit |
| QA-064 | 16 | Support bounded operator categories | Direct | allowlist and FastExpr reference | static validation |
| QA-065 | 16-17 | Topk50, drop5, open execution, costs, limits | Disclosure | not a BRAIN formula-alpha interface | no-equivalence statement |
| QA-066 | 17-20 | Preserve factor identity, trajectory ID, round, phase, parents | Direct | candidate IDs, run IDs, iteration, operation, parents | lineage audit |
| QA-067 | 18-20 | Crossover hypothesis can be only partially supported | Direct | compare metrics and deployment blockers; allow REJECTED outcome | evaluation record |
| QA-068 | 19-20 | Higher return can coexist with worse IR/MDD | Direct | multi-objective reward and risk gates | reward breakdown |
| QA-069 | 20 | Rejected trajectory should inform next mutation | Direct | diagnose evaluation and generate next task | mutation packet |
| QA-070 | 20-22 | Market-style interpretation must align with factor semantics | Direct | category-backed claims plus annual regime analysis | semantic and decay audit |
| QA-071 | 21 | Compare right-tail, coverage, positive-factor share | Adapted | factor-pool direction/coverage/reward distributions | research report |
| QA-072 | 22 | Diversity increases survival probability after regime shifts | Direct hypothesis | category/direction concentration and pool novelty | pool governance |
| QA-073 | 22 | Stress-test April 2025 or another prespecified event | Direct | user-specified stress window | stress report |
| QA-074 | 22 | Fifteen-iteration convergence study | Direct | configurable maximum 15 | run policy |
| QA-075 | 22 | Greedy pool admission by validation RankIC | Adapted | greedy deterministic reward because RankIC unavailable | explicit metric substitution |
| QA-076 | 22 | Pool correlation threshold 0.70 and cap 50% | Direct | default correlation 0.70, fraction 0.50, max 150 | pool audit |
| QA-077 | 22 | Iterations 11-12 were empirically balanced in the paper | Adapted | treat as hypothesis; never hard-code as optimum | convergence rule |
| QA-078 | 23 | Reject tautological self-correlations | Direct hardening | explicit `ts_corr(x,x,N)` rejection | self-test |
| QA-079 | 1,7-10 | Paper reports specific IC/return/transfer results | Disclosure | cite as source claims only; never promise reproduction | final report disclosure |
| QA-080 | 10 | Interpretability and controllability are core outputs | Direct | human-readable contracts, reward parts, lineage, audit | governance PASS requirement |

## Acceptance Rule / 验收规则

A release passes paper coverage only when every row has an implementation or explicit disclosure, every referenced executable exists, the offline self-test passes, the governance audit can reproduce stored rewards and lineage, and the Skill validator reports success.

只有当每一行均存在实现或明确披露、全部引用脚本存在、离线 Self-test 通过、治理审计能够重算奖励与谱系、Skill 官方校验成功时，才视为通过论文覆盖验收。
