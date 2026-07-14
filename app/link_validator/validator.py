"""HTTP reachability + (conditionally) page-text checks for a URL."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

from app.link_validator.robots import RobotsCache
from app.url_utils.normalize import extract_domain


@dataclass
class UrlCheckResult:
    status_code: int | None
    redirect_chain: list[str]
    final_url: str | None
    response_time_ms: float | None
    accessible: bool
    error_message: str | None
    robots_disallowed: bool
    page_text_checked: bool
    page_text: str = field(default="")


def _extract_visible_text(response: requests.Response) -> str:
    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        return ""
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


class LinkValidator:
    def __init__(
        self,
        user_agent: str,
        robots_cache: RobotsCache,
        min_seconds_between_requests: float = 1.0,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._user_agent = user_agent
        self._robots = robots_cache
        self._min_interval = min_seconds_between_requests
        self._timeout = timeout_seconds
        self._last_request_at: dict[str, float] = {}

    def _throttle(self, domain: str) -> None:
        last = self._last_request_at.get(domain)
        if last is None:
            return
        remaining = self._min_interval - (time.monotonic() - last)
        if remaining > 0:
            time.sleep(remaining)

    def check(self, url: str) -> UrlCheckResult:
        domain = extract_domain(url)
        self._throttle(domain)
        content_allowed = self._robots.can_fetch_content(url)
        headers = {"User-Agent": self._user_agent}

        start = time.monotonic()
        try:
            if content_allowed:
                response = requests.get(
                    url, headers=headers, timeout=self._timeout, allow_redirects=True
                )
                page_text = _extract_visible_text(response)
                page_text_checked = True
            else:
                # robots.txt disallows this path for our user-agent: confirm
                # reachability only, never read the body.
                try:
                    response = requests.head(
                        url,
                        headers=headers,
                        timeout=self._timeout,
                        allow_redirects=True,
                    )
                    if response.status_code == 405:
                        raise requests.RequestException("HEAD not allowed")
                except requests.RequestException:
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=self._timeout,
                        allow_redirects=True,
                        stream=True,
                    )
                    response.close()
                page_text = ""
                page_text_checked = False
        except requests.RequestException as exc:
            return UrlCheckResult(
                status_code=None,
                redirect_chain=[],
                final_url=None,
                response_time_ms=None,
                accessible=False,
                error_message=str(exc),
                robots_disallowed=not content_allowed,
                page_text_checked=False,
                page_text="",
            )
        finally:
            self._last_request_at[domain] = time.monotonic()

        elapsed_ms = (time.monotonic() - start) * 1000
        redirect_chain = [r.url for r in response.history] + [response.url]

        return UrlCheckResult(
            status_code=response.status_code,
            redirect_chain=redirect_chain,
            final_url=response.url,
            response_time_ms=elapsed_ms,
            accessible=response.status_code < 400,
            error_message=None,
            robots_disallowed=not content_allowed,
            page_text_checked=page_text_checked,
            page_text=page_text,
        )
