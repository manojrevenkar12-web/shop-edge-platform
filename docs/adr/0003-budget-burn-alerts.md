# 0003. Burn alerts measured in error budget, not in ratio

## Status

Accepted, but not yet shown to work. On the held-out shops these alerts paged for 0 of 5 episodes
([docs/heldout.md](../heldout.md)). This decision replaces the ratio form, which is kept as the
`platform_ratio_burn_alerts` ablation.

## Context

- **The ratio form.** The workbook's multi-window alert fires when the error ratio over 1 hour exceeds
  14.4 × (1 − SLO), and over 5 minutes too. That works when traffic is flat.
- **This shop's traffic is not flat.**
  - Night traffic is a tenth of the evening's.
  - A night incident has a high ratio but costs little budget.
  - An evening problem worth a page costs a lot of budget. Yet it can pass under the ratio threshold, because an
    hour of evening traffic dilutes a short burst.
- **What the first development run showed** (with the scoring later found to be wrong):
  - With the ratio form, the platform paged for only 2 of 5 page-worthy episodes.
  - With threshold alerts it paged for all 5, but woke someone for blips.

## Decision

- **Count bad events, not ratios.** Alert when the bad events in the window exceed `burn × window × budget per
  minute`. The budget per minute is the last day's traffic × (1 − SLO) / 1440.
- **Use the workbook's windows and factors:** 60 and 5 minutes at 14.4; 360 and 30 minutes at 6.
- **"Page-worthy" is defined the same way.** An episode is page-worthy if it spends at least 2% of its SLO's
  monthly budget (`config/slo.yaml`). Detection is measured against that definition.
  - Until the held-out run, the scoring counted slow pages against the availability budget. That was the bug the
    held-out run exposed; see [docs/heldout.md](../heldout.md).

## Consequences

- **Pages follow cost.** An evening burst pages and a night blip does not, because pages track what customers lost.
- **Rules are generated.** The recording rules need a day of history (`increase(total[1d])`); the `promtool` tests
  start with a clean day.
- **Assumption.** "Budget per minute" uses the last day as the guide for the month, which is wrong for a few hours
  after a traffic change. The 5-minute window still has to agree, which keeps false pages down.
