"""The designs compared on the same shop, the same traffic, the same incidents and the same builds. Each ablation
switches off exactly one safeguard of the platform, so every difference traces back to one decision."""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Design:
    name: str
    label: str
    ttl: str = "long"                # long (a day, purges keep it right) | short (minutes, no purges)
    purge: str = "precise"           # precise | broad | flush | none
    strip: str = "all"               # all marketing parameters | utm (utm_* only)
    cookies: bool = True             # strip analytics and consent cookies before the cache decides
    grace: bool = True               # serve stale while refreshing, and while the shop is down
    flush_on_deploy: bool = False    # a release empties the cache
    warm: bool = True                # fetch the most viewed pages after a mass purge or a flush
    scaling: str = "rps"             # rps (renders per pod) | cpu (utilisation, with a high floor)
    prescale: bool = True            # raise the floor ahead of known campaigns
    alerts: str = "budget_burn"      # budget_burn (error-budget minutes) | burn_rate (ratio) | threshold
    sonar_gate: bool = True          # SonarQube quality gate blocks the build
    canary: bool = True              # 10% for 15 minutes, analysed, before everyone


PLATFORM = Design("platform", "Platform: tag purges, grace, RPS scaling, burn-rate alerts, gates")
AS_FOUND = Design("shop_as_found", "Shop as found: broad bans, flush on release, CPU scaling, threshold alerts",
                  purge="broad", strip="utm", cookies=False, grace=False, flush_on_deploy=True, warm=False,
                  scaling="cpu", prescale=False, alerts="threshold", sonar_gate=False, canary=False)
SHORT_TTL = Design("short_ttl", "Five-minute TTL instead of purges",
                   ttl="short", purge="none", strip="utm", cookies=False, grace=False, warm=False, scaling="cpu",
                   prescale=False, alerts="threshold", sonar_gate=False, canary=False)

DESIGNS: list[Design] = [
    AS_FOUND,
    SHORT_TTL,
    replace(PLATFORM, name="platform_broad_bans", label="Platform, broad category bans", purge="broad"),
    replace(PLATFORM, name="platform_utm_only", label="Platform, only utm_* stripped", strip="utm"),
    replace(PLATFORM, name="platform_keeps_cookies", label="Platform, analytics cookies bypass the cache",
            cookies=False),
    replace(PLATFORM, name="platform_no_grace", label="Platform, no grace", grace=False),
    replace(PLATFORM, name="platform_flush_on_deploy", label="Platform, release flushes the cache",
            flush_on_deploy=True),
    replace(PLATFORM, name="platform_no_warm", label="Platform, no cache warming", warm=False),
    replace(PLATFORM, name="platform_cpu_scaling", label="Platform, CPU scaling with a high floor", scaling="cpu"),
    replace(PLATFORM, name="platform_no_prescale", label="Platform, no campaign prescale", prescale=False),
    replace(PLATFORM, name="platform_threshold_alerts", label="Platform, threshold alerts", alerts="threshold"),
    replace(PLATFORM, name="platform_ratio_burn_alerts", label="Platform, ratio burn-rate alerts", alerts="burn_rate"),
    replace(PLATFORM, name="platform_no_sonar_gate", label="Platform, no SonarQube gate", sonar_gate=False),
    replace(PLATFORM, name="platform_no_canary", label="Platform, no canary", canary=False),
    PLATFORM,
]
BY_NAME = {d.name: d for d in DESIGNS}
ORDER = [d.name for d in DESIGNS]
