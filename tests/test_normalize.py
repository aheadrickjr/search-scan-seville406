from app.url_utils.normalize import extract_domain, normalize_url


def test_strips_tracking_params():
    url = "https://www.example.com/listing?utm_source=google&utm_medium=cpc&id=42"
    assert normalize_url(url) == "https://www.example.com/listing?id=42"


def test_strips_known_tracking_param_names():
    url = "https://example.com/page?fbclid=abc123&ref=homepage&id=7"
    assert normalize_url(url) == "https://example.com/page?id=7"


def test_removes_fragment_and_trailing_slash():
    url = "https://Example.com/Listing/#section-2"
    assert normalize_url(url) == "https://example.com/Listing"


def test_equivalent_urls_normalize_identically():
    a = "https://example.com/rooms/406?utm_source=fb&sort=asc"
    b = "https://example.com/rooms/406/?sort=asc&utm_source=google"
    assert normalize_url(a) == normalize_url(b)


def test_sorts_remaining_query_params_for_stable_comparison():
    a = "https://example.com/page?b=2&a=1"
    b = "https://example.com/page?a=1&b=2"
    assert normalize_url(a) == normalize_url(b)


def test_default_port_stripped():
    assert normalize_url("http://example.com:80/page") == "http://example.com/page"


def test_extract_domain_strips_www_and_subdomains():
    assert extract_domain("https://www.pirentals.com/seville-406") == "pirentals.com"
    assert extract_domain("https://m.expedia.com/hotel/123") == "expedia.com"
    assert extract_domain("https://frankerentals.com/") == "frankerentals.com"


def test_extract_domain_ignores_port_and_userinfo():
    assert extract_domain("https://user:pass@example.com:8443/x") == "example.com"
