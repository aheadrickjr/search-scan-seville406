"""Search provider adapter interface.

Any provider (Brave, and later Bing/SerpApi/etc.) implements this interface
so the rest of the pipeline never depends on a specific vendor's API shape.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RawSearchResult:
    position: int
    title: str
    snippet: str
    url: str


class SearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, count: int = 20) -> list[RawSearchResult]:
        """Return organic results for `query`, best-effort up to `count`."""
        raise NotImplementedError
