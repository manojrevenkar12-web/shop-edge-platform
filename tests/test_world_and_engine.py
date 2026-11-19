from sep.config import load
from sep.sim.designs import AS_FOUND, BY_NAME, PLATFORM, SHORT_TTL
from sep.sim.engine import run
from sep.world import MIN_PER_DAY, World
from tests.conftest import small_config


def test_same_seed_same_shop(world):
    again = World(small_config(), 4242)
    assert (again.rate == world.rate).all()
    assert again.changes == world.changes and again.deploys == world.deploys and again.incidents == world.incidents


def test_black_friday_is_busier_and_frozen_for_releases():
    w = World(small_config(days=14, black_friday_day=11), 4243)
    bf = w.rate[w.bf_start: w.bf_start + MIN_PER_DAY].sum()
    day_before = w.rate[w.bf_start - MIN_PER_DAY: w.bf_start].sum()
    assert bf > 2 * day_before
    assert not any(w.bf_start <= d.minute < w.bf_start + MIN_PER_DAY for d in w.deploys)
    assert any(w.bf_start <= i.start < w.bf_start + MIN_PER_DAY for i in w.incidents)


def test_sonarqube_sees_only_what_static_analysis_can_find(world):
    for d in world.deploys:
        status = world.sonar_report(d)["projectStatus"]["status"]
        assert (status == "ERROR") == (d.defect is not None and d.sonar_finds)


def test_every_design_sees_the_same_views(world):
    a = run(world, AS_FOUND)
    p = run(world, PLATFORM)
    assert a.views == p.views
    assert p.served_from_cache > a.served_from_cache
    assert p.errors <= a.errors


def test_short_ttl_shows_old_prices_and_purges_do_not(world):
    s = run(world, SHORT_TTL)
    p = run(world, PLATFORM)
    assert s.wrong_price_views > 0
    assert p.wrong_price_views < s.wrong_price_views / 50


def test_flushing_on_release_costs_cache_hits(world):
    flush = run(world, BY_NAME["platform_flush_on_deploy"])
    p = run(world, PLATFORM)
    if any(not d.defect or not d.sonar_finds for d in world.deploys):
        assert flush.served_from_cache < p.served_from_cache


def test_settings_live_in_config():
    for name in ("platform", "slo", "gate", "value"):
        assert load(name)
