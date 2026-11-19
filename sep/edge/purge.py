"""From catalogue changes to Varnish bans.

Pages carry tags in `X-Cache-Tags`: a product page `p-<id>` (and, in the shop's original scheme, `c-<category>` for
every category it belongs to); a category page `c-<category>` and `l-<id>` for each product it lists with a price.

- precise: a price or stock change bans `p-<id>` and `l-<id>`: the product's pages and the listings that show it.
- broad: the original scheme: `p-<id>` and every `c-<category>` the product is in, which also throws away every
  other product page in those categories.
- flush: ban everything (what a full cache clean does).
- none: rely on the TTL.

Changes are batched (one regex ban per `batch_seconds`, at most `max_tags` tags per ban) so the ban list stays
short; a ban list in the thousands slows every lookup.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

_TAG = re.compile(r"[a-z]-[0-9]+")


@dataclass(frozen=True)
class Change:
    kind: str           # price | stock
    product: int
    in_stock: bool = True


@dataclass(frozen=True)
class Ban:
    tags: tuple[str, ...]        # ("*",) for everything

    def __post_init__(self) -> None:
        # the header goes into a VCL regex as raw text (ADR 0002): only [a-z]-<digits> tags may pass
        if self.tags != ("*",) and not all(_TAG.fullmatch(t) for t in self.tags):
            raise ValueError(f"tags must match {_TAG.pattern}: {self.tags}")

    @property
    def expression(self) -> str:
        if self.tags == ("*",):
            return "obj.status != 0"
        return 'obj.http.X-Cache-Tags ~ "(^|,)(' + "|".join(self.tags) + ')(,|$)"'

    @property
    def header(self) -> str:
        """The X-Ban-Tags value the VCL turns into a ban (no quotes: VCL's ban() would match them literally)."""
        return "(^|,)(" + "|".join(self.tags) + ")(,|$)"


class PurgePlanner:
    def __init__(self, mode: str, categories_of: dict[int, list[int]] | None = None, max_tags: int = 200):
        if mode not in ("precise", "broad", "flush", "none"):
            raise ValueError(mode)
        self.mode, self.cats, self.max_tags = mode, categories_of or {}, max_tags

    def tags_for(self, c: Change) -> list[str]:
        if self.mode == "precise":
            return [f"p-{c.product}", f"l-{c.product}"]
        if self.mode == "broad":
            return [f"p-{c.product}"] + [f"c-{k}" for k in self.cats.get(c.product, [])]
        return []

    def plan(self, changes: Iterable[Change]) -> list[Ban]:
        changes = list(changes)
        if not changes or self.mode == "none":
            return []
        if self.mode == "flush":
            return [Ban(("*",))]
        seen: dict[str, None] = {}
        for c in changes:
            for t in self.tags_for(c):
                seen.setdefault(t, None)
        tags = list(seen)
        return [Ban(tuple(tags[i:i + self.max_tags])) for i in range(0, len(tags), self.max_tags)]


def warm_list(view_counts: dict[str, int], limit: int) -> list[str]:
    """Pages to fetch before traffic arrives: the most viewed in the last day, most viewed first."""
    return [k for k, _ in sorted(view_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def warm_order(view_counts: np.ndarray, candidates: np.ndarray, limit: int) -> np.ndarray:
    """The same rule on arrays (page index -> recent views): the `limit` most viewed of `candidates`."""
    if len(candidates) == 0:
        return candidates
    order = np.lexsort((candidates, -view_counts[candidates]))
    return candidates[order[:limit]]
