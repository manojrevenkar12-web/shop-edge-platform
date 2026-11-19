"""SLOs and the alerts that page for them, evaluated the way Prometheus evaluates the generated rules.

Multi-window burn-rate alerts (Google SRE workbook): page when the error budget burns fast over a long window and is
still burning over a short one, so a two-minute blip does not page and a real outage pages within minutes. The
threshold rule ("error ratio above 1% for 5 minutes") is the common alternative, kept to compare against.

`rules_yaml` writes ops/prometheus/rules.yml from config/slo.yaml; CI checks it with `promtool check rules` and
runs the unit tests in ops/prometheus/rules_test.yml with `promtool test rules`.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class Page:
    minute: int
    alert: str


class BurnRateAlerts:
    """Ratio burn rate (the workbook's form) or budget burn: the same windows, but measured in error-budget minutes
    of a month's traffic instead of as a ratio. A ratio treats a bad minute at 03:00 like one at 20:00; the budget
    form pages for what the month can afford, so it is more sensitive at the evening peak and quieter at night."""

    def __init__(self, objective: float, windows: list[dict], name: str, form: str = "ratio"):
        self.budget = 1 - objective
        self.windows = windows
        self.name = name
        self.form = form
        longest = max(max(w["long_minutes"] for w in windows), 1440)
        self.bad: deque = deque(maxlen=longest)
        self.total: deque = deque(maxlen=longest)
        self.firing = False

    def _ratio(self, minutes: int) -> float:
        b = list(self.bad)[-minutes:]
        t = list(self.total)[-minutes:]
        s = sum(t)
        return sum(b) / s if s else 0.0

    def _bad(self, minutes: int) -> float:
        return sum(list(self.bad)[-minutes:])

    def observe(self, minute: int, bad: float, total: float) -> Page | None:
        self.bad.append(bad)
        self.total.append(total)
        if self.form == "ratio":
            fire = any(self._ratio(w["long_minutes"]) > w["burn"] * self.budget
                       and self._ratio(w["short_minutes"]) > w["burn"] * self.budget for w in self.windows)
        else:
            month = sum(self.total) * 43200 / len(self.total)       # this month's traffic, from the last day
            per_minute = self.budget * month / 43200                 # budget a minute may spend
            fire = any(self._bad(w["long_minutes"]) > w["burn"] * per_minute * w["long_minutes"]
                       and self._bad(w["short_minutes"]) > w["burn"] * per_minute * w["short_minutes"]
                       for w in self.windows)
        page = Page(minute, self.name) if fire and not self.firing else None
        self.firing = fire
        return page


class ThresholdAlert:
    def __init__(self, ratio: float, for_minutes: int, name: str):
        self.ratio, self.for_minutes, self.name = ratio, for_minutes, name
        self.bad: deque = deque(maxlen=5)
        self.total: deque = deque(maxlen=5)
        self.over = 0
        self.firing = False

    def observe(self, minute: int, bad: float, total: float) -> Page | None:
        self.bad.append(bad)
        self.total.append(total)
        r = sum(self.bad) / sum(self.total) if sum(self.total) else 0.0
        self.over = self.over + 1 if r > self.ratio else 0
        fire = self.over >= self.for_minutes
        page = Page(minute, self.name) if fire and not self.firing else None
        self.firing = fire
        return page


def build(kind: str, slo: dict) -> list:
    """The paging rules for each SLO, as one design uses them."""
    out = []
    for name, s in slo["slos"].items():
        if kind in ("burn_rate", "budget_burn"):
            out.append(BurnRateAlerts(s["objective"], slo["burn_rate_windows"], name,
                                      "ratio" if kind == "burn_rate" else "budget"))
        else:
            out.append(ThresholdAlert(s["threshold_ratio"], slo["threshold_for_minutes"], name))
    return out


def rules_yaml(slo: dict) -> str:
    """Prometheus recording and alerting rules for the SLOs in config/slo.yaml."""
    groups = []
    for name, s in slo["slos"].items():
        rec, alerts = [], []
        bad, total = s["bad_expr"], s["total_expr"]
        for w in sorted({x["long_minutes"] for x in slo["burn_rate_windows"]}
                        | {x["short_minutes"] for x in slo["burn_rate_windows"]}):
            rec.append({"record": f"slo:{name}:bad_{w}m", "expr": f"sum(increase({bad}[{w}m]))"})
        rec.append({"record": f"slo:{name}:budget_per_minute",
                    "expr": f"sum(increase({total}[1d])) / 1440 * {round(1 - s['objective'], 6)}"})
        for w in slo["burn_rate_windows"]:
            lw, sw, b = w["long_minutes"], w["short_minutes"], w["burn"]
            alerts.append({
                "alert": f"{name.title().replace('_', '')}BudgetBurn{lw}m",
                "expr": (f"slo:{name}:bad_{lw}m > ({b} * {lw} * slo:{name}:budget_per_minute)"
                         f" and slo:{name}:bad_{sw}m > ({b} * {sw} * slo:{name}:budget_per_minute)"),
                "labels": {"severity": "page", "slo": name},
                "annotations": {"summary": f"{name} error budget burning {w['burn']}x over {w['long_minutes']}m",
                                "runbook_url": f"https://github.com/manojrevenkar12-web/shop-edge-platform/blob/main/docs/runbooks/{name}.md"},
            })
        groups.append({"name": f"slo-{name}", "rules": rec + alerts})
    return yaml.safe_dump({"groups": groups}, sort_keys=False, width=200)
