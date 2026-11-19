"""Every design on the same shops, scored, with 95% intervals from resampling days (paired across designs)."""
from __future__ import annotations

import math
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from sep.config import load, world_config
from sep.keyed import rng
from sep.sim.designs import BY_NAME, ORDER
from sep.sim.engine import false_pages, mttd, run
from sep.world import MIN_PER_DAY, World

B = 1000


def run_seed(args) -> dict:
    cfg, seed, names = args
    w = World(cfg, seed)
    out = {"seed": seed, "days": cfg["days"], "designs": {}, "bf_series": {}}
    for name in names:
        keep = name in ("shop_as_found", "short_ttl", "platform")
        r = run(w, BY_NAME[name], keep_series=keep)
        out["designs"][name] = {
            "views": r.views, "errors": r.errors, "slow": r.slow, "cache": r.served_from_cache,
            "wrong": r.wrong_price_views, "oversold": r.oversold_orders, "lost": r.lost_orders,
            "pod_minutes": r.pod_minutes, "peak_pods": r.peak_pods, "cost_eur": r.cost_eur,
            "bf_views": r.bf_views, "bf_errors": r.bf_errors, "bf_slow": r.bf_slow,
            "pages": len(r.pages), "episodes": len(r.episodes),
            "detected": sum(e.detected_at is not None for e in r.episodes),
            "mttd": mttd(r.episodes), "false_pages": false_pages(r.pages, r.episodes),
            "bad_builds": r.bad_builds, "blocked": r.blocked_by_gate, "canary_caught": r.caught_by_canary,
            "reached_everyone": r.reached_everyone, "defect_minutes_full": r.defect_minutes_full,
            "daily": r.daily,
        }
        if keep:
            s0 = (w.bf_start - 6 * 60) // 5
            out["bf_series"][name] = {k: v[s0: s0 + (MIN_PER_DAY + 6 * 60) // 5] for k, v in r.series.items()}
    out["world"] = {"pages": w.cat.n, "deploys": len(w.deploys),
                    "defective_builds": sum(d.defect is not None for d in w.deploys),
                    "incidents": len(w.incidents), "blips": len(w.blips),
                    "changes": sum(len(v) for v in w.changes.values())}
    return out


def run_all(heldout: bool = False, days: int | None = None, workers: int | None = None, names: list[str] | None = None):
    cfg = world_config(heldout)
    if days:
        cfg["days"] = days
        cfg["black_friday_day"] = min(cfg["black_friday_day"], days - 1)
    names = names or ORDER
    workers = workers or max(1, min(len(cfg["seeds"]), os.cpu_count() or 1))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(run_seed, [(cfg, s, names) for s in cfg["seeds"]]))


def _ci(x: np.ndarray, d: int = 4) -> list[float]:
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [round(float(lo), d), round(float(hi), d)]


def summarize(results: list[dict]) -> dict:
    names = [n for n in ORDER if n in results[0]["designs"]]
    days = sum(r["days"] for r in results)
    order_value = load("value")["order_value_eur"]
    month = 30 / (days / len(results))            # scale one seed's window to a month
    blocks = [(i, dd) for i, r in enumerate(results) for dd in range(r["days"])]
    idx = rng("bootstrap", len(blocks)).integers(0, len(blocks), size=(B, len(blocks)))

    def daily(name: str, key: str) -> np.ndarray:
        return np.array([results[i]["designs"][name]["daily"][key][dd] for i, dd in blocks])

    out = {}
    for n in names:
        tot = {k: sum(r["designs"][n][k] for r in results) for k in
               ("views", "errors", "slow", "cache", "wrong", "oversold", "lost", "pod_minutes", "cost_eur", "bf_views",
                "bf_errors", "bf_slow", "pages", "episodes", "detected", "false_pages", "bad_builds", "blocked",
                "canary_caught", "reached_everyone", "defect_minutes_full")}
        v, e, wr, lo = daily(n, "views"), daily(n, "errors"), daily(n, "wrong"), daily(n, "lost")
        vb = v[idx].sum(1)
        mt = [r["designs"][n]["mttd"] for r in results if not math.isnan(r["designs"][n]["mttd"])]
        pod_hour = world_config()["prices"]["php_pod_hour_eur"]
        out[n] = {
            "label": BY_NAME[n].label,
            "availability": round(1 - tot["errors"] / tot["views"], 6),
            "availability_ci": _ci(1 - e[idx].sum(1) / vb, 6),
            "fast_share": round(1 - tot["slow"] / tot["views"], 6),
            "bf_availability": round(1 - tot["bf_errors"] / tot["bf_views"], 6) if tot["bf_views"] else None,
            "bf_fast_share": round(1 - tot["bf_slow"] / tot["bf_views"], 6) if tot["bf_views"] else None,
            "hit_ratio": round(tot["cache"] / tot["views"], 4),
            "wrong_per_100k": round(tot["wrong"] / tot["views"] * 1e5, 2),
            "wrong_ci": _ci(wr[idx].sum(1) / vb * 1e5, 2),
            "oversold_per_month": round(tot["oversold"] / len(results) * month, 1),
            "lost_orders_per_month": round(tot["lost"] / len(results) * month, 1),
            "lost_orders_ci": _ci(lo[idx].sum(1) / len(results) * month, 1),
            "lost_revenue_per_month": round(tot["lost"] / len(results) * month * order_value, -1),
            "compute_eur_per_month": round(tot["pod_minutes"] / 60 * pod_hour / len(results) * month, 0),
            "cost_eur_per_month": round(tot["cost_eur"] / len(results) * month, 0),
            "peak_pods": max(r["designs"][n]["peak_pods"] for r in results),
            "pages": tot["pages"], "episodes": tot["episodes"], "detected": tot["detected"],
            "mttd_minutes": round(float(np.mean(mt)), 1) if mt else None,
            "false_pages_per_week": round(tot["false_pages"] / (days / 7), 2),
            "bad_builds": tot["bad_builds"], "blocked_by_gate": tot["blocked"], "caught_by_canary": tot["canary_caught"],
            "reached_everyone": tot["reached_everyone"],
            "defect_hours_full": round(tot["defect_minutes_full"] / 60, 1),
        }
    world = {k: sum(r["world"][k] for r in results) for k in results[0]["world"]}
    world["seeds"] = [r["seed"] for r in results]
    world["days"] = days
    world["views"] = round(sum(r["designs"][names[0]]["views"] for r in results))
    return {"world": world, "designs": out}
