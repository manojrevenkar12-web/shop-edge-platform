"""The shop's runtime, minute by minute: page views meet the cache, misses meet the PHP pods, pods meet incidents
and releases, and each design's real components decide what happens (sep/edge, sep/scale, sep/slo, sep/release).

This is the evaluation harness. It may read the truth (prices, stock, which build is broken) to score the minute;
the components only get what production would give them: change messages, metrics and SonarQube reports.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from sep.config import load
from sep.edge.keys import MARKETING, UTM_ONLY, fragmenting_share
from sep.edge.purge import Change, PurgePlanner, warm_order
from sep.keyed import rng
from sep.release.gates import Canary, quality_gate
from sep.scale.autoscaler import Autoscaler, Window
from sep.sim.designs import Design
from sep.slo.burnrate import build as build_alerts
from sep.world import MIN_PER_DAY, World

SLOW_MS = 1500.0


@dataclass
class Episode:
    start: int
    end: int
    detected_at: int | None = None


@dataclass
class Result:
    design: str
    views: float = 0.0
    errors: float = 0.0
    slow: float = 0.0
    served_from_cache: float = 0.0
    wrong_price_views: float = 0.0
    oversold_orders: float = 0.0
    lost_orders: float = 0.0
    renders: float = 0.0
    pod_minutes: float = 0.0
    peak_pods: int = 0
    cost_eur: float = 0.0
    bf_views: float = 0.0
    bf_errors: float = 0.0
    bf_slow: float = 0.0
    pages: list[int] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    bad_builds: int = 0
    blocked_by_gate: int = 0
    caught_by_canary: int = 0
    reached_everyone: int = 0
    defect_minutes_full: int = 0
    series: dict = field(default_factory=dict)
    minute: dict = field(default_factory=dict)      # per-minute views, errors and slow views, for diagnosis
    daily: dict = field(default_factory=dict)       # per-day sums, for bootstrap intervals over days


class TagIndex:
    """Which cached pages carry which tags, as the shop's templates set them."""

    def __init__(self, world: World, scheme: str):
        c = world.cat
        self.c, self.scheme = c, scheme
        self.base_cat = c.shops
        self.base_prod = c.shops + c.shops * c.categories
        self.shop_cat = np.arange(c.shops) * c.categories
        self.shop_prod = np.arange(c.shops) * c.products
        self._cache: dict[str, np.ndarray] = {}

    def pages(self, tag: str) -> np.ndarray:
        if tag in self._cache:
            return self._cache[tag]
        kind, _, n = tag.partition("-")
        i = int(n)
        c = self.c
        if kind == "p":
            out = self.base_prod + self.shop_prod + i
        elif kind == "l":
            cats = c.product_categories[i]
            out = np.concatenate([self.base_cat + self.shop_cat + k for k in cats]) if cats else np.array([], int)
        elif kind == "c":
            parts = [self.base_cat + self.shop_cat + i]
            if self.scheme == "broad":   # product pages carry their categories' tags in this scheme
                parts += [self.base_prod + self.shop_prod + p for p in c.category_products[i]]
            out = np.concatenate(parts)
        else:
            raise ValueError(tag)
        self._cache[tag] = out
        return out


def _campaign_windows(world: World, cfg: dict) -> list[Window]:
    t0 = datetime.combine(world.start, datetime.min.time())
    out = []
    for c in cfg["autoscaling"]["campaigns"]:
        s = int((datetime.fromisoformat(c["start"]) - t0).total_seconds() // 60)
        e = int((datetime.fromisoformat(c["end"]) - t0).total_seconds() // 60)
        out.append(Window(s, e, int(c["min_replicas"])))
    return out


def run(world: World, d: Design, keep_series: bool = False) -> Result:
    pcfg = load("platform")
    slo = load("slo")
    w, cat = world, world.cat
    t = w.cfg["traffic"]
    o = w.origin
    res = Result(d.name)
    n_obj = cat.n
    seed = w.seed

    # -- the design's components -------------------------------------------------------------------------------
    ttl = pcfg["cache"]["ttl_minutes"] if d.ttl == "long" else pcfg["cache"]["short_ttl_minutes"]
    grace = pcfg["cache"]["grace_minutes"] if d.grace else 0
    planner = PurgePlanner(d.purge, {p: cs for p, cs in enumerate(cat.product_categories)},
                           pcfg["cache"]["max_tags_per_ban"])
    tags = TagIndex(w, d.purge)
    frag = fragmenting_share(t["params_seen"], MARKETING if d.strip == "all" else UTM_ONLY)
    a = pcfg["autoscaling"]
    if d.scaling == "rps":
        scaler = Autoscaler("rps", a["rps"]["target_renders_per_pod"], a["rps"]["min_replicas"],
                            a["rps"]["max_replicas"], a["down_window_minutes"],
                            _campaign_windows(w, pcfg) if d.prescale else [])
    else:
        scaler = Autoscaler("cpu", a["cpu"]["target_utilisation"], a["cpu"]["min_replicas"],
                            a["cpu"]["max_replicas"], a["down_window_minutes"],
                            _campaign_windows(w, pcfg) if d.prescale else [])
    alerts = build_alerts(d.alerts, slo)
    rel = pcfg["release"]

    # -- truth and cache state ----------------------------------------------------------------------------------
    P = cat.products
    price_ver = np.zeros(P, dtype=np.int64)
    in_stock = np.ones(P, dtype=bool)
    is_prod = cat.kind == 2
    is_cat = cat.kind == 1
    prod_of = np.where(is_prod, cat.item, 0)
    cat_of = np.where(is_cat, cat.item, 0)

    listing = price_ver[cat.category_products].sum(axis=1)

    def truth(idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """What a page shows if rendered now: a price signature and whether it says 'in stock'."""
        k = cat.kind[idx]
        tp = np.where(k == 2, price_ver[prod_of[idx]], np.where(k == 1, listing[cat_of[idx]], 0))
        return tp, np.where(k == 2, in_stock[prod_of[idx]], True)

    all_idx = np.arange(n_obj)
    cached = np.ones(n_obj, dtype=bool)                 # the shop has been running: the cache is warm
    cached_at = -rng(seed, "warm-start").integers(0, ttl, n_obj)
    snap_price, snap_stock = truth(all_idx)
    recent_views = w.rate[0] * cat.weight * 1440.0      # what varnishncsa saw in the last day
    hour_views = np.zeros(n_obj)
    cdf = np.cumsum(cat.weight)
    cdf[-1] = 1.0
    warm_queue = np.array([], dtype=np.int64)

    pods_ready = scaler.floor(0)
    pending: list[tuple[int, int]] = []                  # (ready_at, count)
    last_demand = w.rate[0] * 0.1
    last_util = 0.3

    deploys = {x.minute: x for x in w.deploys}
    live_defect = None            # (deploy, share of traffic on it)
    canary: Canary | None = None
    canary_deploy = None
    rollback_at: int | None = None
    noticed: set[str] = set()

    bad_minutes = np.zeros(w.minutes, dtype=bool)
    minute = {k: np.zeros(w.minutes) for k in ("views", "errors", "slow")}
    days = w.cfg["days"]
    daily = {k: np.zeros(days) for k in ("views", "errors", "slow", "cache", "wrong", "oversold", "lost", "pod_min")}
    keep = {"views": [], "errors": [], "pods": [], "hit": [], "slow": []} if keep_series else None
    pod_hour = w.prices["php_pod_hour_eur"] / 60.0
    priv, cook = t["private_share"], t["analytics_cookie_share"]
    fetch_s = 0.4 / 60.0          # share of a minute a refetch takes: views in that slice see the old page

    for m in range(w.minutes):
        # 1. catalogue changes arrive from the ERP; the planner turns them into bans
        ch = w.changes.get(m)
        if ch:
            priced = False
            for kind, p, stock_after in ch:
                if kind == "price":
                    price_ver[p] += 1
                    priced = True
                else:
                    in_stock[p] = stock_after
            if priced:
                listing = price_ver[cat.category_products].sum(axis=1)
            bans = planner.plan(Change(k, p, s) for k, p, s in ch)
            purged = []
            for b in bans:
                if b.tags == ("*",):
                    cached[:] = False
                    purged.append(np.arange(n_obj))
                else:
                    idx = np.concatenate([tags.pages(tg) for tg in b.tags])
                    cached[idx] = False
                    purged.append(idx)
            if d.warm and purged and len(ch) > 200:       # a mass change: warm what people will ask for first
                cand = np.unique(np.concatenate(purged))
                warm_queue = np.concatenate([warm_queue, warm_order(recent_views, cand,
                                                                    pcfg["cache"]["warm_pages"])])

        # 2. a release: quality gate, then canary or straight to everyone
        dep = deploys.get(m)
        if dep is not None:
            if dep.defect:
                res.bad_builds += 1
            ok, _ = quality_gate(w.sonar_report(dep))
            if d.sonar_gate and not ok:
                res.blocked_by_gate += 1
            else:
                if d.canary:
                    canary, canary_deploy = Canary(rel["canary_weight"], rel["canary_minutes"]), dep
                else:
                    if dep.defect:
                        live_defect = (dep, 1.0)
                        res.reached_everyone += 1
                    if d.flush_on_deploy:
                        cached[:] = False
                        if d.warm:
                            warm_queue = np.concatenate([warm_queue, warm_order(recent_views, np.arange(n_obj),
                                                                                pcfg["cache"]["warm_pages"])])
        if rollback_at is not None and m >= rollback_at:
            live_defect, rollback_at = None, None

        # 3. pods: scale-ups become ready after the start delay
        ready_now = sum(c for r_at, c in pending if r_at <= m)
        pending = [(r_at, c) for r_at, c in pending if r_at > m]
        pods_ready += ready_now
        target = scaler.desired(m, pods_ready + sum(c for _, c in pending), last_demand / 60.0, last_util)
        in_flight = pods_ready + sum(c for _, c in pending)
        if target > in_flight:
            pending.append((m + o["pod_start_minutes"], target - in_flight))
        elif target < pods_ready:
            pods_ready = target
        inc = w.incident_at(m)
        cap_factor = inc.capacity if inc else 1.0
        capacity = pods_ready * o["pod_rps"] * 60 * cap_factor

        # 4. page views this minute (the same draws for every design); only pages someone asked for are touched
        rv = rng(seed, "views", m)
        total = int(rv.poisson(w.rate[m]))
        hit_idx = np.searchsorted(cdf, rv.random(total))
        nz, cnt = np.unique(hit_idx, return_counts=True)
        rm = rng(seed, "mix", m)
        n_priv = rm.binomial(cnt, priv)
        rest = cnt - n_priv
        n_cook = rm.binomial(rest, cook)
        n_trk = rm.binomial(rest, w.tracked_share[m])
        n_frag = rng(seed, "frag", m).binomial(n_trk, frag)
        n_pass = np.minimum(n_priv + n_frag + (0 if d.cookies else n_cook), cnt).astype(np.float64)
        n_c = cnt - n_pass
        hour_views[nz] += cnt
        if m % 60 == 59:
            recent_views = recent_views * (23 / 24) + hour_views
            hour_views[:] = 0

        age = m - cached_at[nz]
        c_nz = cached[nz]
        fresh = c_nz & (age < ttl)
        stale_ok = c_nz & ~fresh & (age < ttl + grace)
        asked = n_c > 0
        fg = asked & ~fresh & ~stale_ok                 # the visitor waits for the shop
        bg = asked & stale_ok                           # served stale, refreshed in the background
        k_warm = min(len(warm_queue), pcfg["cache"]["warm_rate_per_minute"]) if d.warm else 0
        warm_now, warm_queue = warm_queue[:k_warm], warm_queue[k_warm:]
        demand = float(fg.sum() + bg.sum() + n_pass.sum() + k_warm)

        # 5. the origin: overload, incidents, blips, a broken build
        util = demand / capacity if capacity > 0 else 10.0
        fail_overload = max(0.0, (demand - capacity) / demand) if demand > 0 else 0.0
        blip = w.blip_at(m)
        app_err = o["noise_error_rate"] + (blip.error_rate if blip else 0.0)
        defect_err, defect_ms, defect_share = 0.0, 0.0, 0.0
        if live_defect:
            dep_, share = live_defect
            defect_err, defect_ms, defect_share = dep_.error_rate, dep_.latency_ms, share
        if canary is not None and canary_deploy is not None and canary_deploy.defect:
            defect_err, defect_ms, defect_share = canary_deploy.error_rate, canary_deploy.latency_ms, canary.weight
        p_err = 1 - (1 - fail_overload) * (1 - app_err) * (1 - defect_err * defect_share)
        origin_ms = o["base_latency_ms"] * (1 + 2.0 * min(util, 1.6) ** 3) + defect_ms * defect_share
        if inc and inc.kind == "search_cluster_slow":
            origin_ms += 600

        ok_fetch = rng(seed, "fetch", m).random(len(nz)) >= p_err
        fg_ok = fg & ok_fetch
        fg_fail = fg & ~ok_fetch
        is_p = cat.kind[nz] == 2

        views = float(cnt.sum())
        pass_sum = float(n_pass.sum())
        err_views = float((n_c * fg_fail).sum()) + pass_sum * p_err
        origin_views = float((n_c * fg_ok).sum()) + pass_sum * (1 - p_err)
        served = fresh | stale_ok
        cache_views = float((n_c * served).sum())
        slow_views = origin_views if origin_ms > SLOW_MS else 0.0

        # wrong prices and stock shown from the cache (a refetch takes a moment, so stale-while-revalidate shows the
        # old page to the views in that moment, and to all of them while the shop cannot answer)
        tp, ts = truth(nz)
        stale_page = served & (snap_price[nz] != tp)
        wr = float((n_c * stale_page * fresh).sum() + (n_c * stale_page * stale_ok * np.where(ok_fetch, fetch_s, 1.0)).sum())
        res.wrong_price_views += wr
        daily["wrong"][m // MIN_PER_DAY] += wr
        oos_shown = served & is_p & snap_stock[nz] & ~ts
        ov = float((n_c * oos_shown).sum()) * t["conversion"]
        lo = (float((n_c * fg_fail * is_p).sum()) + float((n_pass * is_p).sum()) * p_err) * t["conversion"]
        res.oversold_orders += ov
        res.lost_orders += lo
        daily["oversold"][m // MIN_PER_DAY] += ov
        daily["lost"][m // MIN_PER_DAY] += lo

        # 6. successful fetches refresh the cache
        ref = nz[fg_ok | (bg & ok_fetch)]
        if k_warm:
            ok_w = rng(seed, "warmfetch", m).random(k_warm) >= p_err
            ref = np.concatenate([ref, warm_now[ok_w]])
        if len(ref):
            cached[ref] = True
            cached_at[ref] = m
            snap_price[ref], snap_stock[ref] = truth(ref)

        # 7. bookkeeping, metrics, alerts
        dd = m // MIN_PER_DAY
        daily["views"][dd] += views
        daily["errors"][dd] += err_views
        daily["slow"][dd] += slow_views
        daily["cache"][dd] += cache_views
        daily["pod_min"][dd] += pods_ready + sum(c for _, c in pending)
        res.views += views
        res.errors += err_views
        res.slow += slow_views
        res.served_from_cache += cache_views
        res.renders += demand
        res.pod_minutes += pods_ready + sum(c for _, c in pending)
        res.peak_pods = max(res.peak_pods, pods_ready)
        if w.bf_start <= m < w.bf_start + MIN_PER_DAY:
            res.bf_views += views
            res.bf_errors += err_views
            res.bf_slow += slow_views
        last_demand, last_util = demand, min(util, 1.5)
        bad_minutes[m] = (err_views / views > 0.005 or slow_views / views > 0.05) if views else False
        minute["views"][m], minute["errors"][m], minute["slow"][m] = views, err_views, slow_views

        for al in alerts:
            if al.name == "availability":
                page = al.observe(m, err_views, views)
            else:
                page = al.observe(m, slow_views, views)
            if page:
                res.pages.append(m)
                if live_defect and rollback_at is None:
                    noticed.add(live_defect[0].build)
                    rollback_at = m + rel["rollback_after_page_minutes"] + rel["rollback_minutes"]

        if canary is not None:
            share_n = origin_views + err_views
            c_n, b_n = share_n * canary.weight, share_n * (1 - canary.weight)
            base_err = 1 - (1 - fail_overload) * (1 - app_err)
            c_err = 1 - (1 - base_err) * (1 - (canary_deploy.error_rate if canary_deploy.defect else 0.0))
            rc = rng(seed, "canary", m, canary_deploy.build)
            c_bad = rc.binomial(int(c_n), min(c_err, 1.0)) if c_n >= 1 else 0
            b_bad = rc.binomial(int(b_n), min(base_err, 1.0)) if b_n >= 1 else 0
            base_ms = o["base_latency_ms"] * (1 + 2.0 * min(util, 1.6) ** 3)
            verdict = canary.observe(c_bad, int(c_n), b_bad, int(b_n),
                                     base_ms + (canary_deploy.latency_ms if canary_deploy.defect else 0.0), base_ms)
            if verdict == "rollback":
                if canary_deploy.defect:
                    res.caught_by_canary += 1
                canary, canary_deploy = None, None
            elif verdict == "promote":
                if canary_deploy.defect:
                    live_defect = (canary_deploy, 1.0)
                    res.reached_everyone += 1
                if d.flush_on_deploy:
                    cached[:] = False
                    if d.warm:
                        warm_queue = np.concatenate([warm_queue, warm_order(recent_views, np.arange(n_obj),
                                                                            pcfg["cache"]["warm_pages"])])
                canary, canary_deploy = None, None
        if live_defect and live_defect[1] >= 1.0:
            res.defect_minutes_full += 1

        if keep is not None and m % 5 == 0:
            keep["views"].append(round(float(views)))
            keep["errors"].append(round(float(err_views), 1))
            keep["slow"].append(round(float(slow_views), 1))
            keep["pods"].append(int(pods_ready))
            keep["hit"].append(round(float(cache_views / views), 4) if views else 0)

    # cost: pods, the varnish nodes, egress (HTML from the load balancer, assets mostly from the CDN)
    pr = w.prices
    hours = w.minutes / 60
    egress = res.views * (pr["html_kb"] / 1e6 * pr["origin_egress_gb_eur"]
                          + pr["assets_kb_per_view"] / 1e6 * (pr["cdn_hit_assets"] * pr["cdn_egress_gb_eur"]
                                                             + (1 - pr["cdn_hit_assets"]) * pr["origin_egress_gb_eur"]))
    res.cost_eur = res.pod_minutes * pod_hour + pr["varnish_nodes"] * pr["varnish_node_hour_eur"] * hours + egress
    # each SLO is judged against its own budget: errors against availability's, slow pages against latency's
    month_views = float(w.rate.mean()) * 43200
    share = slo["page_worthy_budget_share"]
    worth = (month_views * (1 - slo["slos"]["availability"]["objective"]) * share,
             month_views * (1 - slo["slos"]["latency"]["objective"]) * share)
    res.minute = minute
    res.episodes = _episodes(bad_minutes, minute["errors"], minute["slow"], res.pages, worth)
    if keep is not None:
        res.series = keep
    res.daily = {k: [round(float(x), 3) for x in v] for k, v in daily.items()}
    return res


def _episodes(bad: np.ndarray, errors: np.ndarray, slow: np.ndarray, pages: list[int], worth: tuple[float, float],
              slack: int = 10) -> list[Episode]:
    """Stretches of bad minutes that burned enough of a monthly budget to deserve a page.

    `worth` is (error views, slow views): a stretch deserves a page if its errors spent that share of the
    availability budget, or its slow pages that share of the latency budget.
    """
    eps, m = [], 0
    while m < len(bad):
        if bad[m]:
            s = m
            while m < len(bad) and bad[m]:
                m += 1
            if errors[s:m].sum() >= worth[0] or slow[s:m].sum() >= worth[1]:
                det = next((p for p in pages if s - 2 <= p <= m + slack), None)
                eps.append(Episode(s, m, det))
        m += 1
    return eps


def false_pages(pages: list[int], episodes: list[Episode], slack: int = 15) -> int:
    return sum(1 for p in pages if not any(e.start - slack <= p <= e.end + slack for e in episodes))


def mttd(episodes: list[Episode]) -> float:
    xs = [e.detected_at - e.start for e in episodes if e.detected_at is not None]
    return float(np.mean(xs)) if xs else math.nan
