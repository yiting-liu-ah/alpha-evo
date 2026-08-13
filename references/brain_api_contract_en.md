# WorldQuant BRAIN Interface Contract

## Contents

1. Scope
2. Authentication and security
3. Endpoints and states
4. PnL recordsets
5. Retry and rate limits
6. Submission state machine
7. Compatibility validation

## 1. Scope

This contract documents behavior assumed by the current Skill. It is not an official stability guarantee from WorldQuant. When fields, schemas, states, or endpoints change, update private compatibility tests before changing public instructions.

## 2. Authentication and Security

- Read `WQ_BRAIN_USERNAME` and `WQ_BRAIN_PASSWORD`, or an ignored `credential.txt`.
- Create an HTTP Basic Auth session and `POST /authentication`.
- Expect HTTP 201. Never print passwords or sensitive full responses.
- Never commit cookies, tokens, sessions, credentials, or account-linked results.

## 3. Endpoints and States

| Function | Method and endpoint | Expected behavior |
|---|---|---|
| Authentication | `POST /authentication` | 201 |
| Field catalog | `GET /data-fields` | paginated objects |
| User alphas | `GET /users/self/alphas` | paginated objects |
| Alpha detail | `GET /alphas/{id}` | metrics, status, checks |
| PnL | `GET /alphas/{id}/recordsets/pnl` | schema plus records |
| Simulation | `POST /simulations` | 201 plus Location |
| Simulation poll | `GET <Location>` | COMPLETE/FAILED states |
| Submission | `POST /alphas/{id}/submit` | request acceptance, not ACTIVE |

Never replay an ambiguous simulation POST automatically. Poll with a total timeout.

## 4. PnL Recordsets

`schema.properties` may be a list or dictionary, and records may contain one nested row. Unwrap rows, resolve date and PnL indexes from schema, coerce values, deduplicate and sort dates, difference cumulative PnL, and inner-join by date before correlation. BRAIN may soft-throttle this endpoint with HTTP 200 and an empty body; retry it as a transient GET state, pace ACTIVE requests, and retain the last valid private cache rather than replacing it with an empty list.

Never align only by array length and never correlate cumulative curves.

## 5. Retry and Rate Limits

- Retry bounded GET connection errors, timeouts, 429, 500, 502, 503, and 504.
- Honor Retry-After seconds or HTTP date; otherwise use capped exponential backoff.
- Send POST once by default and query state after ambiguity.
- Execute serially with a two-second candidate interval and stop at the run API budget.

## 6. Submission State Machine

```text
SIMULATED
  |-- blocker -> SIMULATED_NOT_SUBMITTED
  `-- explicit submission
        |-- HTTP failure -> SUBMIT_FAILED
        |-- self-correlation fail -> NOT_ACTIVE_AFTER_SUBMIT
        |-- timeout/review -> NOT_ACTIVE_AFTER_SUBMIT
        `-- status ACTIVE -> ACTIVE
```

Record UNSUBMITTED, self-correlation failure, timeout, and other rejection separately. HTTP 201 is never ACTIVE.

## 7. Compatibility Validation

Account synchronization is compatible with the original WQ Skill: `python scripts/evolve_skill.py` previews and `--apply` updates private `alpha_db.json`. Preview mode writes nothing, and public lessons contain sanitized aggregates only.

Run `selftest.py`, dry-run one low-risk field, then after simulation authority use one candidate to validate authentication, Location polling, alpha detail, and PnL schema. Never auto-submit the compatibility candidate. Preserve sanitized error types only.
