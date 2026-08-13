# Enterprise Quantitative Research Controls

## Contents

1. Authority and classification
2. Research integrity
3. Model and prompt governance
4. Statistical controls
5. Risk and tradability
6. Change, audit, and recovery
7. Release gates

## 1. Authority and Classification

Classify data as public skill assets, internal configurations, confidential alpha assets, or credentials/sessions. Public files contain none of the latter three.

Simulation and submission write external state and require explicit authority. This project has continuing auto-submission authority: attempt submission only when `grade` is AVERAGE, GOOD, EXCELLENT, or SPECTACULAR and no IS test is FAIL; let the server resolve PENDING checks and record the terminal status.

## 2. Research Integrity

- Preregister region, universe, delay, budget, directions, thresholds, stopping rules, and stress windows.
- Record every candidate, failure, repair, and API call.
- Use only permitted in-sample metrics and ACTIVE self-correlation for evolution.
- Never feed hidden tests, competition scores, or final transfer outcomes back into generation.
- Record every manual change as an audit event.

## 3. Model and Prompt Governance

- Record runtime, model, prompt version, and candidate-schema version externally when the platform cannot expose them.
- Keep model, prompt, candidate budget, iteration budget, and metric policy equal across ablations.
- Never change rewards, gates, or stopping rules after observing results.
- Require human review for lesson promotion and retain scope, sample size, and counterevidence.

## 4. Statistical Controls

- Use independent run IDs and at least three seeds for method comparisons.
- Disclose total candidates, repairs, failures, and search space.
- Do not claim component efficacy when differences are below cross-seed dispersion.
- Use suitable external HAC, block bootstrap, Reality Check, SPA, FDR, or Deflated Sharpe methods for significance claims.
- Keep the final test untouched and never use it to decide stopping.

## 5. Risk and Tradability

- Decompose industry, size, beta, volatility, liquidity, and crowding externally when BRAIN does not expose them.
- Review Sharpe, Fitness, Returns, Turnover, Drawdown, Margin, counts, and every IS check.
- Compare date-aligned daily PnL with every ACTIVE alpha and pool member.
- Before capital allocation, test fees, slippage, execution limits, capacity, impact, borrow, and extreme markets.
- Passing BRAIN submission gates is not production investment approval.

## 6. Change, Audit, and Recovery

- Append trajectory history; never overwrite it.
- Before release, run self-test, governance audit, Skill validator, and local-link checks.
- Stop at budgets, authentication failure, or ambiguous outcomes; never blindly replay POST.
- Recover private runs from JSONL and `run.json`, not chat context.
- Mark a run FAIL when hashes, lineage, rewards, or PnL dates cannot be reproduced.

## 7. Release Gates

Allow real-submission candidacy only when software, governance, and research gates pass; semantics are defensible; independent/yearly/stress stability is acceptable; multiple testing and search budget are disclosed; correlation, cost, capacity, and risk comply with policy; and the user explicitly approves submission.

Discuss capital allocation only after a separate production review.
