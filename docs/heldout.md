# Held-out run

The held-out shops are seeds 8201, 8202 and 8203 (`config/heldout.yaml`). They are run once with
`python -m sep.eval.cli heldout`, which writes `config/heldout.lock` and refuses to run again.

## Record

**Run.** 2026-11-19, once; `config/heldout.lock` holds the time and the config hash.

**Result: the gate did not pass.**

- **Detection failed.** The platform paged for **0 of 5** page-worthy episodes; the gate asks for 90%. It also
  paged 0 times in all, so it sent no false pages.
- **Everything else in the gate passed:**
  - availability, overall and on Black Friday;
  - stale prices;
  - no broken build reaching everyone;
  - false pages.
- **Threshold alerts did better.** The `platform_threshold_alerts` ablation paged for 5 of 5, with no false pages, on
  these shops. On the development shops it had sent 0.8 false pages a week.

These numbers are in `reports/heldout.json` and in the README exactly as they came out. They are not re-run.

## Why, as far as the development shops show

I did not open the held-out runs to look; this diagnosis comes from the development shops.

- **What the scoring did.** It called a stretch of bad minutes "page-worthy" if its error views plus slow views
  passed 2% of the **availability** budget (0.1% of views).
- **What the alerts do.** They judge errors against the availability budget, and slow pages against the
  **latency** budget (1% of views), as `config/slo.yaml` defines them.
- **The mismatch.** A stretch made mostly of slow pages looked worth a page to the scoring. It had used only a tenth of
  that share of its own budget, so the alerts rightly stayed quiet.
- **On the development shops** most episodes were error-heavy, so the mismatch did not show.

So two things were wrong:

- the scoring was inconsistent with the SLOs it claims to measure;
- I tuned the alerts on three shops whose episodes happened not to expose that.

## Changes made after the run

1. **Scoring.** An episode is page-worthy if its errors spend 2% of the availability budget, or its slow pages spend
   2% of the latency budget (`sep/sim/engine.py`, `_episodes`).
   - The development numbers in the README were re-run with this definition.
   - The held-out numbers were not, and they still use the old one.

The alerts and the platform's components were not changed after the run.

## What it would take to claim the alerts work

A new set of held-out shops, run once, with the corrected scoring. This repository does not make that claim.
