"""The simulated shop: catalogue, traffic, catalogue changes, incidents, deploys and prices. The truth lives here.

The platform never imports this package. It sees what a real platform would see: change messages from the ERP,
page requests, metrics, SonarQube reports for each build, and the billing export.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from sep.keyed import rng

MIN_PER_DAY = 1440


@dataclass(frozen=True)
class Incident:
    start: int
    end: int
    kind: str
    capacity: float            # share of origin capacity left while it lasts


@dataclass(frozen=True)
class Blip:
    start: int
    end: int
    error_rate: float


@dataclass(frozen=True)
class Deploy:
    minute: int
    build: str
    defect: str | None
    error_rate: float = 0.0
    latency_ms: float = 0.0
    sonar_finds: bool = False    # truth: would static analysis flag this build's defect?


@dataclass
class Catalogue:
    shops: int
    products: int
    categories: int
    kind: np.ndarray            # 0 home, 1 category, 2 product
    shop: np.ndarray
    item: np.ndarray            # product id or category id within the shop (home: 0)
    weight: np.ndarray          # share of page views
    category_products: np.ndarray   # [categories, products_per_category] product ids listed on each category
    product_categories: list[list[int]] = field(default_factory=list)

    def index(self, kind: int, shop: int, item: int) -> int:
        if kind == 0:
            return shop
        if kind == 1:
            return self.shops + shop * self.categories + item
        return self.shops + self.shops * self.categories + shop * self.products + item

    @property
    def n(self) -> int:
        return len(self.kind)


def _zipf(n: int, s: float) -> np.ndarray:
    w = 1.0 / np.arange(1, n + 1) ** s
    return w / w.sum()


def build_catalogue(cfg: dict, seed: int) -> Catalogue:
    r = rng(seed, "catalogue")
    S, P, C, k = cfg["shops"], cfg["products"], cfg["categories"], cfg["products_per_category"]
    mix = cfg["traffic"]["page_mix"]
    shop_w = _zipf(S, 0.8)                         # Germany first, then the smaller country shops
    prod_rank = r.permutation(P)
    prod_w = _zipf(P, cfg["zipf_products"])[np.argsort(prod_rank)]
    cat_w = _zipf(C, cfg["zipf_categories"])
    kind = np.concatenate([np.zeros(S), np.ones(S * C), np.full(S * P, 2)]).astype(np.int8)
    shop = np.concatenate([np.arange(S), np.repeat(np.arange(S), C), np.repeat(np.arange(S), P)]).astype(np.int16)
    item = np.concatenate([np.zeros(S), np.tile(np.arange(C), S), np.tile(np.arange(P), S)]).astype(np.int32)
    weight = np.concatenate([mix["home"] * shop_w, mix["category"] * np.outer(shop_w, cat_w).ravel(),
                             mix["product"] * np.outer(shop_w, prod_w).ravel()])
    # categories list their products by popularity within a random subset
    cats = np.zeros((C, k), dtype=np.int32)
    pc: list[list[int]] = [[] for _ in range(P)]
    for c in range(C):
        members = r.choice(P, size=k, replace=False, p=prod_w)
        cats[c] = members
        for m in members:
            pc[m].append(c)
    return Catalogue(S, P, C, kind, shop, item, weight / weight.sum(), cats, pc)


class World:
    def __init__(self, cfg: dict, seed: int):
        self.cfg, self.seed = cfg, seed
        self.start = date.fromisoformat(str(cfg["start"]))
        self.minutes = cfg["days"] * MIN_PER_DAY
        self.cat = build_catalogue(cfg, seed)
        self.bf_start = cfg["black_friday_day"] * MIN_PER_DAY
        self.rate = self._traffic()
        self.tracked_share = np.where((np.arange(self.minutes) >= self.bf_start)
                                      & (np.arange(self.minutes) < self.bf_start + MIN_PER_DAY),
                                      cfg["traffic"]["tracked_share_sale"], cfg["traffic"]["tracked_share"])
        self.changes = self._changes()
        self.incidents, self.blips = self._incidents()
        self.deploys = self._deploys()
        self.prices = cfg["prices"]
        self.origin = cfg["origin"]

    # -- traffic ---------------------------------------------------------------------------------------------
    def _traffic(self) -> np.ndarray:
        t = self.cfg["traffic"]
        m = np.arange(self.minutes)
        hour = (m // 60) % 24
        frac = (m % 60) / 60
        d = np.array(t["diurnal"])
        curve = d[hour] * (1 - frac) + d[(hour + 1) % 24] * frac
        day = m // MIN_PER_DAY
        weekday = np.array([(self.start + timedelta(days=int(x))).weekday() for x in range(self.cfg["days"])])
        mult = np.where(weekday[day] >= 5, t["weekend"], 1.0)
        on_sale = (m >= self.bf_start) & (m < self.bf_start + MIN_PER_DAY)
        launch = np.exp(-((m - self.bf_start) / 70.0) ** 2) * 2.5
        mult = np.where(on_sale, mult * t["black_friday"], mult) + np.where(m >= self.bf_start - 30, launch, 0)
        r = rng(self.seed, "traffic-noise")
        noise = np.exp(r.normal(0, 0.05, self.minutes))
        return t["page_views_per_minute"] * curve * mult * noise

    def views(self, minute: int, r: np.random.Generator) -> np.ndarray:
        """Page views per page this minute (Poisson around its share of traffic)."""
        return r.poisson(self.rate[minute] * self.cat.weight)

    # -- catalogue changes -----------------------------------------------------------------------------------
    def _changes(self) -> dict[int, list[tuple[str, int, bool]]]:
        """minute -> [(kind 'price'|'stock', product, in_stock_after)]"""
        c = self.cfg["catalogue_changes"]
        r = rng(self.seed, "changes")
        P = self.cat.products
        pop = self.cat.weight[self.cat.index(2, 0, 0): self.cat.index(2, 0, 0) + P]
        pop = pop / pop.sum()
        mix = 0.6 * pop + 0.4 / P          # changes favour popular products a little
        out: dict[int, list] = {}
        for m in range(self.minutes):
            for kind, rate in (("price", c["price_changes_per_hour"]), ("stock", c["stock_changes_per_hour"])):
                n = r.poisson(rate / 60 * (0.3 if (m // 60) % 24 < 6 else 1.0))
                for p in r.choice(P, size=n, p=mix):
                    out.setdefault(m, []).append((kind, int(p), bool(r.random() > c["out_of_stock_share"])))
        for d in range(self.cfg["days"]):
            m = d * MIN_PER_DAY + 3 * 60
            for p in r.choice(P, size=min(P, c["nightly_price_batch"]), replace=False):
                out.setdefault(m, []).append(("price", int(p), True))
        for p in r.choice(P, size=min(P, c["sale_price_changes"]), replace=False, p=mix):
            out.setdefault(self.bf_start, []).append(("price", int(p), True))
        return out

    # -- incidents, blips, deploys ---------------------------------------------------------------------------
    def _incidents(self) -> tuple[list[Incident], list[Blip]]:
        cfg = self.cfg["incidents"]
        r = rng(self.seed, "incidents")
        n = r.poisson(cfg["per_week"] * self.cfg["days"] / 7)
        kinds = list(cfg["kinds"])
        w = np.array([cfg["kinds"][k]["weight"] for k in kinds])
        incs = []
        for _ in range(n):
            k = kinds[int(r.choice(len(kinds), p=w / w.sum()))]
            spec = cfg["kinds"][k]
            s = int(r.integers(0, self.minutes - 60))
            incs.append(Incident(s, s + int(r.integers(*spec["minutes"])), k, float(spec["capacity"])))
        # the sale evening always has one: the search cluster struggles at the peak
        s = self.bf_start + 20 * 60 + int(r.integers(0, 40))
        incs.append(Incident(s, s + 25, "search_cluster_slow", cfg["kinds"]["search_cluster_slow"]["capacity"]))
        blips = []
        for d in range(self.cfg["days"]):
            for _ in range(r.poisson(cfg["blips_per_day"])):
                s = d * MIN_PER_DAY + int(r.integers(0, MIN_PER_DAY - 5))
                blips.append(Blip(s, s + int(r.integers(*cfg["blip_minutes"])), float(r.uniform(*cfg["blip_error_rate"]))))
        return sorted(incs, key=lambda x: x.start), sorted(blips, key=lambda x: x.start)

    def _deploys(self) -> list[Deploy]:
        cfg = self.cfg["deploys"]
        r = rng(self.seed, "deploys")
        kinds = list(cfg["defects"])
        w = np.array([cfg["defects"][k]["weight"] for k in kinds])
        out = []
        n = 0
        for d in range(self.cfg["days"]):
            if (self.start + timedelta(days=d)).weekday() >= 5 or d == self.cfg["black_friday_day"]:
                continue                     # code freeze on weekends and on the sale day
            for _ in range(r.poisson(cfg["per_business_day"])):
                n += 1
                m = d * MIN_PER_DAY + int(r.integers(cfg["hour"][0] * 60, cfg["hour"][1] * 60))
                if r.random() < cfg["defect_rate"]:
                    k = kinds[int(r.choice(len(kinds), p=w / w.sum()))]
                    spec = cfg["defects"][k]
                    out.append(Deploy(m, f"b{n:03d}", k, float(r.uniform(*spec["error_rate"])) if "error_rate" in spec
                                      else 0.0, float(r.uniform(*spec["latency_ms"])) if "latency_ms" in spec else 0.0,
                                      bool(r.random() < spec["static_analysis_finds"])))
                else:
                    out.append(Deploy(m, f"b{n:03d}", None))
        return sorted(out, key=lambda x: x.minute)

    def sonar_report(self, d: Deploy) -> dict:
        """What SonarQube's quality-gate API returns for this build (the platform only sees this)."""
        bad = d.defect is not None and d.sonar_finds
        cond = [{"metricKey": "new_reliability_rating", "status": "ERROR" if bad else "OK",
                 "actualValue": "4" if bad else "1", "errorThreshold": "1", "comparator": "GT"},
                {"metricKey": "new_coverage", "status": "OK", "actualValue": "83.1", "errorThreshold": "80",
                 "comparator": "LT"}]
        return {"projectStatus": {"status": "ERROR" if bad else "OK", "conditions": cond}}

    def incident_at(self, m: int) -> Incident | None:
        for i in self.incidents:
            if i.start <= m < i.end:
                return i
        return None

    def blip_at(self, m: int) -> Blip | None:
        for b in self.blips:
            if b.start <= m < b.end:
                return b
        return None
