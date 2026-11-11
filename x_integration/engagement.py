# -*- coding: utf-8 -*-
"""Conversation-aware mention decision.

Shadow mode records this decision. It does not post. A mention of
@MoodyBotAI is required before a reply can be appropriate, and it is
not sufficient. Uncertain intent and missing context do not reply.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

DIRECT_REQUEST = "DIRECT_REQUEST"
FOLLOW_UP = "FOLLOW_UP"
CHALLENGE = "CHALLENGE"
CONTRIBUTION = "CONTRIBUTION"
AMBIENT = "AMBIENT"
SPAM = "SPAM"
UNSAFE = "UNSAFE"

_CLASSES = frozenset({
    DIRECT_REQUEST,
    FOLLOW_UP,
    CHALLENGE,
    CONTRIBUTION,
    AMBIENT,
    SPAM,
    UNSAFE,
})
_REPLY_CLASSES = frozenset({DIRECT_REQUEST, FOLLOW_UP, CHALLENGE})
_MENTION = re.compile(r"(?i)(?<!\w)@MoodyBotAI\b")
_CRISIS = re.compile(
    r"(?i)\b(?:kill myself|killing myself|end my life|want to die|wanna die|"
    r"suicide|suicidal|self[- ]harm|hurt myself|take my own life)\b"
)
_SPAM = re.compile(
    r"(?i)\b(?:giveaway|follow me|check out my|subscribe|promo code|airdrop|"
    r"dm me|turn on notifications)\b"
)
_EVIDENCE = re.compile(
    r"(?i)\b(?:evidence|sources?|citations?|prove|data|stud(?:y|ies))\b"
)
_CHALLENGE = re.compile(
    r"(?i)\b(?:i disagree|don't agree|do not agree|"
    r"that(?:'s| is) (?:wrong|false|not true)|contradict(?:s|ion)?|"
    r"makes no sense|you(?:'re| are) mistaken|not what you said)\b"
)
_FOLLOW = re.compile(
    r"(?i)\b(?:say more|go on|elaborate|clarify|what do you mean|explain that|"
    r"defend that|expand on|another example|give an example|for example)\b"
)
_DIRECT = re.compile(
    r"(?i)(?:"
    r"\bwhat(?:'s|\s+(?:is|are|should|do|would|can|about))\b|"
    r"\bwhy\b|"
    r"\bhow\s+(?:do|should|can|would|to|did|does)\b|"
    r"\b(?:can|could|would|will)\s+you\b|"
    r"\bshould\s+i\b|"
    r"\b(?:tell me|help me|weigh in)\b|"
    r"\byour\s+(?:take|thoughts|advice|view|opinion)\b|"
    r"\bplease\b"
    r")"
)
_GENERIC = re.compile(
    r"(?i)\b(?:stay patient|keep going|hang in|you(?:'ve| have) got|"
    r"don't give up|do not give up|one (?:small )?step|progress|momentum|"
    r"great point|thanks for sharing|so true|love this|well said)\b"
)
_EXPERIENCE = re.compile(
    r"(?i)\b(?:i (?:went|have|had|was|lost|learned|tried)|in my experience|"
    r"when i|my own)\b"
)
_CORRECTION = re.compile(
    r"(?i)\b(?:you(?:'re| are) wrong|that(?:'s| is) incorrect|correction|"
    r"you missed|the (?:date|number|claim) (?:is|was))\b"
)
_ACK = re.compile(r"(?i)\b(?:thanks for sharing|great point|nice point)\b")
_STALE = timedelta(hours=72)
_CONTEXT_LIMIT = 8


def decide_engagement(
    tweet: dict,
    *,
    user_id: str,
    floor: str,
    already_replied: bool,
    context: dict | None = None,
    conversation: dict | None = None,
    complete=None,
) -> dict:
    """Classify one mention. `complete` is the model, used only when rules are unsure."""
    post_id = str(tweet.get("id") or "").strip()
    author_id = str(tweet.get("author_id") or "").strip()
    username = str(tweet.get("author_username") or "")
    conversation_id = str(tweet.get("conversation_id") or post_id).strip()
    text = tweet.get("text") if isinstance(tweet.get("text"), str) else ""
    window = _window(tweet, context, user_id)
    base = {
        "post_id": post_id,
        "author_id": author_id,
        "conversation_id": conversation_id,
        "context_ids": window["ids"],
        "safety_flags": [],
        "model": "rules",
    }
    if not post_id.isdigit():
        return _pack(base, AMBIENT, 1.0, "invalid_id", False, "skip", "none", "none")
    if floor.isdigit() and int(post_id) <= int(floor):
        return _pack(base, AMBIENT, 1.0, "historical", False, "skip", "none", "none")
    if user_id and author_id == user_id:
        return _pack(base, AMBIENT, 1.0, "own_post", False, "skip", "none", "none")
    if username.lower().endswith("bot") and author_id != user_id:
        return _pack(base, SPAM, 0.95, "bot_loop", False, "skip", "C", "none", ["bot_loop"])
    body = _body(text)
    words = re.findall(r"[A-Za-z0-9']+", body)
    if _CRISIS.search(body):
        return _pack(
            base, UNSAFE, 0.98, "crisis", False, "skip", "safety", "safety_hold", ["crisis"]
        )
    if not _MENTION.search(text):
        return _pack(base, AMBIENT, 0.9, "not_mentioned", False, "skip", "C", "none")
    if not words:
        return _pack(base, AMBIENT, 0.99, "empty", False, "skip", "C", "none")
    if _SPAM.search(body):
        return _pack(base, SPAM, 0.96, "spam", False, "skip", "C", "none", ["spam"])

    decision = _intent(base, body, words, window)
    if decision.get("needs_model") and complete is not None:
        decision = _ask_model(decision, text, window, complete)
    decision.pop("needs_model", None)
    if already_replied:
        decision["respond"] = False
        decision["action"] = "skip"
        decision["reason"] = "duplicate_parent"
        decision["objective"] = "none"
    elif decision["respond"] and _over_conversation_cap(conversation):
        decision["respond"] = False
        decision["action"] = "skip"
        decision["reason"] = "conversation_limit"
        decision["objective"] = "none"
    elif (
        decision["classification"] == CONTRIBUTION
        and decision["respond"]
        and _stale(conversation)
    ):
        decision["respond"] = False
        decision["action"] = "observe"
        decision["reason"] = "stale"
        decision["objective"] = "none"
    if decision["classification"] == CONTRIBUTION and _ACK.search(decision.get("objective") or ""):
        decision["respond"] = False
        decision["action"] = "observe"
        decision["objective"] = "none"
        decision["reason"] = "empty_acknowledgment"
    return decision


def _intent(base: dict, body: str, words: list[str], window: dict) -> dict:
    participating = window["participating"]
    missing = window["missing_parent"]
    evidence = _EVIDENCE.search(body) is not None
    if evidence or _CHALLENGE.search(body):
        if missing and not evidence:
            return _pack(
                base, CHALLENGE, 0.45, "missing_context", False, "observe", "A",
                "answer_substance", ["missing_context"], needs_model=False,
            )
        flags = ["evidence"] if evidence else []
        objective = "separate_verified_from_uncertain" if evidence else "answer_substance"
        return _pack(base, CHALLENGE, 0.9, "challenge", True, "reply", "A", objective, flags)
    if _FOLLOW.search(body) and (participating or missing):
        if missing:
            return _pack(
                base, FOLLOW_UP, 0.44, "missing_context", False, "observe", "A",
                "elaborate", ["missing_context"],
            )
        return _pack(base, FOLLOW_UP, 0.9, "follow_up", True, "reply", "A", "elaborate")
    requested = _DIRECT.search(body) is not None or ("?" in body and len(words) >= 3)
    if requested:
        if missing and _DIRECT.search(body) is None:
            return _pack(
                base, DIRECT_REQUEST, 0.42, "missing_context", False, "observe", "A",
                "answer_request", ["missing_context"],
            )
        return _pack(
            base, DIRECT_REQUEST, 0.9, "direct_request", True, "reply", "A", "answer_request"
        )
    generic = _GENERIC.search(body) is not None
    meaningful = _EXPERIENCE.search(body) is not None or _CORRECTION.search(body) is not None
    if generic and not meaningful:
        return _pack(
            base, CONTRIBUTION, 0.93, "generic_encouragement", False, "observe", "B", "none"
        )
    if meaningful and len(words) >= 12 and participating and not missing:
        return _pack(base, CONTRIBUTION, 0.86, "meaningful", True, "reply", "B", "add_an_idea")
    if meaningful and missing:
        return _pack(
            base, CONTRIBUTION, 0.4, "missing_context", False, "observe", "B", "none",
            ["missing_context"],
        )
    if participating or generic or meaningful:
        return _pack(base, CONTRIBUTION, 0.8, "contribution", False, "observe", "B", "none")
    if missing:
        return _pack(
            base, AMBIENT, 0.4, "missing_context", False, "observe", "C", "none",
            ["missing_context"],
        )
    return _pack(
        base, AMBIENT, 0.5, "review", False, "observe", "C", "none", needs_model=True
    )


def _ask_model(ruled: dict, text: str, window: dict, complete) -> dict:
    prior = [
        {
            "id": post["id"],
            "author_is_bot": post["author_is_bot"],
            "text": post["text"][:240],
        }
        for post in window["posts"][:-1]
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "Classify one X mention of @MoodyBotAI. Return one JSON object "
                "with classification, confidence, reason, objective. "
                "classification is DIRECT_REQUEST, FOLLOW_UP, CHALLENGE, "
                "CONTRIBUTION, AMBIENT, SPAM, or UNSAFE. "
                "A mention is not enough. Use AMBIENT when the person is not "
                "addressing MoodyBot. Use UNSAFE for imminent self-harm and "
                "do not joke. Use CHALLENGE when the person disputes a claim "
                "or asks for evidence. Do not invent facts. If unsure, AMBIENT."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {"text": text[:500], "prior": prior, "missing_parent": window["missing_parent"]},
                ensure_ascii=False,
            ),
        },
    ]
    try:
        raw = complete(messages)
        parsed = _parse_model(raw)
    except Exception:
        ruled["reason"] = "model_unavailable"
        ruled["respond"] = False
        ruled["action"] = "observe"
        ruled["model"] = "unavailable"
        ruled["needs_model"] = False
        return ruled
    kind = str(parsed.get("classification") or "").strip().upper()
    if kind not in _CLASSES:
        ruled["reason"] = "model_unavailable"
        ruled["respond"] = False
        ruled["action"] = "observe"
        ruled["model"] = "unavailable"
        return ruled
    try:
        confidence = float(parsed.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.5
    if confidence < 0:
        confidence = 0.0
    if confidence > 1:
        confidence = 1.0
    objective = str(parsed.get("objective") or "none").strip()[:80] or "none"
    reason = str(parsed.get("reason") or "model").strip()[:80] or "model"
    flags = list(ruled.get("safety_flags") or [])
    if kind == CHALLENGE and _EVIDENCE.search(text):
        if "evidence" not in flags:
            flags.append("evidence")
        objective = "separate_verified_from_uncertain"
    respond = False
    action = "observe"
    mode = "C"
    if kind in _REPLY_CLASSES and confidence >= 0.6 and not window["missing_parent"]:
        respond = True
        action = "reply"
        mode = "A"
    elif (
        kind == CONTRIBUTION
        and confidence >= 0.8
        and window["participating"]
        and not window["missing_parent"]
        and not _ACK.search(objective)
        and not _GENERIC.search(_body(text))
    ):
        respond = True
        action = "reply"
        mode = "B"
        objective = "add_an_idea"
    elif kind == UNSAFE:
        action = "skip"
        mode = "safety"
        objective = "safety_hold"
        if "crisis" not in flags:
            flags.append("crisis")
    elif kind == SPAM:
        action = "skip"
        mode = "C"
        objective = "none"
    elif kind == CONTRIBUTION:
        mode = "B"
        objective = "none"
    ruled.update({
        "classification": kind,
        "confidence": confidence,
        "reason": reason,
        "respond": respond,
        "action": action,
        "mode": mode,
        "objective": objective,
        "safety_flags": flags,
        "model": "model",
        "needs_model": False,
    })
    return ruled


def _window(tweet: dict, context: dict | None, user_id: str) -> dict:
    supplied = []
    if isinstance(context, dict):
        supplied = [item for item in context.get("posts") or [] if isinstance(item, dict)]
    elif isinstance(tweet.get("context_posts"), list):
        supplied = [item for item in tweet.get("context_posts") or [] if isinstance(item, dict)]
    posts = []
    seen = set()

    def add(post_id: str, author_id: str, text: str) -> None:
        if not post_id or post_id in seen:
            return
        seen.add(post_id)
        posts.append({
            "id": post_id,
            "author_id": author_id,
            "author_is_bot": bool(user_id) and author_id == user_id,
            "text": text if isinstance(text, str) else "",
        })

    for item in supplied:
        add(
            str(item.get("id") or ""),
            str(item.get("author_id") or ""),
            item.get("text") if isinstance(item.get("text"), str) else "",
        )
    parent_id = str(tweet.get("parent_id") or "")
    parent_text = tweet.get("parent_text") if isinstance(tweet.get("parent_text"), str) else ""
    add(parent_id, str(tweet.get("parent_author_id") or ""), parent_text)
    add(
        str(tweet.get("id") or ""),
        str(tweet.get("author_id") or ""),
        tweet.get("text") if isinstance(tweet.get("text"), str) else "",
    )
    posts = posts[-_CONTEXT_LIMIT:]
    participating = any(post["author_is_bot"] for post in posts[:-1])
    missing_parent = bool(parent_id) and not parent_text.strip()
    return {
        "posts": posts,
        "ids": [post["id"] for post in posts],
        "participating": participating,
        "missing_parent": missing_parent,
    }


def _over_conversation_cap(conversation: dict | None) -> bool:
    if not isinstance(conversation, dict):
        return False
    try:
        used = int(conversation.get("bot_replies_24h") or 0)
    except (TypeError, ValueError):
        return False
    from x_integration.state import conversation_reply_limit

    return used >= conversation_reply_limit()


def _stale(conversation: dict | None) -> bool:
    if not isinstance(conversation, dict):
        return False
    raw = str(conversation.get("last_interaction_at") or "").strip()
    if not raw:
        return False
    try:
        seen = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - seen > _STALE


def _body(text: str) -> str:
    stripped = _MENTION.sub(" ", text)
    return re.sub(r"(?i)@\w+", " ", stripped)


def _parse_model(raw: str) -> dict:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("model json")
    return loaded


def _pack(
    base: dict,
    classification: str,
    confidence: float,
    reason: str,
    respond: bool,
    action: str,
    mode: str,
    objective: str,
    safety_flags: list | None = None,
    needs_model: bool = False,
) -> dict:
    packed = dict(base)
    packed.update({
        "classification": classification,
        "confidence": confidence,
        "reason": reason,
        "respond": respond,
        "action": action,
        "mode": mode,
        "objective": objective,
        "safety_flags": list(safety_flags or []),
        "needs_model": needs_model,
    })
    return packed
