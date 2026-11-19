"""Autoscaler, alerts, release gates and FinOps on their own."""
import math

import pytest

from sep.config import load
from sep.cost.finops import by_service, recommendations
from sep.release.canary_check import analyse
from sep.release.gates import Canary, quality_gate
from sep.scale.autoscaler import Autoscaler, Window
from sep.slo.burnrate import BurnRateAlerts, ThresholdAlert, build, rules_yaml


def test_rps_scaling_goes_up_at_once_and_down_slowly():
    a = Autoscaler("rps", 5.0, 4, 50, down_window=5)
    assert a.desired(0, 4, renders_per_second=60, cpu_utilisation=0) == 12
    downs = [a.desired(m, 12, renders_per_second=20, cpu_utilisation=0) for m in range(1, 7)]
    assert downs[0] == 12 and downs[-1] == 4


def test_tolerance_band_and_bounds():
    a = Autoscaler("rps", 5.0, 2, 10)
    assert a.desired(0, 4, renders_per_second=21, cpu_utilisation=0) == 4      # within 10%
    assert a.desired(1, 4, renders_per_second=500, cpu_utilisation=0) == 10    # max


def test_campaign_floor_raises_the_minimum_ahead_of_the_peak():
    a = Autoscaler("rps", 5.0, 4, 100, schedule=[Window(100, 200, 40)])
    assert a.desired(99, 4, 1, 0) == 4
    assert a.desired(100, 4, 1, 0) == 40


def test_cpu_scaling_averages_two_minutes():
    a = Autoscaler("cpu", 0.7, 3, 30)
    a.desired(0, 10, 0, 0.35)
    assert a.desired(1, 10, 0, 1.4) == math.ceil(10 * 0.875 / 0.7)


def _feed(alert, ratios, total=1000.0):
    pages = []
    for m, r in enumerate(ratios):
        p = alert.observe(m, r * total, total)
        if p:
            pages.append(p.minute)
    return pages


def test_a_short_blip_pages_the_threshold_rule_but_not_the_burn_rate():
    blip = [0.0005] * 120 + [0.05] * 6 + [0.0005] * 60
    slo = load("slo")
    burn = BurnRateAlerts(0.999, slo["burn_rate_windows"], "availability")
    thr = ThresholdAlert(0.01, 5, "availability")
    assert _feed(burn, blip) == []
    assert _feed(thr, blip) != []


def test_a_real_outage_pages_both():
    outage = [0.0005] * 60 + [0.08] * 40
    slo = load("slo")
    assert _feed(BurnRateAlerts(0.999, slo["burn_rate_windows"], "availability"), outage)
    assert _feed(ThresholdAlert(0.01, 5, "availability"), outage)
    assert len(build("burn_rate", slo)) == len(slo["slos"])


def test_generated_rules_are_committed():
    from sep.config import ROOT

    assert (ROOT / "ops" / "prometheus" / "rules.yml").read_text() == rules_yaml(load("slo"))


def test_quality_gate_reads_sonarqube():
    ok, why = quality_gate({"projectStatus": {"status": "OK", "conditions": []}})
    assert ok and why == []
    bad = {"projectStatus": {"status": "ERROR", "conditions": [
        {"metricKey": "new_reliability_rating", "status": "ERROR", "actualValue": "4", "errorThreshold": "1"}]}}
    ok, why = quality_gate(bad)
    assert not ok and why == ["new_reliability_rating=4 (limit 1)"]


def test_canary_rolls_back_a_clear_defect_and_promotes_a_healthy_build():
    bad = Canary(minutes=15)
    assert [bad.observe(30, 300, 5, 2700) for _ in range(2)][-1] == "rollback"
    good = Canary(minutes=3)
    assert [good.observe(1, 300, 9, 2700) for _ in range(3)] == ["continue", "continue", "promote"]


def test_canary_catches_a_slow_build():
    c = Canary(minutes=15)
    assert c.observe(0, 300, 0, 2700, canary_ms=1100, base_ms=450) == "rollback"


def test_canary_check_loop_with_a_fake_prometheus():
    data = {("bad", "canary"): 40.0, ("n", "canary"): 300.0, ("bad", "stable"): 3.0, ("n", "stable"): 2700.0,
            ("ms", "canary"): 450.0, ("ms", "stable"): 440.0}
    assert analyse(lambda k, w: data[(k, w)], Canary(), sleep=lambda s: None) == "rollback"


def test_finops_per_service_and_floor_advice():
    rows = [{"labels": {"service": "shop-php"}, "cost": 70.0}, {"labels": {"service": "varnish"}, "cost": 14.0},
            {"labels": {}, "cost": 1.0}]
    assert by_service(rows, days=7) == {"shop-php": 300.0, "unlabelled": 4.29, "varnish": 60.0}
    pods = [4] * 360 + [20] * 1080
    recs = recommendations(pods, floor=18, pod_hour_eur=0.19, cache_hit_ratio=0.6, days=1)
    assert recs[0].action == "lower minReplicas from 18 to 4" and recs[0].monthly_eur == pytest.approx(479.0)
    assert recs[1].service == "varnish"


def test_budget_form_pages_for_an_evening_burst_the_ratio_form_lets_pass():
    """Night traffic is a fifth of the evening's; the same error ratio costs five times the budget in the evening."""
    slo = load("slo")
    day = [200.0] * 1080 + [1000.0] * 360                       # quiet day, busy evening
    bad = [0.0] * len(day)
    for m in range(1380, 1386):                                   # six minutes at 9% in the evening
        bad[m] = 0.09 * day[m]
    ratio = BurnRateAlerts(0.999, slo["burn_rate_windows"], "availability", "ratio")
    budget = BurnRateAlerts(0.999, slo["burn_rate_windows"], "availability", "budget")
    r_pages = [m for m in range(len(day)) if ratio.observe(m, bad[m], day[m])]
    b_pages = [m for m in range(len(day)) if budget.observe(m, bad[m], day[m])]
    assert b_pages and not r_pages
