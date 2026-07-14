from app.classifier.rules import classify, mark_duplicates
from app.config.loader import DomainConfig
from app.link_validator.validator import UrlCheckResult

DOMAINS = DomainConfig(
    pir_domains=["pirentals.com"],
    franke_domains=["frankerentals.com"],
    ota_domains=["expedia.com", "airbnb.com"],
)


def _check(**overrides) -> UrlCheckResult:
    base = dict(
        status_code=200,
        redirect_chain=["https://example.com/"],
        final_url="https://example.com/",
        response_time_ms=120.0,
        accessible=True,
        error_message=None,
        robots_disallowed=False,
        page_text_checked=True,
        page_text="",
        hidden_metadata_text="",
    )
    base.update(overrides)
    return UrlCheckResult(**base)


def test_active_pir_listing():
    result = classify(
        normalized_url="https://pirentals.com/seville-406",
        title="Seville 406 - South Padre Island",
        snippet="Book Seville 406 with Padre Island Rentals",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://pirentals.com/seville-406",
            redirect_chain=["https://pirentals.com/seville-406"],
            page_text="Welcome to Seville 406, managed by Padre Island Rentals.",
        ),
    )
    assert result.classification == "Active PIR listing"
    assert result.confidence == "High"
    assert result.mentions_seville_406 is True
    assert result.mentions_pir is True
    assert result.manual_review_flag is False


def test_dead_pir_page():
    result = classify(
        normalized_url="https://pirentals.com/seville-406",
        title="Seville 406",
        snippet="",
        domains=DOMAINS,
        url_check=_check(
            status_code=404,
            accessible=False,
            final_url="https://pirentals.com/seville-406",
            redirect_chain=["https://pirentals.com/seville-406"],
            page_text="",
        ),
    )
    assert result.classification == "Dead PIR page"
    assert result.confidence == "High"


def test_pir_domain_blocked_not_dead():
    result = classify(
        normalized_url="https://pirentals.com/seville-406",
        title="Seville 406",
        snippet="",
        domains=DOMAINS,
        url_check=_check(
            status_code=403,
            accessible=False,
            final_url="https://pirentals.com/seville-406",
            redirect_chain=["https://pirentals.com/seville-406"],
        ),
    )
    assert result.classification == "Blocked or inaccessible"
    assert result.manual_review_flag is True


def test_pir_redirect_to_generic_inventory():
    result = classify(
        normalized_url="https://pirentals.com/seville-406",
        title="Seville 406",
        snippet="",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://pirentals.com/listings",
            redirect_chain=[
                "https://pirentals.com/seville-406",
                "https://pirentals.com/listings",
            ],
        ),
    )
    assert result.classification == "Redirect to PIR inventory"


def test_pir_trailing_slash_canonicalization_is_not_a_redirect():
    # Regression test: a site's own trailing-slash canonicalization (e.g.
    # "/rental/sv406" -> "/rental/sv406/") produces a real HTTP redirect to
    # what is otherwise the identical page. This must NOT be classified as
    # "redirected to different content" -- it's still the live page.
    result = classify(
        normalized_url="https://pirentals.com/vacation-rentals/rental/sv406",
        title="Seville 406 | Padre Island Rentals",
        snippet="Book Seville 406 with Padre Island Rentals",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://pirentals.com/vacation-rentals/rental/sv406/",
            redirect_chain=[
                "https://pirentals.com/vacation-rentals/rental/sv406",
                "https://pirentals.com/vacation-rentals/rental/sv406/",
            ],
        ),
    )
    assert result.classification == "Active PIR listing"
    assert result.classification not in {
        "Redirect to PIR inventory",
        "Redirect to unrelated property",
    }


def test_pir_redirect_to_unrelated_property():
    result = classify(
        normalized_url="https://pirentals.com/seville-406",
        title="Seville 406",
        snippet="",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://pirentals.com/listings/seville-201",
            redirect_chain=[
                "https://pirentals.com/seville-406",
                "https://pirentals.com/listings/seville-201",
            ],
        ),
    )
    assert result.classification == "Redirect to unrelated property"


def test_franke_domain_listing():
    result = classify(
        normalized_url="https://frankerentals.com/seville-406",
        title="Seville 406",
        snippet="",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://frankerentals.com/seville-406",
            redirect_chain=["https://frankerentals.com/seville-406"],
        ),
    )
    assert result.classification == "Franke Rentals listing"
    assert result.confidence == "High"


def test_ota_page_attributed_to_pir():
    result = classify(
        normalized_url="https://expedia.com/hotel/seville-406",
        title="Seville 406",
        snippet="Managed by Padre Island Rentals",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://expedia.com/hotel/seville-406",
            redirect_chain=["https://expedia.com/hotel/seville-406"],
            page_text="Seville 406 managed by Padre Island Rentals. Book now!",
        ),
    )
    assert result.classification == "Active third-party listing attributed to PIR"
    assert result.booking_language_detected is True
    assert result.booking_status_text == "Booking controls detected"


def test_ota_page_js_heavy_no_signal_is_cautious():
    result = classify(
        normalized_url="https://airbnb.com/rooms/12345",
        title="Seville 406",
        snippet="South Padre Island condo",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://airbnb.com/rooms/12345",
            redirect_chain=["https://airbnb.com/rooms/12345"],
            page_text="<app shell, no content>",
        ),
    )
    assert result.classification == "OTA page, no availability signal detected"
    assert "Unable to determine" in result.booking_status_text
    assert result.confidence == "Medium"


def test_ota_page_js_heavy_rendered_no_signal_is_trusted():
    # Same JS-heavy domain/no-signal scenario, but this time the check came
    # from a real headless-browser render (Phase 2) -- so a negative result
    # can actually be trusted instead of hedged.
    result = classify(
        normalized_url="https://airbnb.com/rooms/12345",
        title="Seville 406",
        snippet="South Padre Island condo",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://airbnb.com/rooms/12345",
            redirect_chain=["https://airbnb.com/rooms/12345"],
            page_text="Beachfront condo, 2BR/2BA. Fully rendered content, no booking widget found.",
            rendered=True,
            screenshot_path="1/airbnb.com__rooms_12345.png",
        ),
    )
    assert result.classification == "OTA page, no availability signal detected"
    assert result.booking_status_text == "No booking path detected"
    assert result.confidence == "High"


def test_ota_blocked():
    result = classify(
        normalized_url="https://expedia.com/hotel/seville-406",
        title="Seville 406",
        snippet="",
        domains=DOMAINS,
        url_check=_check(status_code=429, accessible=False),
    )
    assert result.classification == "Blocked or inaccessible"
    assert result.confidence == "Low"


def test_robots_disallowed_defers_to_manual_review_language():
    result = classify(
        normalized_url="https://pirentals.com/seville-406",
        title="Seville 406",
        snippet="",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://pirentals.com/seville-406",
            redirect_chain=["https://pirentals.com/seville-406"],
            page_text_checked=False,
            robots_disallowed=True,
            page_text="",
        ),
    )
    assert "robots.txt" in result.booking_status_text


def test_unknown_domain_search_result_only():
    result = classify(
        normalized_url="https://randomblog.example/post",
        title="Seville 406 mentioned here",
        snippet="Padre Island Rentals used to manage this unit",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://randomblog.example/post",
            redirect_chain=["https://randomblog.example/post"],
            page_text_checked=False,
            page_text="",
        ),
    )
    assert result.classification == "Search result only (no page content confirms property)"


def test_unknown_domain_unclear():
    result = classify(
        normalized_url="https://randomblog.example/post",
        title="Nothing relevant",
        snippet="",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://randomblog.example/post",
            redirect_chain=["https://randomblog.example/post"],
            page_text_checked=True,
            page_text="Totally unrelated content.",
        ),
    )
    assert result.classification == "Unclear — manual review required"


def test_hidden_metadata_only_mention_is_flagged():
    result = classify(
        normalized_url="https://expedia.com/hotel/seville-406",
        title="Beachfront Condo",
        snippet="South Padre Island rental",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://expedia.com/hotel/seville-406",
            redirect_chain=["https://expedia.com/hotel/seville-406"],
            page_text="Beachfront condo, 2BR/2BA. Great views.",
            hidden_metadata_text=(
                '<title>Seville 406 | Padre Island Rentals</title> '
                '{"name": "Seville 406", "provider": "Padre Island Rentals"}'
            ),
        ),
    )
    assert result.mentions_only_in_hidden_metadata is True
    assert result.mentions_seville_406 is True
    assert result.mentions_pir is True
    assert result.manual_review_flag is True
    assert "hidden" in result.notes.lower() or "metadata" in result.notes.lower()


def test_visible_mention_is_not_flagged_as_hidden_only():
    result = classify(
        normalized_url="https://expedia.com/hotel/seville-406",
        title="Seville 406",
        snippet="Managed by Padre Island Rentals",
        domains=DOMAINS,
        url_check=_check(
            final_url="https://expedia.com/hotel/seville-406",
            redirect_chain=["https://expedia.com/hotel/seville-406"],
            page_text="Seville 406, managed by Padre Island Rentals.",
            hidden_metadata_text="<title>Seville 406 | Padre Island Rentals</title>",
        ),
    )
    assert result.mentions_only_in_hidden_metadata is False


def test_mark_duplicates_preserves_original_fields_on_lower_ranked_copy():
    rows = [
        ("https://expedia.com/a", "expedia.com", "Seville 406 Condo", 1),
        ("https://expedia.com/a?ref=mobile", "expedia.com", "Seville 406 Condo", 5),
    ]
    base_result = classify(
        normalized_url="https://expedia.com/a",
        title="Seville 406 Condo",
        snippet="Managed by Padre Island Rentals",
        domains=DOMAINS,
        url_check=_check(page_text="Padre Island Rentals"),
    )
    classifications = {
        "https://expedia.com/a": base_result,
        "https://expedia.com/a?ref=mobile": base_result,
    }
    updated = mark_duplicates(rows, classifications)
    assert updated["https://expedia.com/a"].classification == base_result.classification
    assert updated["https://expedia.com/a?ref=mobile"].classification == "Duplicate"
    assert updated["https://expedia.com/a?ref=mobile"].mentions_pir == base_result.mentions_pir
