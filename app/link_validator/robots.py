"""Per-domain robots.txt cache.

Policy (Option A, confirmed with the project owner):
- The HTTP reachability check (status/redirects/timing) always runs,
  regardless of robots.txt -- resolving a URL you already have is normal
  client behavior, not crawling.
- Reading the page body to check for keyword/booking-language mentions is
  skipped on any path robots.txt disallows for our user-agent. Those results
  are flagged for manual review instead.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests


class RobotsCache:
    def __init__(self, user_agent: str, timeout_seconds: float = 10.0) -> None:
        self._user_agent = user_agent
        self._timeout = timeout_seconds
        self._parsers: dict[str, RobotFileParser | None] = {}

    def _get_parser(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._parsers:
            return self._parsers[origin]

        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            response = requests.get(
                f"{origin}/robots.txt",
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout,
            )
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                # No robots.txt (404) or inaccessible -> treat as "allow all".
                parser.parse([])
        except requests.RequestException:
            parser.parse([])

        self._parsers[origin] = parser
        return parser

    def can_fetch_content(self, url: str) -> bool:
        parser = self._get_parser(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self._user_agent, url)
        except Exception:
            return True
