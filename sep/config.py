"""Settings live in config/*.yaml. The world reads only world.yaml (and its held-out overlay); the platform never does."""
from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


@cache
def _load(name: str) -> dict:
    return yaml.safe_load((CONFIG / f"{name}.yaml").read_text())


def load(name: str) -> dict:
    """A fresh copy, so callers may change it."""
    import copy

    return copy.deepcopy(_load(name))


def world_config(heldout: bool = False) -> dict:
    cfg = load("world")
    if heldout:
        cfg.update(load("heldout"))
    return cfg
