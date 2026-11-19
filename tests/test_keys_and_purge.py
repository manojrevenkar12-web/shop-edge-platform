import numpy as np
import pytest

from sep.edge.keys import MARKETING, UTM_ONLY, cacheable, fragmenting_share, normalize
from sep.edge.purge import Ban, Change, PurgePlanner, warm_list, warm_order


def test_marketing_parameters_do_not_split_the_cache():
    a = normalize("https://WWW.Lampshop.example/lamps/arc-floor?gclid=Cj0KCQ&utm_source=google&color=black")
    b = normalize("https://www.lampshop.example/lamps/arc-floor?color=black&fbclid=IwAR2")
    assert a == b == "https://www.lampshop.example/lamps/arc-floor?color=black"


def test_utm_only_stripping_leaves_ad_clicks_unique():
    u = "https://shop.example/p/1?gclid=abc&utm_medium=cpc"
    assert "gclid=abc" in normalize(u, UTM_ONLY)
    assert fragmenting_share({"utm": 0.5, "gclid": 0.3, "fbclid": 0.2}, UTM_ONLY) == pytest.approx(0.5)
    assert fragmenting_share({"utm": 0.5, "gclid": 0.3, "fbclid": 0.2}, MARKETING) == 0


@pytest.mark.parametrize(("cookie", "ok"), [
    (None, True),
    ("_ga=GA1.2.3; _gid=GA1.2.4; OptanonConsent=x", True),
    ("_ga=GA1.2.3; PHPSESSID=abc", False),
    ("cart_id=9", False),
])
def test_analytics_cookies_are_stripped_session_cookies_bypass(cookie, ok):
    assert cacheable(cookie) is ok


def test_without_stripping_any_cookie_bypasses():
    assert cacheable("_ga=GA1", strip_analytics=False) is False


def test_precise_bans_only_the_product_and_its_listings():
    p = PurgePlanner("precise")
    assert p.plan([Change("price", 12)]) == [Ban(("p-12", "l-12"))]


def test_broad_bans_take_whole_categories():
    p = PurgePlanner("broad", {12: [3, 7]})
    assert p.plan([Change("stock", 12, False)])[0].tags == ("p-12", "c-3", "c-7")


def test_bans_are_batched_and_deduplicated():
    p = PurgePlanner("precise", max_tags=4)
    bans = p.plan([Change("price", i) for i in (1, 2, 1, 3)])
    assert [b.tags for b in bans] == [("p-1", "l-1", "p-2", "l-2"), ("p-3", "l-3")]
    assert bans[0].expression == 'obj.http.X-Cache-Tags ~ "(^|,)(p-1|l-1|p-2|l-2)(,|$)"'


def test_flush_and_none():
    assert PurgePlanner("flush").plan([Change("price", 1)]) == [Ban(("*",))]
    assert PurgePlanner("flush").plan([Change("price", 1)])[0].expression == "obj.status != 0"
    assert PurgePlanner("none").plan([Change("price", 1)]) == []


def test_warming_starts_with_what_people_ask_for():
    assert warm_list({"/a": 3, "/b": 9, "/c": 1}, 2) == ["/b", "/a"]
    counts = np.array([5.0, 0.0, 9.0, 1.0])
    assert list(warm_order(counts, np.array([0, 2, 3]), 2)) == [2, 0]


def test_a_tag_with_regex_characters_is_refused():
    import pytest

    from sep.edge.purge import Ban
    with pytest.raises(ValueError):
        Ban(("p-1|.*",))
    assert Ban(("p-1", "l-22")).header == "(^|,)(p-1|l-22)(,|$)"
