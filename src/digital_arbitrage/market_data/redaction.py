"""Redaction for stored market-data records.

Two layers, deliberately not relying on "just drop the headers":

1. :func:`redact_request` - converts an :class:`HttpRequest` into a storable
   description containing method + URL only. Headers are structurally absent
   (never serialised), so ``Authorization`` bearer tokens, ``x-api-key`` and
   cookies cannot leak into storage. Query parameters whose *names* look
   credential-like are additionally masked as defence in depth.
2. :func:`redact_payload` - scans the response body *content* for secrets and
   unnecessary personal details: JWT/bearer-shaped strings, denylisted JSON
   keys (``access_token``, ``client_secret``, ...), eBay affiliate tracking
   URLs, and seller usernames (replaced by a stable pseudonymous key unless
   ``keep_seller_usernames`` is set).

Every stored payload is stamped with :data:`REDACTION_VERSION` so the exact
algorithm applied is auditable.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from typing import Any

from ..providers.live.http import HttpRequest

#: Query-parameter names whose values are masked in stored request URLs.
_CREDENTIAL_PARAM_NAMES = re.compile(
    r"(?i)(access_?token|refresh_?token|id_?token|api_?key|apikey|"
    r"client_?secret|secret|password|authorization|auth|jwt|session)"
)
#: Bearer/JWT-shaped strings anywhere in a payload body.
_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{8,}")
#: JSON keys whose values are replaced wherever they appear in a payload.
_DENYLIST_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "api_key",
        "authorization",
        "itemAffiliateWebUrl",  # affiliate tracking link - unnecessary
    }
)
_REDACTED = "<redacted>"


def seller_pseudonym(provider: str, username: str) -> str:
    """Stable, non-reversible seller key for counts and seller history."""
    digest = hashlib.sha256(f"{provider}|{username.strip().lower()}".encode()).hexdigest()
    return f"sel_{digest[:16]}"


def redact_request(request: HttpRequest) -> dict[str, Any]:
    """Return a storable request description: method + sanitised URL.

    Headers are never read or serialised - credentials cannot leak through
    this path even if a caller accidentally injects them.
    """
    split = urllib.parse.urlsplit(request.full_url())
    params = urllib.parse.parse_qsl(split.query, keep_blank_values=True)
    safe_query = urllib.parse.urlencode(
        [(k, _REDACTED if _CREDENTIAL_PARAM_NAMES.search(k) else v) for k, v in params]
    )
    safe_url = urllib.parse.urlunsplit((split.scheme, split.netloc, split.path, safe_query, ""))
    return {"method": request.method.upper(), "url": safe_url}


def _redact_json_value(key: str, value: Any, provider: str, keep_sellers: bool) -> Any:
    if key in _DENYLIST_KEYS:
        return _REDACTED
    if key == "username" and isinstance(value, str) and not keep_sellers:
        return seller_pseudonym(provider, value)
    if isinstance(value, dict):
        return _redact_json_tree(value, provider, keep_sellers)
    if isinstance(value, list):
        return [_redact_json_tree(v, provider, keep_sellers) for v in value]
    if isinstance(value, str):
        return _scrub_secret_strings(value)
    return value


def _redact_json_tree(node: Any, provider: str, keep_sellers: bool) -> Any:
    if isinstance(node, dict):
        return {k: _redact_json_value(k, v, provider, keep_sellers) for k, v in node.items()}
    if isinstance(node, list):
        return [_redact_json_tree(v, provider, keep_sellers) for v in node]
    if isinstance(node, str):
        return _scrub_secret_strings(node)
    return node


def _scrub_secret_strings(text: str) -> str:
    text = _JWT_PATTERN.sub("<redacted-jwt>", text)
    return _BEARER_PATTERN.sub("Bearer <redacted>", text)


def redact_payload(body: bytes | str, *, provider: str, keep_seller_usernames: bool = False) -> str:
    """Return a sanitised payload string safe to persist.

    JSON bodies are redacted field-by-field; non-JSON bodies are scanned for
    secret-shaped strings only. Stamped algorithm: :data:`REDACTION_VERSION`.
    """
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return _scrub_secret_strings(text)
    return json.dumps(
        _redact_json_tree(parsed, provider, keep_seller_usernames),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
