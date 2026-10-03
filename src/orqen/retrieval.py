"""Opt-in lexical catalog filtering before planning, with a full-catalog baseline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower().replace("_", " ")))


@dataclass(frozen=True)
class CatalogPolicy:
    mode: str = "all"
    top_k: int = 5

    def __post_init__(self) -> None:
        if self.mode not in {"all", "fixed", "adaptive"}:
            raise ValueError("Catalog mode must be all, fixed, or adaptive")
        if type(self.top_k) is not int or self.top_k < 1:
            raise ValueError("top_k must be a positive integer")

    def select(self, goal: str, catalog: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
        if self.mode == "all" or not catalog:
            return catalog
        query = _tokens(goal)
        ranked = sorted(
            (
                (
                    len(
                        query
                        & _tokens(f"{tool['name']} {tool['description']} {tool['capability']}")
                    ),
                    index,
                    tool,
                )
                for index, tool in enumerate(catalog)
            ),
            key=lambda row: (-row[0], row[1]),
        )
        if self.mode == "fixed":
            return tuple(row[2] for row in ranked[: self.top_k])
        # Conservative heuristic, not a trained confidence estimate. No lexical
        # evidence means abstain from filtering. Retain ties at the cutoff rather
        # than choosing arbitrarily between equally scored tools.
        if ranked[0][0] == 0:
            return catalog
        positive = [row for row in ranked if row[0] > 0]
        cutoff = positive[min(self.top_k, len(positive)) - 1][0]
        return tuple(row[2] for row in positive if row[0] >= cutoff)
