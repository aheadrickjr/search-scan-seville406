"""Deterministic (non-AI) classification rules.

Every classification is derived from: which domain list a URL's domain falls
into, HTTP reachability, redirect target, and plain substring/keyword
matches against title/snippet/page text. No ML/LLM involved in Phase 1.

Booking status always uses cautious, non-committal language -- the app must
never assert a listing is bookable or not bookable with more certainty than
an HTTP-only check actually supports.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.config.loader import DomainConfig
from app.link_validator.validator import UrlCheckResult
from app.url_utils.normalize import extract_domain

# Status codes that typically indicate a bot-block / access denial rather
# than a genuinely dead page. Treated as "Blocked or inaccessible", never
# as evidence a page no longer exists.
BLOCK_STATUS_CODES = {401, 403, 429, 999}

# Domains known to render availability/booking UI client-side (JavaScript).
# A plain HTTP GET will usually only see an empty app shell, so absence of
# booking language here must NOT be read as "no booking path" -- Phase 1
# cannot tell the difference between "not bookable" and "couldn't render it".
JS_HEAVY_DOMAINS = {
    "airbnb.com",
    "vrbo.com",
    "booking.com",
    "expedia.com",
    "hotels.com",
    "travelocity.com",
    "vacationrenter.com",
    "rentbyowner.com",
}

_BOOKING_PHRASES = (
    "book now",
    "check availability",
    "select your dates",
    "choose dates",
    "reserve now",
    "add dates",
    "instant book",
    "request to book",
    "check-in",
    "check availability calendar",
)

_PIR_RE = re.compile(r"\bpir\b|padre island rentals|pirentals", re.IGNORECASE)
_FRANKE_RE = re.compile(r"franke rentals|frankerentals", re.IGNORECASE)
_SEVILLE_406_RE = re.compile(
    r"seville\s+(unit\s+)?#?\s*406", re.IGNORECASE
)


@dataclass
class ClassificationResult:
    classification: str
    confidence: str  # "High" | "Medium" | "Low"
    mentions_seville_406: bool
    mentions_pir: bool
    mentions_franke: bool
    mentions_only_in_hidden_metadata: bool
    booking_language_detected: bool
    booking_status_text: str
    manual_review_flag: bool
    notes: str


def _combined_text(title: str, snippet: str, page_text: str, hidden_metadata_text: str) -> str:
    return " ".join(
        part for part in (title, snippet, page_text, hidden_metadata_text) if part
    )


def _booking_status_text(
    *, booking_language_detected: bool, domain: str, page_text_checked: bool, rendered: bool
) -> str:
    if booking_language_detected:
        return "Booking controls detected"
    if not page_text_checked:
        return "Unable to determine (content check skipped per robots.txt)"
    if domain in JS_HEAVY_DOMAINS and not rendered:
        return (
            "Unable to determine (page likely requires JavaScript rendering; "
            "not evaluated -- ran an HTTP-only check, not a browser render)"
        )
    return "No booking path detected"


def classify(
    *,
    normalized_url: str,
    title: str,
    snippet: str,
    domains: DomainConfig,
    url_check: UrlCheckResult,
) -> ClassificationResult:
    domain = extract_domain(normalized_url)
    visible_text = _combined_text(title, snippet, url_check.page_text, "")
    full_text = _combined_text(
        title, snippet, url_check.page_text, url_check.hidden_metadata_text
    )

    mentions_seville_406 = bool(_SEVILLE_406_RE.search(full_text))
    mentions_pir = bool(_PIR_RE.search(full_text))
    mentions_franke = bool(_FRANKE_RE.search(full_text))

    # True when a manager-name/property reference exists in machine-readable
    # metadata (title/meta tags/JSON-LD/alt text) that a site owner's cleanup
    # pass -- which typically only touches visible page copy -- would miss.
    # Search engines and OTAs index this metadata directly, so it's a
    # concrete, documentable reason stale attribution persists.
    mentions_only_in_hidden_metadata = bool(
        (_SEVILLE_406_RE.search(url_check.hidden_metadata_text)
         or _PIR_RE.search(url_check.hidden_metadata_text))
        and not (_SEVILLE_406_RE.search(visible_text) or _PIR_RE.search(visible_text))
    )

    booking_language_detected = url_check.page_text_checked and any(
        phrase in url_check.page_text.lower() for phrase in _BOOKING_PHRASES
    )
    booking_status_text = _booking_status_text(
        booking_language_detected=booking_language_detected,
        domain=domain,
        page_text_checked=url_check.page_text_checked,
        rendered=url_check.rendered,
    )

    is_blocked = url_check.status_code in BLOCK_STATUS_CODES
    final_domain = (
        extract_domain(url_check.final_url) if url_check.final_url else domain
    )
    redirected = bool(
        url_check.final_url
        and len(url_check.redirect_chain) > 1
        and url_check.final_url != normalized_url
    )

    notes = ""

    # 1. Franke Rentals' own domain.
    if domain in domains.franke_domains:
        classification = "Franke Rentals listing"
        confidence = "High" if url_check.accessible else "Medium"
        manual_review_flag = not url_check.accessible
        if not url_check.accessible:
            notes = "Franke Rentals' own domain did not respond successfully."

    # 2. Former manager's (PIR) own domain.
    elif domain in domains.pir_domains:
        if is_blocked:
            classification = "Blocked or inaccessible"
            confidence = "Low"
            manual_review_flag = True
            notes = f"HTTP {url_check.status_code} looks like a bot-block, not confirmation the page is gone."
        elif not url_check.accessible:
            classification = "Dead PIR page"
            confidence = "High" if url_check.status_code in (404, 410) else "Medium"
            manual_review_flag = False
        elif redirected:
            # Heuristic: a short/root-like final path suggests a generic
            # inventory page rather than a specific (different) listing.
            if final_domain in domains.pir_domains:
                final_path = urlsplit(url_check.final_url).path
                looks_generic = final_path.strip("/").count("/") == 0
                if looks_generic:
                    classification = "Redirect to PIR inventory"
                    notes = "Redirected to a shorter/generic path on the same PIR domain; likely a general listings page rather than a specific unit."
                else:
                    classification = "Redirect to unrelated property"
                    notes = "Redirected to a different, more specific path on the PIR domain -- may point at another unit."
            else:
                classification = "Redirect to unrelated property"
                notes = f"Redirected off PIR's domain entirely, to {final_domain}."
            confidence = "Medium"
            manual_review_flag = True
        else:
            classification = "Active PIR listing"
            confidence = "High" if mentions_seville_406 else "Medium"
            manual_review_flag = not mentions_seville_406
            if not mentions_seville_406:
                notes = "Page is live on PIR's domain but Seville 406 was not confirmed in title/snippet/page text."

    # 3. Known third-party OTA domains.
    elif domain in domains.ota_domains:
        if is_blocked or not url_check.accessible:
            classification = "Blocked or inaccessible"
            confidence = "Low"
            manual_review_flag = True
            notes = url_check.error_message or f"HTTP {url_check.status_code}"
        elif mentions_pir:
            classification = "Active third-party listing attributed to PIR"
            confidence = "High" if mentions_seville_406 else "Medium"
            manual_review_flag = not mentions_seville_406
        elif mentions_franke:
            classification = "Franke Rentals listing"
            confidence = "Medium"
            manual_review_flag = False
            notes = "Third-party page attributes this listing to Franke Rentals."
        elif booking_language_detected:
            classification = "Apparently bookable listing"
            confidence = "Medium"
            manual_review_flag = True
            notes = "Booking controls detected but manager attribution could not be confirmed from page text."
        else:
            classification = "OTA page, no availability signal detected"
            if url_check.rendered and url_check.page_text_checked:
                confidence = "High"
            elif url_check.page_text_checked:
                confidence = "Medium"
            else:
                confidence = "Low"
            manual_review_flag = not url_check.page_text_checked

    # 4. Anything else.
    else:
        if is_blocked:
            classification = "Blocked or inaccessible"
            confidence = "Low"
            manual_review_flag = True
        elif not url_check.accessible:
            classification = "Unclear — manual review required"
            confidence = "Low"
            manual_review_flag = True
            notes = url_check.error_message or f"HTTP {url_check.status_code}"
        elif url_check.page_text_checked and mentions_pir:
            classification = "Active third-party listing attributed to PIR"
            confidence = "Medium"
            manual_review_flag = not mentions_seville_406
        elif url_check.page_text_checked and mentions_franke:
            classification = "Franke Rentals listing"
            confidence = "Medium"
            manual_review_flag = False
        elif mentions_seville_406 or mentions_pir or mentions_franke:
            # Only the search snippet (not the page itself) confirms anything.
            classification = "Search result only (no page content confirms property)"
            confidence = "Low"
            manual_review_flag = True
        else:
            classification = "Unclear — manual review required"
            confidence = "Low"
            manual_review_flag = True

    if mentions_only_in_hidden_metadata:
        hidden_note = (
            "Seville 406/PIR reference found only in page metadata (title, meta "
            "tags, structured data, or image alt text) -- not in the visible "
            "page text. This suggests the visible copy was updated but the "
            "underlying page metadata was not, which is a plausible reason "
            "search engines/OTAs keep resurfacing this association."
        )
        notes = f"{notes} {hidden_note}".strip()
        manual_review_flag = True

    return ClassificationResult(
        classification=classification,
        confidence=confidence,
        mentions_seville_406=mentions_seville_406,
        mentions_pir=mentions_pir,
        mentions_franke=mentions_franke,
        mentions_only_in_hidden_metadata=mentions_only_in_hidden_metadata,
        booking_language_detected=booking_language_detected,
        booking_status_text=booking_status_text,
        manual_review_flag=manual_review_flag,
        notes=notes,
    )


def mark_duplicates(
    rows: list[tuple[str, str, str, int]],
    classifications: dict[str, ClassificationResult],
) -> dict[str, ClassificationResult]:
    """Given (normalized_url, domain, title, position) tuples from one scan
    plus each URL's already-computed ClassificationResult, return an updated
    dict where near-duplicates of a better-ranked result (same domain + exact
    title match) have their classification overridden to "Duplicate". All
    other fields (mention flags, booking status, etc.) are preserved from the
    original classification so evidence isn't lost.

    This is an exact-match heuristic only (Phase 1 limitation) -- fuzzy
    title matching is left for a later phase.
    """
    groups: dict[tuple[str, str], list[tuple[str, int]]] = {}
    for normalized_url, domain, title, position in rows:
        key = (domain, title.strip().lower())
        groups.setdefault(key, []).append((normalized_url, position))

    updated = dict(classifications)
    for (_, title_key), members in groups.items():
        if len(members) < 2 or not title_key:
            continue
        members.sort(key=lambda pair: pair[1])
        for normalized_url, _position in members[1:]:
            original = updated[normalized_url]
            updated[normalized_url] = ClassificationResult(
                classification="Duplicate",
                confidence="Medium",
                mentions_seville_406=original.mentions_seville_406,
                mentions_pir=original.mentions_pir,
                mentions_franke=original.mentions_franke,
                mentions_only_in_hidden_metadata=original.mentions_only_in_hidden_metadata,
                booking_language_detected=original.booking_language_detected,
                booking_status_text=original.booking_status_text,
                manual_review_flag=original.manual_review_flag,
                notes=(
                    "Same domain and title as a better-ranked result in this scan; "
                    f"likely the same listing under a different URL. "
                    f"(Original classification: {original.classification})"
                ),
            )
    return updated
