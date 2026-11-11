# -*- coding: utf-8 -*-
"""Draft a mention reply with the Telegram personality path.

Routing, the response plan, and the finalizer are the same functions
the Telegram handler calls. This module does not post to X.
"""
from __future__ import annotations

import logging
from typing import Callable, List, Optional

logger = logging.getLogger("moodybot")

Complete = Callable[[List[dict]], str]


def _accepts(fn, name: str) -> bool:
    import inspect

    return name in inspect.signature(fn).parameters


def conversation_key(conversation_id: str) -> str:
    safe = "".join(ch for ch in str(conversation_id) if ch.isalnum() or ch in {"-", "_"})
    return f"x-{safe or 'unknown'}"


def draft_mention_reply(
    text: str,
    conversation_id: str,
    *,
    complete: Optional[Complete] = None,
    brief: str = "",
) -> str:
    """Plan and finalize one mention. `complete` stands in for the model in a dry run."""
    if brief.strip():
        text = brief.strip() + "\n\n" + (text or "")
    import moodybot
    from capability_detection import classify_social_mode
    from prompt_runtime import build_openrouter_messages, build_runtime_prompt

    user_input = moodybot.process_user_input(text)
    social = classify_social_mode(user_input)
    typed_slash = any(
        cmd in (user_input or "").lower()
        for cmd in (
            "/savage", "/roast", "/cut", "/validate", "/jukebox", "/velvet",
            "/noir", "/clinical", "/dark", "/ghost", "/numb", "/cinema",
            "/sensory", "/tighten", "/contrast", "/godfather", "/spiral",
            "/villain", "/thoughts",
        )
    )
    selected = moodybot.route_command(user_input)
    if social.blocks_topical_auto_route and not typed_slash:
        selected = "/thoughts"
        source = "social-first"
    elif not selected:
        selected = moodybot.select_best_command(user_input)
        source = "classifier"
    else:
        source = "explicit" if typed_slash else "auto-route"

    key = conversation_key(conversation_id)
    from conversation_context import conversation_log as live_log

    prior = live_log.recent(key)
    plan_kwargs = {
        "selected_command": selected,
        "channel": "x",
        "mode": "dynamic",
        "tone_source": source,
    }
    if _accepts(moodybot.build_response_plan, "history"):
        plan_kwargs["history"] = prior
    plan = moodybot.build_response_plan(user_input, **plan_kwargs)
    inject = None
    if not (social.blocks_topical_auto_route and not typed_slash):
        inject = moodybot.structure_prompt_for(selected, social=social, plan=plan)
    runtime = build_runtime_prompt(
        plan,
        social=social,
        selected_command=selected,
        structure_prompt=inject or "",
    )
    if _accepts(build_openrouter_messages, "history"):
        messages = build_openrouter_messages(runtime, user_input, history=prior)
    else:
        messages = build_openrouter_messages(runtime, user_input)
    messages = _with_post_limit(messages)
    raw = (complete or openrouter_complete)(messages)
    from generation_gate import reject_reason, settle_authored_interior

    structure = (
        getattr(plan, "routed_structure", None)
        or getattr(plan, "preferred_structure", None)
        or "SNAP"
    )
    budget = getattr(plan, "response_budget", None) or "medium"
    reason = reject_reason(user_input, raw, structure, budget)
    if reason:
        from generation_gate import retry_messages

        retry = (complete or openrouter_complete)(retry_messages(messages, reason))
        raw, _source = settle_authored_interior(
            user_input, raw, retry, structure, budget
        )
    content = moodybot.process_bot_output(raw)
    content = moodybot.clean_response(content)
    finalized = moodybot.finalize_response(
        content,
        user_input,
        plan,
        selected_command=selected,
        channel="x",
        mode="dynamic",
        prompt_hash=runtime.prompt_hash,
    )
    text_out = moodybot.safe_emoji(finalized.text)
    from x_integration.post_length import AUTONOMOUS_LIMIT, fit_x_post, weighted_length

    if weighted_length(text_out) > AUTONOMOUS_LIMIT:
        caller = complete or openrouter_complete

        def _shorten(current: str) -> str:
            rewritten = caller(
                [
                    {
                        "role": "system",
                        "content": (
                            "Shorten this reply so it fits one X post. "
                            "The hard limit is 200 weighted characters: emoji count as two, "
                            "and a link counts as 23. Keep the same point and the closing "
                            "emoji when it still fits. Return only the reply."
                        ),
                    },
                    {"role": "user", "content": current},
                ]
            )
            return moodybot.safe_emoji(moodybot.clean_response(rewritten))

        text_out = fit_x_post(text_out, _shorten, AUTONOMOUS_LIMIT)
    try:
        live_log.append_exchange(key, user_input, text_out)
    except Exception:
        logger.warning("X conversation log failed")
    return text_out


def _with_post_limit(messages: List[dict]) -> List[dict]:
    """Tell the existing engine the post cap. The last user turn stays last."""
    note = {
        "role": "system",
        "content": (
            "This reply will be posted on X. Hard limit: 200 weighted characters. "
            "Emoji count as two characters. A link counts as 23. "
            "One post, one paragraph. Stop before the limit."
        ),
    }
    prepared = list(messages)
    if prepared and prepared[-1].get("role") == "user":
        return prepared[:-1] + [note, prepared[-1]]
    return prepared + [note]


def openrouter_complete(messages: List[dict]) -> str:
    import httpx
    import moodybot

    if not moodybot.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    with httpx.Client(timeout=20) as client:
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {moodybot.OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://moodybot.ai",
                "X-Title": "MoodyBot",
            },
            json={
                "model": moodybot.OPENROUTER_MODEL,
                "messages": messages,
                "max_tokens": 1000,
            },
        )
    response.raise_for_status()
    body = response.json()
    return body["choices"][0]["message"]["content"]
