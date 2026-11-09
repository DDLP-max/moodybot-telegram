# -*- coding: utf-8 -*-
"""Standard X posts are 280 weighted characters."""
from x_integration.post_length import fit_x_post, trim_to_post, weighted_length


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


if __name__ == "__main__":
    test_weights_match_the_standard_cap()
    test_trim_and_shorten_stop_at_the_cap()
    print("post length ok")
