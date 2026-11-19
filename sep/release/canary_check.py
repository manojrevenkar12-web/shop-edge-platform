"""Canary analysis against Prometheus, run by the Jenkins pipeline while a Rollout pauses at 10%.

Every minute it reads the canary's and the stable pods' 5xx and request counts and their mean render time, feeds
them to `Canary.observe`, and exits 0 to promote or 1 to abort (Jenkins then runs `kubectl argo rollouts abort`).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

from sep.config import load
from sep.release.gates import Canary

Q = {
    "bad": 'sum(increase(shop_page_views_total{{code=~"5..",rollouts_pod_template_hash="{h}"}}[1m]))',
    "n": 'sum(increase(shop_page_views_total{{rollouts_pod_template_hash="{h}"}}[1m]))',
    "ms": ('sum(increase(shop_render_seconds_sum{{rollouts_pod_template_hash="{h}"}}[1m])) * 1000 / '
           'sum(increase(shop_render_seconds_count{{rollouts_pod_template_hash="{h}"}}[1m]))'),
}


def query(base: str, expr: str) -> float:
    url = f"{base}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.load(r)["data"]["result"]
    return float(data[0]["value"][1]) if data else 0.0


def analyse(fetch, canary: Canary, sleep=time.sleep) -> str:
    """fetch(kind, which) -> float, which in {'canary', 'stable'}"""
    while True:
        v = canary.observe(fetch("bad", "canary"), fetch("n", "canary"), fetch("bad", "stable"), fetch("n", "stable"),
                           fetch("ms", "canary"), fetch("ms", "stable"))
        if v != "continue":
            return v
        sleep(60)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - runs in Jenkins against a cluster
    ap = argparse.ArgumentParser()
    ap.add_argument("--prometheus", required=True)
    ap.add_argument("--canary-hash", required=True)
    ap.add_argument("--stable-hash", required=True)
    a = ap.parse_args(argv)
    rel = load("platform")["release"]
    hashes = {"canary": a.canary_hash, "stable": a.stable_hash}
    verdict = analyse(lambda k, w: query(a.prometheus, Q[k].format(h=hashes[w])),
                      Canary(rel["canary_weight"], rel["canary_minutes"]))
    print(f"canary analysis: {verdict}")
    return 0 if verdict == "promote" else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
