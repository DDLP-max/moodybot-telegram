# -*- coding: utf-8 -*-
"""Final surface render — typography only. Never meaning. Never prose repair."""

from __future__ import annotations

import re
from typing import Tuple


def response_text_after_surface_semantically_equals(
    after_landing: str,
    after_surface: str,
) -> bool:
    """True if surface render did not append a new sentence or banned closer."""

    def _norm(t: str) -> str:
        return re.sub(
            r"\s+",
            " ",
            (t or "")
            .replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
            .replace("—", "-")
            .replace("–", "-")
            .replace("🥃", "")
            .strip()
            .lower(),
        )

    a = _norm(after_landing)
    b = _norm(after_surface)
    if re.search(r"seen it named|what about .+ looks different", after_surface or "", re.I):
        return False
    a_sents = [s for s in re.split(r"(?<=[.!?])\s+", a) if s.strip()]
    b_sents = [s for s in re.split(r"(?<=[.!?])\s+", b) if s.strip()]
    if len(b_sents) > len(a_sents):
        return False
    return True


def final_surface_render(response: str, *, append_whiskey: bool = True) -> Tuple[str, bool]:
    """Normalize whitespace/quotes only. No prose repair. No cadence changes."""
    original = (response or "").strip()
    text = original

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )
    text = re.sub(r"\s*[—–]\s*", " - ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n")).strip()

    if append_whiskey and "🥃" not in text:
        text = f"{text} 🥃".strip()

    text = re.sub(r"([^\s])(🥃)", r"\1 \2", text)
    text = re.sub(r"(🥃)(?:\s*🥃)+", r"\1", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text, text != original
