# -*- coding: utf-8 -*-
"""Final surface render — presentation only, never meaning.

Must run last in finalization. No module may modify text after this.
"""

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
    """Normalize typography/spacing after all rewrites. Returns (text, changed).

    This is the last text mutation allowed in the pipeline.
    """
    original = response or ""
    text = original

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Fancy quotes → straight (Telegram-safe, consistent)
    text = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )

    # Em/en dashes → spaced hyphen for cleaner mobile render
    text = re.sub(r"\s*[—–]\s*", " - ", text)

    # Fix orphan punctuation: "neutral ." / "word ,"
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)

    # Repair common rewrite fragments left mid-clause
    text = re.sub(r"\bit often\s+(\w+)", r"it often leans on \1", text, flags=re.IGNORECASE)

    # Duplicate punctuation
    text = re.sub(r"([.!?]){3,}", r"\1\1\1", text)  # keep ellipsis as ...
    text = re.sub(r"\.\s*\.\s*\.", "...", text)
    text = re.sub(r"([!?])\1+", r"\1", text)
    text = re.sub(r",,", ",", text)

    # Ellipsis spacing: "word..." not "word ..."
    text = re.sub(r"\s+\.\.\.", "...", text)

    # Collapse spaces
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Paragraph spacing: max one blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Repair broken paragraph starts after rewrites: "neutral.\n\nand" → capitalize
    def _cap_para(match: re.Match) -> str:
        return match.group(1) + match.group(2).upper()

    text = re.sub(r"([.!?])\n\n([a-z])", _cap_para, text)

    # Sentence-boundary repair after mid-sentence rewrites leaving lowercase after period
    text = re.sub(r"([.!?])\s+([a-z])", lambda m: f"{m.group(1)} {m.group(2).upper()}", text)

    # Trim line ends
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = text.strip()

    # Ensure closing punctuation on last non-emoji sentence if it ends with a letter
    body = text
    emoji_suffix = ""
    m = re.search(r"(.*?)(\s*🥃)?\s*$", text, flags=re.DOTALL)
    if m:
        body = (m.group(1) or "").rstrip()
        emoji_suffix = m.group(2) or ""
    if body and body[-1].isalnum():
        body += "."
    if append_whiskey:
        emoji_suffix = " 🥃"
    text = f"{body}{emoji_suffix}".strip()

    # Emoji spacing / dedupe (after optional append)
    text = re.sub(r"([^\s])(🥃)", r"\1 \2", text)
    text = re.sub(r"(🥃)(?:\s*🥃)+", r"\1", text)

    # Final whitespace pass
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text, text != original.strip()
