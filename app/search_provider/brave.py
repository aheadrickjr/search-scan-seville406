"""Brave Search API adapter.

Docs: https://api-dochub.brave.com/api-reference/web-search
No SERP scraping -- this hits Brave's sanctioned JSON API only.
"""
from __future__ import annotations

import time

import requests

from app.search_provider.base import RawSearchResult, SearchProvider

_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class SearchProviderError(RuntimeError):
    pass


class BraveSearchProvider(SearchProvider):
    name = "brave"

    def __init__(
        self,
        api_key: str,
        user_agent: str,
        min_seconds_between_requests: float = 1.0,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not api_key:
            raise SearchProviderError(
                "BRAVE_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self._api_key = api_key
        self._user_agent = user_agent
        self._min_interval = min_seconds_between_requests
        self._timeout = timeout_seconds
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def search(self, query: str, count: int = 20) -> list[RawSearchResult]:
        self._throttle()
        try:
            response = requests.get(
                _ENDPOINT,
                params={"q": query, "count": min(count, 20)},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self._api_key,
                    "User-Agent": self._user_agent,
                },
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise SearchProviderError(f"Brave Search request failed: {exc}") from exc
        finally:
            self._last_request_at = time.monotonic()

        if response.status_code != 200:
            raise SearchProviderError(
                f"Brave Search returned HTTP {response.status_code} for query "
                f"{query!r}: {response.text[:300]}"
            )

        payload = response.json()
        web_results = (payload.get("web") or {}).get("results") or []

        results: list[RawSearchResult] = []
        for position, item in enumerate(web_results[:count], start=1):
            results.append(
                RawSearchResult(
                    position=position,
                    title=item.get("title", "") or "",
                    snippet=item.get("description", "") or "",
                    url=item.get("url", "") or "",
                )
            )
        return results
