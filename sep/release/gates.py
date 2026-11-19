"""Release gates: SonarQube's quality gate before a build may ship, and canary analysis while it ships.

The quality gate reads SonarQube's `api/qualitygates/project_status` answer (Jenkins waits for it with
`waitForQualityGate`, see Jenkinsfile). The canary compares the new build's 5xx ratio and slow-response ratio on a
small share of traffic with the stable build's, and rolls back as soon as the difference is clear, or promotes after
the observation window when it is not.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def quality_gate(report: dict) -> tuple[bool, list[str]]:
    ps = report["projectStatus"]
    failed = [f"{c['metricKey']}={c['actualValue']} (limit {c['errorThreshold']})"
              for c in ps.get("conditions", []) if c.get("status") == "ERROR"]
    return ps["status"] == "OK", failed


def _wilson_lower(bad: float, n: float, z: float) -> float:
    if n <= 0:
        return 0.0
    p = bad / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - a) / d)


def _wilson_upper(bad: float, n: float, z: float) -> float:
    if n <= 0:
        return 1.0
    p = bad / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (c + a) / d)


@dataclass
class Canary:
    weight: float = 0.1
    minutes: int = 15
    z: float = 3.0               # strict: a rollback should be sure
    min_requests: int = 200
    margin: float = 0.002        # differences below this are noise, not a defect
    canary_bad: float = 0.0
    canary_n: float = 0.0
    base_bad: float = 0.0
    base_n: float = 0.0
    latency_margin_ms: float = 150.0
    latency_ratio: float = 1.25
    elapsed: int = 0
    canary_ms: float = 0.0
    base_ms: float = 0.0

    def observe(self, canary_bad: float, canary_n: float, base_bad: float, base_n: float,
                canary_ms: float = 0.0, base_ms: float = 0.0) -> str:
        """-> 'continue' | 'rollback' | 'promote'. Latencies are mean render times this minute."""
        self.canary_bad += canary_bad
        self.canary_n += canary_n
        self.base_bad += base_bad
        self.base_n += base_n
        self.canary_ms += canary_ms * canary_n
        self.base_ms += base_ms * base_n
        self.elapsed += 1
        if self.canary_n >= self.min_requests:
            lo = _wilson_lower(self.canary_bad, self.canary_n, self.z)
            hi = _wilson_upper(self.base_bad, self.base_n, self.z)
            if lo > hi + self.margin:
                return "rollback"
            c, b = self.canary_ms / self.canary_n, self.base_ms / max(self.base_n, 1)
            if c > max(b * self.latency_ratio, b + self.latency_margin_ms):
                return "rollback"
        return "promote" if self.elapsed >= self.minutes else "continue"
