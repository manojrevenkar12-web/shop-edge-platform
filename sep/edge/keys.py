"""Cache keys: the same rules as edge/default.vcl, in Python so the simulation, the tests and the tooling agree.

Marketing parameters create a new cache key per click (`?gclid=...` is unique per ad click), so every tracked visit
misses the cache unless the parameter is stripped. Analytics and consent cookies do not change the page, so they are
stripped before the cache decides; session and cart cookies still bypass it.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# strip these query parameters before hashing; the VCL uses the same list (tests/test_vcl.py checks they match)
MARKETING = re.compile(r"^(utm_[a-z]+|gclid|gbraid|wbraid|fbclid|msclkid|dclid|mc_cid|mc_eid|_ga|_gl|yclid|ttclid)$")
UTM_ONLY = re.compile(r"^utm_[a-z]+$")
# cookies that never change the HTML
ANALYTICS_COOKIES = re.compile(r"^(_ga.*|_gid|_gat.*|_fbp|_fbc|_gcl_.*|_uet.*|_clck|_clsk|OptanonConsent|"
                               r"OptanonAlertBoxClosed|_hj.*|cookie_consent)$")
# cookies that do: the page is personal while they are present
PRIVATE_COOKIES = re.compile(r"^(PHPSESSID|frontend|private_content_version|cart_id|customer_token)$")


def normalize(url: str, strip: re.Pattern = MARKETING) -> str:
    """The URL the cache hashes: host lower-cased, marketing parameters removed, the rest sorted."""
    parts = urlsplit(url)
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not strip.match(k))
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", urlencode(query), ""))


def cacheable(cookie_header: str | None, strip_analytics: bool = True) -> bool:
    """May this request be answered from the shared cache?"""
    if not cookie_header:
        return True
    names = [c.split("=", 1)[0].strip() for c in cookie_header.split(";") if c.strip()]
    if any(PRIVATE_COOKIES.match(n) for n in names):
        return False
    if not strip_analytics:
        return False
    return all(ANALYTICS_COOKIES.match(n) for n in names)


def fragmenting_share(params_seen: dict[str, float], strip: re.Pattern) -> float:
    """Of tracked visits, the share whose parameter survives normalisation and so gets a cache key of its own."""
    sample = {"utm": "utm_source", "gclid": "gclid", "fbclid": "fbclid", "msclkid": "msclkid"}
    return sum(w for k, w in params_seen.items() if not strip.match(sample.get(k, k)))
