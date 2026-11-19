"""Cloud spend per service from the billing export, and what to do about it.

Rows look like BigQuery's billing export (service, sku, labels.service, usage, cost); the platform labels every
workload with `service`, so cost lands on the team that runs it. Recommendations are computed from usage the
platform already scrapes: a replica floor far above what the night needs, and traffic that could be cached.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Recommendation:
    service: str
    action: str
    monthly_eur: float


def by_service(rows: list[dict], days: float) -> dict[str, float]:
    """Monthly cost per labelled service (30-day month)."""
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[r["labels"].get("service", "unlabelled")] += r["cost"]
    return {k: round(v * 30 / days, 2) for k, v in sorted(out.items())}


def recommendations(pods_by_minute: list[int], floor: int, pod_hour_eur: float, cache_hit_ratio: float,
                    days: float) -> list[Recommendation]:
    recs = []
    night = sorted(pods_by_minute[i] for i in range(len(pods_by_minute)) if (i // 60) % 24 < 6)
    if night:
        p95 = night[int(len(night) * 0.95)]
        if floor > p95 * 1.5:
            hours = 6 * 30
            recs.append(Recommendation("shop-php", f"lower minReplicas from {floor} to {max(p95, 2)}",
                                       round((floor - max(p95, 2)) * hours * pod_hour_eur, 0)))
    if cache_hit_ratio < 0.9:
        recs.append(Recommendation("varnish", f"cache hit ratio {cache_hit_ratio:.0%}: strip marketing parameters "
                                              "and analytics cookies before hashing", 0.0))
    return recs
