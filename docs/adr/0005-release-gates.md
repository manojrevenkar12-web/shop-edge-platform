# 0005. Two gates on a release: SonarQube, then a canary

## Status

Accepted.

## Context

Static analysis finds some defects (a null dereference, an unsafe config read) but not others (a query that is slow
only on real data). A canary finds what traffic finds, but only for the share of visitors it serves.

## Decision

1. **SonarQube's quality gate** (`waitForQualityGate abortPipeline: true`) stops a build whose new code fails it.
2. **A canary checks the rest.**
   - The Argo Rollout sends 10% of traffic to the new pods for 15 minutes.
   - `sep.release.canary_check` compares the canary's 5xx ratio with the stable pods' each minute. It rolls back when
     the Wilson lower bound of the canary's ratio is above the upper bound of the stable pods' ratio, or when the
     canary's mean render time is more than 25% and 150 ms worse.
3. **The cache is left alone.** A release never flushes it.

## Consequences

- **Short is the cost.** A release takes at least 15 minutes. A defect that shows only at low traffic can pass the
  canary.
- **Measured:** `platform_no_sonar_gate` and `platform_no_canary`.
