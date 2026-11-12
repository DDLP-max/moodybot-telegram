# -*- coding: utf-8 -*-
"""Standard X posts are 280 weighted characters."""
import os

from x_integration.post_length import (
    autonomous_limit,
    fit_x_post,
    fits_autonomous,
    trim_to_post,
    weighted_length,
)


def test_weights_match_the_standard_cap():
    assert weighted_length("a" * 280) == 280
    assert weighted_length("a" * 281) == 281
    assert weighted_length("a" * 278 + "\U0001f943") == 280
    assert weighted_length("see https://example.com/path") == 4 + 23


def test_trim_and_shorten_stop_at_the_cap():
    long_text = ("One sentence stays. " * 20).strip()
    assert weighted_length(long_text) > 280
    trimmed = trim_to_post(long_text)
    assert weighted_length(trimmed) <= 280
    assert trimmed.endswith(".")

    def shorten(_text):
        return "Short enough."

    assert fit_x_post(long_text, shorten) == "Short enough."
    assert weighted_length(fit_x_post(long_text, lambda _text: long_text)) <= 280


def test_autonomous_limit_boundaries():
    assert autonomous_limit() == 280
    assert fits_autonomous("a" * 279)
    assert fits_autonomous("a" * 280)
    assert not fits_autonomous("a" * 281)
    emoji = "\U0001f943"
    assert weighted_length(emoji) == 2
    assert fits_autonomous("a" * 277 + emoji)
    assert weighted_length("a" * 277 + emoji) == 279
    assert fits_autonomous("a" * 278 + emoji)
    assert weighted_length("a" * 278 + emoji) == 280
    assert not fits_autonomous("a" * 279 + emoji)
    assert weighted_length("a" * 279 + emoji) == 281
    url = "https://example.com/path"
    assert weighted_length(url) == 23
    assert fits_autonomous("a" * (279 - 23) + url)
    assert weighted_length("a" * (279 - 23) + url) == 279
    assert fits_autonomous("a" * (280 - 23) + url)
    assert weighted_length("a" * (280 - 23) + url) == 280
    assert not fits_autonomous("a" * (281 - 23) + url)
    assert weighted_length("a" * (281 - 23) + url) == 281
    os.environ["X_AUTONOMOUS_CHAR_LIMIT"] = "400"
    try:
        assert autonomous_limit() == 400
        assert fits_autonomous("a" * 400)
        assert not fits_autonomous("a" * 401)
    finally:
        os.environ.pop("X_AUTONOMOUS_CHAR_LIMIT", None)
    assert autonomous_limit() == 280


if __name__ == "__main__":
    test_weights_match_the_standard_cap()
    test_trim_and_shorten_stop_at_the_cap()
    test_autonomous_limit_boundaries()
    print("post length ok")
