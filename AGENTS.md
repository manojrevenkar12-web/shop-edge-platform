# AGENTS.md

How to work in this repository, for people and for coding agents.

## Fast feedback

- `python -m pytest`: everything, about a minute. The VCL tests need `varnishd`, otherwise they are skipped.
- `python -m sep.eval.cli quick`: three designs on three days.
- `ruff check .`, and in `web/` run `pnpm build`.
- `promtool test rules ops/prometheus/rules_test.yml`.

## Invariants

1. **The truth stays in the world.**
   - `sep/world` holds the shop.
   - The platform's components (`sep/edge`, `sep/scale`, `sep/slo`, `sep/release`, `sep/cost`) never import
     `sep.world` or `sep.sim`.
   - They get what production would give them: change messages, metrics, SonarQube reports and billing rows.
2. **The world does not read the platform's settings.** It reads `config/world.yaml` (and the held-out overlay)
   only.
3. **Same luck for every design.** Every draw is keyed by what it is about (`sep/keyed.py`), so every design meets
   the same page views, changes, incidents and broken builds.
4. **One source for each rule.**
   - Cache-key rules are in `sep/edge/keys.py`, mirrored in the VCL, and a test checks the two match.
   - Prometheus rules are generated from `config/slo.yaml`; CI fails if the committed ones differ.
5. **Settings in config.** TTLs, grace, floors, campaigns, SLOs and gates live in `config/*.yaml`.
6. **Generated reports.**
   - `reports/`, the charts, the README results block and `deploy/k8s/base/slo-rules.yaml` are written by
     `sep.eval.cli`.
   - CI re-runs the development evaluation and fails if the committed reports differ.

## The held-out rule

- The held-out shops (`config/heldout.yaml`) are run once with `python -m sep.eval.cli heldout`. The run writes
  `config/heldout.lock`, and the command refuses to run again.
- Tune on the development shops only.
- A change made after the run is written up in `docs/heldout.md`; the held-out numbers are not re-run.
