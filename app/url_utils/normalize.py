"""URL normalization and domain extraction for deduplication/classification."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query params that are pure tracking/session noise and never change what
# page is being referred to. Stripped before comparing/storing normalized
# URLs so that e.g. "?utm_source=google" doesn't create a fake duplicate.
_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = {
    "gclid",
    "fbclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "affid",
    "affiliate_id",
    "sessionid",
    "session_id",
    "sid",
    "clickid",
    "click_id",
    "igshid",
}


def _is_tracking_param(key: str) -> bool:
    key_lower = key.lower()
    return key_lower in _TRACKING_PARAMS or key_lower.startswith(
        _TRACKING_PARAM_PREFIXES
    )


def extract_domain(url: str) -> str:
    """Return a best-effort registrable domain, e.g. "www.pirentals.com" -> "pirentals.com".

    This is a simple last-two-labels heuristic (adequate for the .com/.net
    domains this project targets) and does not implement a full public-suffix
    list, so multi-part TLDs like ".co.uk" will be extracted incorrectly.
    """
    host = urlsplit(url).netloc.lower()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    labels = [label for label in host.split(".") if label]
    if len(labels) <= 2:
        return host
    return ".".join(labels[-2:])


def normalize_url(url: str) -> str:
    """Canonicalize a URL for deduplication/storage.

    - lowercases scheme and host
    - drops default ports, fragments
    - strips known tracking query params
    - sorts remaining query params for stable comparison
    - strips a single trailing slash from the path (except root "/")
    """
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[: -len(":80")]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[: -len(":443")]

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    kept_params = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(k)
    ]
    kept_params.sort()
    query = urlencode(kept_params)

    return urlunsplit((scheme, netloc, path, query, ""))
