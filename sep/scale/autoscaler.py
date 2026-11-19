"""Replica decisions for the shop's PHP pods, in the HPA's own arithmetic.

`desired = ceil(current * metric / target)`, scale-up applied at once, scale-down only to the highest recommendation
of the last `down_window` minutes, bounded by min/max. Two metrics:

- cpu: average utilisation over the last two minutes (what the cluster had). It lags: a render queue builds before
  CPU shows it, and teams answer with a high floor.
- rps: uncached page renders per second per pod, from Prometheus through the custom-metrics adapter. It moves with
  traffic, so the floor can be low.

Scheduled minimums raise the floor ahead of known peaks (a sale launch), because new pods need minutes to start.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Window:
    start: int        # minute from the start of the simulation, or an epoch minute in production
    end: int
    min_replicas: int


@dataclass
class Autoscaler:
    metric: str                     # cpu | rps
    target: float                   # utilisation 0..1 for cpu, renders per second per pod for rps
    min_replicas: int
    max_replicas: int
    down_window: int = 5
    schedule: list[Window] = field(default_factory=list)
    _history: deque = field(default_factory=lambda: deque(maxlen=60))
    _cpu: deque = field(default_factory=lambda: deque(maxlen=2))

    def floor(self, minute: int) -> int:
        return max([self.min_replicas] + [w.min_replicas for w in self.schedule if w.start <= minute < w.end])

    def desired(self, minute: int, current: int, renders_per_second: float, cpu_utilisation: float) -> int:
        if self.metric == "rps":
            value, target = renders_per_second / max(current, 1), self.target
        else:
            self._cpu.append(cpu_utilisation)
            value, target = sum(self._cpu) / len(self._cpu), self.target
        raw = math.ceil(current * value / target) if value > 0 else self.min_replicas
        if abs(value / target - 1) <= 0.1:          # the HPA's tolerance band
            raw = current
        lo, hi = self.floor(minute), self.max_replicas
        rec = min(max(raw, lo), hi)
        self._history.append(rec)
        if rec >= current:
            return rec
        recent = list(self._history)[-self.down_window:]
        return max(min(max(recent), current), lo)
