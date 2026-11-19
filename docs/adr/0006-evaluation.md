# 0006. How designs are compared

## Status

Accepted.

## Decision

- **Same luck.** Every design runs the same simulated shops (seeds) and meets the same visits, changes, incidents
  and broken builds. Draws are keyed by what they are about, not by order.
- **Development and held-out shops.** Three development shops tune the work. Three held-out shops are run once,
  behind a lock.
- **Uncertainty.** Intervals are bootstrapped over (shop, day) blocks, so a single bad day cannot look like a trend.
- **One headline.** Lost orders per month, at €96 an order, with stale-price views, cost and paging as separate
  columns. None of these is traded off into a single score.
- **The gate** (`config/gate.yaml`) is checked on the held-out shops. It covers availability overall and on Black
  Friday, stale prices, broken builds reaching everyone, false pages and detection.

## Consequences

The held-out numbers are the ones to quote. Changes made after the held-out run are listed in `docs/heldout.md`.
