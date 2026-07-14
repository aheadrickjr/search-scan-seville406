"""Headless-browser (Playwright) URL validation with screenshots.

Phase 2: replaces the plain HTTP GET used in app/link_validator with a real
headless Chromium render. This is what lets the tool actually see
JavaScript-driven booking widgets, availability calendars, and manager-name
text that a raw HTTP response never contains (Phase 1's core limitation).

Same policy as Phase 1 (Option A, confirmed with the project owner):
reachability (status/redirect chain) is always recorded. Reading rendered
page text and taking a screenshot is skipped when robots.txt disallows the
path for our user-agent -- those results are flagged for manual review
instead of guessed at.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import Browser, Playwright, Response, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.link_validator.robots import RobotsCache
from app.link_validator.validator import UrlCheckResult, extract_hidden_metadata_text
from app.url_utils.normalize import extract_domain

_UNSAFE_FILENAME_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_filename(normalized_url: str) -> str:
    domain = extract_domain(normalized_url)
    slug = _UNSAFE_FILENAME_CHARS.sub("_", normalized_url).strip("_")[:150]
    return f"{domain}__{slug}.png"


def _build_redirect_chain(response: Response | None, original_url: str, final_url: str) -> list[str]:
    if response is None:
        return [original_url]
    requests_chain = [response.request]
    prior = response.request.redirected_from
    while prior is not None:
        requests_chain.append(prior)
        prior = prior.redirected_from
    requests_chain.reverse()
    chain = [r.url for r in requests_chain]
    if not chain:
        chain = [original_url]
    if chain[-1] != final_url:
        chain.append(final_url)
    return chain


class BrowserValidator:
    """Use as a context manager so one browser instance is reused across a
    whole scan instead of paying Chromium startup cost per URL:

        with BrowserValidator(...) as validator:
            for url in urls:
                result = validator.check(url, scan_id)
    """

    def __init__(
        self,
        user_agent: str,
        robots_cache: RobotsCache,
        screenshots_dir: Path,
        min_seconds_between_requests: float = 1.0,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._user_agent = user_agent
        self._robots = robots_cache
        self._screenshots_dir = screenshots_dir
        self._min_interval = min_seconds_between_requests
        self._timeout_ms = timeout_seconds * 1000
        self._last_request_at: dict[str, float] = {}
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def __enter__(self) -> "BrowserValidator":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def _throttle(self, domain: str) -> None:
        last = self._last_request_at.get(domain)
        if last is None:
            return
        remaining = self._min_interval - (time.monotonic() - last)
        if remaining > 0:
            time.sleep(remaining)

    def _error_result(self, error_message: str, robots_disallowed: bool) -> UrlCheckResult:
        return UrlCheckResult(
            status_code=None,
            redirect_chain=[],
            final_url=None,
            response_time_ms=None,
            accessible=False,
            error_message=error_message,
            robots_disallowed=robots_disallowed,
            page_text_checked=False,
            page_text="",
            hidden_metadata_text="",
            rendered=False,
            screenshot_path=None,
        )

    def check(self, normalized_url: str, scan_id: int) -> UrlCheckResult:
        assert self._browser is not None, "BrowserValidator must be used as a context manager"

        domain = extract_domain(normalized_url)
        self._throttle(domain)
        content_allowed = self._robots.can_fetch_content(normalized_url)

        context = self._browser.new_context(user_agent=self._user_agent)
        page = context.new_page()
        start = time.monotonic()
        try:
            try:
                response = page.goto(
                    normalized_url, timeout=self._timeout_ms, wait_until="networkidle"
                )
            except PlaywrightTimeoutError:
                # Some pages never go fully idle (polling widgets, ads) but
                # have already loaded their main content -- fall back to a
                # less strict wait condition instead of treating this as a
                # hard failure.
                response = page.goto(
                    normalized_url, timeout=self._timeout_ms, wait_until="load"
                )
        except Exception as exc:
            context.close()
            self._last_request_at[domain] = time.monotonic()
            return self._error_result(str(exc), not content_allowed)

        elapsed_ms = (time.monotonic() - start) * 1000
        status_code = response.status if response else None
        final_url = page.url
        redirect_chain = _build_redirect_chain(response, normalized_url, final_url)
        accessible = bool(status_code is not None and status_code < 400)

        page_text = ""
        hidden_metadata_text = ""
        screenshot_path: str | None = None
        page_text_checked = False

        if content_allowed:
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            hidden_metadata_text = extract_hidden_metadata_text(soup)
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            page_text = soup.get_text(separator=" ", strip=True)
            page_text_checked = True

            scan_dir = self._screenshots_dir / str(scan_id)
            scan_dir.mkdir(parents=True, exist_ok=True)
            screenshot_file = scan_dir / _safe_filename(normalized_url)
            try:
                page.screenshot(path=str(screenshot_file), full_page=True, timeout=self._timeout_ms)
                screenshot_path = str(screenshot_file.relative_to(self._screenshots_dir.parent))
            except Exception:
                screenshot_path = None

        context.close()
        self._last_request_at[domain] = time.monotonic()

        return UrlCheckResult(
            status_code=status_code,
            redirect_chain=redirect_chain,
            final_url=final_url,
            response_time_ms=elapsed_ms,
            accessible=accessible,
            error_message=None,
            robots_disallowed=not content_allowed,
            page_text_checked=page_text_checked,
            page_text=page_text,
            hidden_metadata_text=hidden_metadata_text,
            rendered=True,
            screenshot_path=screenshot_path,
        )
