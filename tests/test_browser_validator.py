from app.browser_validator.validator import _build_redirect_chain, _safe_filename


class _FakeRequest:
    def __init__(self, url: str, redirected_from=None):
        self.url = url
        self.redirected_from = redirected_from


class _FakeResponse:
    def __init__(self, request: _FakeRequest):
        self.request = request


def test_safe_filename_strips_unsafe_characters():
    name = _safe_filename("https://expedia.com/hotel/seville-406?id=1&x=2")
    assert name.endswith(".png")
    assert "?" not in name
    assert "/" not in name
    assert name.startswith("expedia.com__")


def test_redirect_chain_with_no_redirects():
    request = _FakeRequest("https://pirentals.com/seville-406")
    response = _FakeResponse(request)
    chain = _build_redirect_chain(response, "https://pirentals.com/seville-406", "https://pirentals.com/seville-406")
    assert chain == ["https://pirentals.com/seville-406"]


def test_redirect_chain_follows_redirected_from():
    first = _FakeRequest("https://pirentals.com/seville-406-old")
    second = _FakeRequest("https://pirentals.com/listings", redirected_from=first)
    response = _FakeResponse(second)
    chain = _build_redirect_chain(
        response, "https://pirentals.com/seville-406-old", "https://pirentals.com/listings"
    )
    assert chain == [
        "https://pirentals.com/seville-406-old",
        "https://pirentals.com/listings",
    ]


def test_redirect_chain_falls_back_to_original_url_when_no_response():
    chain = _build_redirect_chain(None, "https://example.com/a", "https://example.com/a")
    assert chain == ["https://example.com/a"]
