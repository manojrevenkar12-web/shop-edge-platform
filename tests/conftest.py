from __future__ import annotations

import pytest

from sep.config import world_config
from sep.world import World


def small_config(**over) -> dict:
    cfg = world_config()
    cfg.update({"days": 2, "black_friday_day": 1})
    cfg.update(over)
    return cfg


@pytest.fixture(scope="session")
def world() -> World:
    return World(small_config(), 4242)
