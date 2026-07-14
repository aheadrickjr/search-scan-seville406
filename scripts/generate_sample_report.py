"""Generates a sample Excel evidence register from fabricated mock data.

This does NOT call the search API or the network -- it's purely so you can
see the report format before running a real scan. Run with:

    python scripts/generate_sample_report.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Classification, Scan, ScanQuery, SearchResult, UrlCheck
from app.reporting.excel_export import export_scan_to_excel

MOCK_ROWS = [
    # (query, position, title, snippet, url, status_code, final_url, redirect_chain,
    #  accessible, robots_disallowed, page_text_checked,
    #  classification, confidence, mentions_406, mentions_pir, mentions_franke,
    #  mentions_hidden_only, booking_lang, booking_status, manual_review, notes)
    (
        '"Seville 406" "Padre Island Rentals"', 1,
        "Seville 406 | Padre Island Rentals", "Book Seville 406 directly with Padre Island Rentals.",
        "https://pirentals.com/seville-406", 200, "https://pirentals.com/seville-406",
        ["https://pirentals.com/seville-406"], True, False, True,
        "Active PIR listing", "Medium", True, True, False, False,
        False, "No booking path detected", True,
        "Live on PIR's domain; still attributes the unit to the former manager.",
    ),
    (
        '"Seville 406 by Padre Island Rentals"', 4,
        "Page Not Found | Padre Island Rentals", "",
        "https://pirentals.com/listings/seville-406-old", 404, "https://pirentals.com/listings/seville-406-old",
        ["https://pirentals.com/listings/seville-406-old"], False, False, True,
        "Dead PIR page", "High", False, False, False, False,
        False, "No booking path detected", False,
        "",
    ),
    (
        '"Seville 406" PIR', 2,
        "Seville 406", "",
        "https://pirentals.com/seville-406-legacy", 301, "https://pirentals.com/listings",
        ["https://pirentals.com/seville-406-legacy", "https://pirentals.com/listings"], True, False, True,
        "Redirect to PIR inventory", "Medium", False, False, False, False,
        False, "No booking path detected", True,
        "Redirected to a shorter/generic path on the same PIR domain.",
    ),
    (
        '"Seville 406" condo', 6,
        "Seville 406", "",
        "https://pirentals.com/seville-406-old2", 301, "https://pirentals.com/listings/seville-201",
        ["https://pirentals.com/seville-406-old2", "https://pirentals.com/listings/seville-201"], True, False, True,
        "Redirect to unrelated property", "Medium", False, False, False, False,
        False, "No booking path detected", True,
        "Redirected to a different, more specific path -- may point at another unit.",
    ),
    (
        'site:frankerentals.com "Seville 406"', 1,
        "Seville 406 | Franke Rentals", "Seville 406 is now managed by Franke Rentals.",
        "https://frankerentals.com/seville-406", 200, "https://frankerentals.com/seville-406",
        ["https://frankerentals.com/seville-406"], True, False, True,
        "Franke Rentals listing", "High", True, False, True, False,
        False, "No booking path detected", False,
        "",
    ),
    (
        'site:expedia.com "Seville 406"', 3,
        "Seville 406 Condo - South Padre Island", "Managed by Padre Island Rentals. Check availability.",
        "https://expedia.com/hotel/seville-406", 200, "https://expedia.com/hotel/seville-406",
        ["https://expedia.com/hotel/seville-406"], True, False, True,
        "Active third-party listing attributed to PIR", "High", True, True, False, False,
        True, "Booking controls detected", False,
        "",
    ),
    (
        'site:airbnb.com "Seville 406"', 5,
        "Seville 406 South Padre Island", "Beachfront condo, 2BR/2BA.",
        "https://airbnb.com/rooms/9988776", None, None,
        [], False, False, True,
        "Apparently bookable listing", "Medium", True, False, False, False,
        True, "Booking controls detected", True,
        "Booking controls detected but manager attribution could not be confirmed from page text.",
    ),
    (
        'site:vrbo.com "Seville 406"', 8,
        "Seville 406 Condo", "South Padre Island vacation rental.",
        "https://vrbo.com/1234567", 200, "https://vrbo.com/1234567",
        ["https://vrbo.com/1234567"], True, False, True,
        "OTA page, no availability signal detected", "Medium", True, False, False, False,
        False, "Unable to determine (page likely requires JavaScript rendering; not evaluated in Phase 1)", False,
        "",
    ),
    (
        # This is the hotels.com-style case: nothing in the visible page copy
        # mentions PIR, but the <title>/JSON-LD structured data still does --
        # evidence the old listing metadata was never fully cleaned up, which
        # is a plausible reason it keeps resurfacing in search results.
        'site:hotels.com "Seville 406"', 4,
        "Seville 406 Condo", "South Padre Island vacation condo, sleeps 6.",
        "https://hotels.com/ho123456", 200, "https://hotels.com/ho123456",
        ["https://hotels.com/ho123456"], True, False, True,
        "OTA page, no availability signal detected", "Medium", True, False, False, True,
        False, "Unable to determine (page likely requires JavaScript rendering; not evaluated in Phase 1)", True,
        'Seville 406/PIR reference found only in page metadata (title, meta tags, structured data, or image alt '
        'text) -- not in the visible page text. This suggests the visible copy was updated but the underlying '
        'page metadata was not, which is a plausible reason search engines/OTAs keep resurfacing this association.',
    ),
    (
        'site:booking.com "Seville 406"', 9,
        "Seville 406", "",
        "https://booking.com/hotel/us/seville-406.html", 403, None,
        [], False, False, False,
        "Blocked or inaccessible", "Low", False, False, False, False,
        False, "Unable to determine (content check skipped per robots.txt)", True,
        "HTTP 403 looks like a bot-block, not confirmation the page is gone.",
    ),
    (
        '"Seville 406" rental', 12,
        "Forum: anyone stayed at Seville 406?", "Mentions Padre Island Rentals in a 2019 post.",
        "https://travelforum.example/thread/558", 200, "https://travelforum.example/thread/558",
        ["https://travelforum.example/thread/558"], True, False, False,
        "Search result only (no page content confirms property)", "Low", True, True, False, False,
        False, "Unable to determine (content check skipped per robots.txt)", True,
        "",
    ),
    (
        '"Seville 406" "South Padre Island"', 15,
        "South Padre Island Rentals Guide", "General guide, no specific unit mentioned.",
        "https://travelblog.example/spi-guide", 200, "https://travelblog.example/spi-guide",
        ["https://travelblog.example/spi-guide"], True, False, True,
        "Unclear — manual review required", "Low", False, False, False, False,
        False, "No booking path detected", True,
        "",
    ),
    (
        'site:expedia.com "Seville 406"', 3,
        "Seville 406 Condo - South Padre Island", "Mobile duplicate of the same listing.",
        "https://expedia.com/hotel/seville-406?device=mobile", 200, "https://expedia.com/hotel/seville-406?device=mobile",
        ["https://expedia.com/hotel/seville-406?device=mobile"], True, False, True,
        "Duplicate", "Medium", True, True, False, False,
        True, "Booking controls detected", False,
        "Same domain and title as a better-ranked result in this scan.",
    ),
]


def main() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()

    scan = Scan(
        run_at=datetime.now(timezone.utc),
        provider="brave",
        notes="SAMPLE DATA -- fabricated for format preview only, not a real scan.",
    )
    session.add(scan)
    session.flush()

    query_cache: dict[str, ScanQuery] = {}

    for row in MOCK_ROWS:
        (
            query_text, position, title, snippet, url, status_code, final_url,
            redirect_chain, accessible, robots_disallowed, page_text_checked,
            classification, confidence, mentions_406, mentions_pir, mentions_franke,
            mentions_hidden_only, booking_lang, booking_status, manual_review, notes,
        ) = row

        scan_query = query_cache.get(query_text)
        if scan_query is None:
            scan_query = ScanQuery(scan_id=scan.id, query_text=query_text, raw_result_count=0)
            session.add(scan_query)
            session.flush()
            query_cache[query_text] = scan_query
        scan_query.raw_result_count += 1

        session.add(
            SearchResult(
                scan_id=scan.id,
                scan_query_id=scan_query.id,
                position=position,
                provider="brave",
                title=title,
                snippet=snippet,
                original_url=url,
                normalized_url=url,
                domain=url.split("/")[2] if "//" in url else url,
            )
        )
        domain = url.split("/")[2] if "//" in url else url
        screenshot_path = (
            f"{scan.id}/{domain}__sample.png" if page_text_checked else None
        )
        session.add(
            UrlCheck(
                scan_id=scan.id,
                normalized_url=url,
                status_code=status_code,
                redirect_chain_json=json.dumps(redirect_chain),
                final_url=final_url,
                response_time_ms=180.0 if accessible else None,
                accessible=accessible,
                error_message=None if accessible else f"HTTP {status_code}",
                robots_disallowed=robots_disallowed,
                page_text_checked=page_text_checked,
                rendered=page_text_checked,
                screenshot_path=screenshot_path,
            )
        )
        session.add(
            Classification(
                scan_id=scan.id,
                normalized_url=url,
                classification=classification,
                confidence=confidence,
                mentions_seville_406=mentions_406,
                mentions_pir=mentions_pir,
                mentions_franke=mentions_franke,
                mentions_only_in_hidden_metadata=mentions_hidden_only,
                booking_language_detected=booking_lang,
                booking_status_text=booking_status,
                manual_review_flag=manual_review,
                notes=notes,
            )
        )

    session.commit()

    output_path = REPO_ROOT / "sample_output" / "sample_evidence_register.xlsx"
    export_scan_to_excel(session, scan.id, output_path)
    print(f"Sample evidence register written to {output_path}")


if __name__ == "__main__":
    main()
