# -*- coding: utf-8 -*-
"""CRC and delivery signatures for X webhooks.

The signing key is the app's OAuth 2.0 client secret. The OAuth 1.0
consumer secret is only the legacy fallback. Neither is a bearer token.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os


def oauth2_client_secret() -> str:
    return (os.environ.get("X_OAUTH2_CLIENT_SECRET") or "").strip()


def oauth1_consumer_secret() -> str:
    return (os.environ.get("X_OAUTH1_CONSUMER_SECRET") or "").strip()


def sign(secret: str, message: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return "sha256=" + base64.b64encode(digest).decode("utf-8")


def crc_response(crc_token: str, secret: str) -> dict:
    return {"response_token": sign(secret, crc_token.encode("utf-8"))}


def signatures_match(expected: str, presented: str) -> bool:
    if not expected or not presented or len(expected) != len(presented):
        return False
    return hmac.compare_digest(expected, presented)


def delivery_is_authentic(
    raw_body: bytes,
    headers,
    *,
    oauth2_secret: str = "",
    oauth1_secret: str = "",
) -> bool:
    """Prefer the OAuth 2.0 header. Fall back to the legacy header."""
    oauth2_header = _header(headers, "X-Twitter-Webhooks-Signature-OAuth2")
    if oauth2_header is not None:
        if not oauth2_secret:
            return False
        return signatures_match(sign(oauth2_secret, raw_body), oauth2_header)
    legacy = _header(headers, "X-Twitter-Webhooks-Signature")
    if legacy is not None and oauth1_secret:
        return signatures_match(sign(oauth1_secret, raw_body), legacy)
    return False


def _header(headers, name: str):
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    value = getter(name)
    if value is None:
        value = getter(name.lower())
    if value is None:
        return None
    text = str(value).strip()
    return text or None
