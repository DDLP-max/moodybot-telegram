# -*- coding: utf-8 -*-
"""Draft a mention reply with the Telegram personality path.

Routing, the response plan, and the finalizer are the same functions
the Telegram handler calls. This module does not post to X.
"""
from __future__ import annotations

import contextvars
import logging
from typing import Callable, List, Optional

generation_post: contextvars.ContextVar[str] = contextvars.ContextVar(
    "x_generation_post",
    default="",
)

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
    post_text = text
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
    from generation_gate import reject_reason, retry_messages, settle_authored_interior

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
    from question_scope import assess_answer, extract_questions, revision_instruction, settle_reply

    try:
        extraction = extract_questions(
            post_text,
            channel="x" if "@MoodyBotAI" in (post_text or "") else "direct",
        )
        if not extraction["questions"] and brief.strip():
            extraction = extract_questions(brief, channel="direct")
    except Exception as exc:
        raise RuntimeError("incomplete_answer") from exc
    if extraction["questions"]:
        verdicts = assess_answer(extraction, text_out)
        if any(item.get("verdict") != "answered" for item in verdicts):
            revised = (complete or openrouter_complete)(
                retry_messages(messages, revision_instruction(extraction, verdicts))
            )
            revised_content = moodybot.clean_response(moodybot.process_bot_output(revised))
            revised_final = moodybot.finalize_response(
                revised_content,
                user_input,
                plan,
                selected_command=selected,
                channel="x",
                mode="dynamic",
                prompt_hash=runtime.prompt_hash,
            )
            text_out = moodybot.safe_emoji(revised_final.text)
        from x_integration.post_length import autonomous_limit

        def _shorten(instruction: str) -> str:
            rewritten = (complete or openrouter_complete)(
                [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": text_out},
                ]
            )
            return moodybot.safe_emoji(moodybot.clean_response(rewritten))

        settled = settle_reply(
            extraction,
            text_out,
            limit=autonomous_limit(),
            shorten=_shorten,
        )
        if not settled["publish"]:
            raise RuntimeError("incomplete_answer")
        text_out = settled["text"]
    else:
        from x_integration.post_length import autonomous_limit, weighted_length

        limit = autonomous_limit()
        if weighted_length(text_out) > limit:
            caller = complete or openrouter_complete
            rewritten = caller(
                [
                    {
                        "role": "system",
                        "content": (
                            "Rewrite this reply in the same voice so it fits one X post. "
                            f"The hard limit is {limit} weighted characters: emoji count as two, "
                            "and a link counts as 23. If the full request cannot fit, give an "
                            "honest partial or decline. Do not claim a list is complete when it is not. "
                            "Do not cut a sentence in half. Return only the reply."
                        ),
                    },
                    {"role": "user", "content": text_out},
                ]
            )
            compressed = moodybot.safe_emoji(moodybot.clean_response(rewritten))
            if not compressed or weighted_length(compressed) > limit:
                raise RuntimeError("reply_too_long")
            text_out = compressed
    try:
        live_log.append_exchange(key, user_input, text_out)
    except Exception:
        logger.warning("X conversation log failed")
    return text_out


def _with_post_limit(messages: List[dict]) -> List[dict]:
    """Tell the existing engine the post cap. The last user turn stays last."""
    from x_integration.post_length import autonomous_limit

    note = {
        "role": "system",
        "content": (
            "This reply will be posted on X. Hard limit: "
            f"{autonomous_limit()} weighted characters. "
            "Emoji count as two characters. A link counts as 23. "
            "This limit applies only to this X post and overrides any request for a "
            "list, a count, or a long explanation. Do not try to fit ten items. "
            "Give a truthful short answer, or decline. Do not claim the full request "
            "was completed. One post. Stop before the limit."
        ),
    }
    prepared = list(messages)
    if prepared and prepared[-1].get("role") == "user":
        return prepared[:-1] + [note, prepared[-1]]
    return prepared + [note]


def _provider_error(exc: Exception) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int) and status > 0:
        return f"openrouter_http_{status}"
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return "openrouter_timeout"
    return "openrouter_transport"


def openrouter_complete(messages: List[dict]) -> str:
    import httpx
    import moodybot
    from x_integration.state import ledger_from_env, operating_mode

    if not moodybot.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    track = operating_mode() == "live_test"
    book = ledger_from_env() if track else None
    call_id = None
    if book is not None:
        call_id = book.reserve_generation_call(generation_post.get())
        if call_id is None:
            book.note_generation_error("budget_exhausted")
            raise RuntimeError("budget_exhausted")
    try:
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
                    "usage": {"include": True},
                },
            )
        response.raise_for_status()
        body = response.json()
    except RuntimeError:
        raise
    except Exception as exc:
        if call_id is not None and book is not None:
            book.settle_generation_call(call_id, error=_provider_error(exc))
        raise
    usage = body.get("usage") if isinstance(body, dict) else None
    if call_id is not None and book is not None:
        book.settle_generation_call(call_id, usage=usage if isinstance(usage, dict) else {})
    return body["choices"][0]["message"]["content"]
