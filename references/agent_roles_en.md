# QuantaAlpha Logical Agent Role Specification

## Contents

1. Shared contracts
2. Planning Agent
3. Idea Agent
4. Factor Agent
5. Verifier
6. Evaluation Agent
7. Evolution Agent
8. Governance Agent
9. Isolation and handoff

## 1. Shared Contracts

Exchange information only through `run.json`, planning packets, candidate JSON, evaluation JSON, iteration task packets, factor pools, and governance reports. Never depend on unarchived chat memory.

Never rewrite historical JSONL. Corrections create a new event or candidate. Use UTC ISO-8601 timestamps.

## 2. Planning Agent

Input: region, universe, delay, allowed categories, seeds, budget, and ACTIVE summary.

Output: complementary directions, mechanism scope, candidate count, horizons, and prohibited duplicate regions.

Gate: cover slow/fast, level/change, price/fundamental/forecast/alternative, and regime-conditioned ideas. Window changes alone are not directions.

## 3. Idea Agent

Input: one direction, catalog, priors, and prior failure modes.

Output: falsifiable mechanism, sign, horizon, proxies, failure modes, and counterexamples.

Gate: every narrative claim is observable from a field category. Do not use institutional, retail, or fundamental labels without data.

## 4. Factor Agent

Input: approved hypothesis, metadata, operator allowlist, and complexity budget.

Output: semantic description, FastExpr, complete settings, and implementation rationale.

Gate: at most three realizations, simplest-first, verified VECTOR reduction, and catalog-compatible market settings.

## 5. Verifier

Input: complete candidate and prior candidates.

Output: field, type, semantic, complexity, identity, simplification, structural redundancy, and lineage decisions.

Gate: stay independent of backtest results. Reject semantic inconsistency even when performance is high.

## 6. Evaluation Agent

Input: BRAIN details, IS checks, dated PnL, ACTIVE snapshot, and complexity.

Output: metrics, aligned correlations, fixed reward components, submission blockers, and fault localization.

Gate: never change reward weights, treat missing metrics as success, or use hidden outcomes.

## 7. Evolution Agent

Input: evaluated trajectories and deterministic mutation/crossover packets.

Output: a new candidate with parent IDs, operation, frozen segments, and revision rationale.

Mutation changes only the localized segment and produces one child per task. Crossover combines complementary mechanisms and proxies, never code strings.

## 8. Governance Agent

Input: configuration, candidates, evaluations, events, pool, and budget.

Output: lineage, hash, reward, PnL-date, redundancy, budget, hidden-test, coverage, and privacy audit.

Gate: any CRITICAL issue blocks submission and lesson promotion.

## 9. Isolation and Handoff

- Generation roles never see hidden tests or competition scores.
- Verification never relaxes semantics for high returns.
- Evaluation never edits expressions.
- Evolution never overwrites parents.
- Governance audits and never generates alphas.
- Parallel roles receive minimum necessary context and merge only through one ResearchStore.
