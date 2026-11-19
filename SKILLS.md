# SKILLS.md

## Strip another tracking parameter or cookie

1. Add it to `MARKETING` or `ANALYTICS_COOKIES` in `sep/edge/keys.py`, and add the same name to `edge/default.vcl`.
2. Check: `pytest tests/test_vcl.py`. It checks the lists match and runs the VCL in Varnish.

## Change what a price or stock change purges

1. Edit `PurgePlanner.tags_for` in `sep/edge/purge.py`.
2. If the shop's templates change their tags, edit `TagIndex` in `sep/sim/engine.py` too.
3. Run `python -m sep.eval.cli quick`.

## Add a campaign floor

1. Add a window under `autoscaling.campaigns` in `config/platform.yaml`.
2. Add the matching `cron` trigger in `deploy/k8s/base/scaling.yaml`.

## Change an SLO or the alert windows

1. Edit `config/slo.yaml`, then run `python -m sep.eval.cli rules`.
2. Run `promtool check rules ops/prometheus/rules.yml && promtool test rules ops/prometheus/rules_test.yml`.

## Add a design or an ablation

1. Add a `Design` in `sep/sim/designs.py` that removes exactly one safeguard.
2. Add it to `ORDER` in `web/src/shared/format.ts`.
3. Run `python -m sep.eval.cli evaluate`.

## Regenerate results

Run `python -m sep.eval.cli evaluate` (about ten minutes on two cores). Commit `reports/` and `README.md` together.

## Run the held-out shops (once)

Run `python -m sep.eval.cli heldout`. Commit `reports/heldout.json`, `config/heldout.lock` and `README.md`, and
record the run in `docs/heldout.md`.

## Deploy

1. In `infra/terraform`, run `terraform apply` with `project` and `billing_account` set.
2. Run `kustomize build --load-restrictor LoadRestrictionsNone deploy/k8s/base | kubectl apply -f -`.
3. Point Jenkins at `Jenkinsfile`, with SonarQube configured as `sonarqube`.
