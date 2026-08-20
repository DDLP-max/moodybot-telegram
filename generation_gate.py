# -*- coding: utf-8 -*-
"""Semantic reject-once gate. Not a finalizer rewrite.

generate → evaluate → authored_interior? → discard → regenerate once
→ evaluate → ship retry if valid, else a conservative grounded fallback.

Never ship a known authored_interior violation. Do not repair the invalid prose.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from gold_shape import evaluate_gold_shape

SEMANTIC_REJECT_ONCE = frozenset({"authored_interior"})

AUTHORED_INTERIOR_RETRY = (
    "REJECTED: authored_interior. You invented an unestablished private motive. "
    "Rewrite using only the established object and permitted inference. "
    "Heat the contradiction; do not answer the rhetorical why with psychology."
)

# Object-level SNAP. No unobserved interior. Used only after first + retry both fail.
CONSERVATIVE_FALLBACK = (
    "The setup already contains the problem. A private why wouldn't fix it."
)


def is_authored_interior(
    user_message: str,
    draft: str,
    structure: str = "SNAP",
    response_budget: str = "medium",
) -> bool:
    fails = evaluate_gold_shape(
        user_message, draft, structure, response_budget=response_budget
    )
    return "authored_interior" in fails


def reject_reason(
    user_message: str,
    draft: str,
    structure: str = "SNAP",
    response_budget: str = "medium",
) -> Optional[str]:
    """Return the surgical retry instruction if the draft is invalid, else None."""
    if not is_authored_interior(user_message, draft, structure, response_budget):
        return None
    return AUTHORED_INTERIOR_RETRY


def retry_messages(
    messages: List[Dict[str, Any]],
    reason: str = AUTHORED_INTERIOR_RETRY,
) -> List[Dict[str, Any]]:
    """Append a reject-once instruction. Do not feed the discarded draft back."""
    return list(messages) + [
        {
            "role": "system",
            "content": reason,
        }
    ]


def settle_authored_interior(
    user_message: str,
    first: str,
    retry: Optional[str] = None,
    structure: str = "SNAP",
    response_budget: str = "medium",
) -> Tuple[str, str]:
    """Pick a shippable draft. Never returns a known authored_interior violation.

    source: first | retry | fallback
    """
    if not is_authored_interior(user_message, first, structure, response_budget):
        return first, "first"
    if retry and not is_authored_interior(
        user_message, retry, structure, response_budget
    ):
        return retry, "retry"
    return CONSERVATIVE_FALLBACK, "fallback"
