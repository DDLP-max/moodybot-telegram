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
DIRECT_CHALLENGE = "DIRECT_CHALLENGE"
CONTRIBUTION = "CONTRIBUTION"
AMBIENT = "AMBIENT"
SPAM = "SPAM"
UNSAFE = "UNSAFE"

_CLASSES = frozenset({
    DIRECT_REQUEST,
    FOLLOW_UP,
    CHALLENGE,
    DIRECT_CHALLENGE,
    CONTRIBUTION,
    AMBIENT,
    SPAM,
    UNSAFE,
})
_REPLY_CLASSES = frozenset({DIRECT_REQUEST, FOLLOW_UP, CHALLENGE, DIRECT_CHALLENGE})
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
_CLAUSE_REQUEST = re.compile(
    r"(?i)(?:"
    r"\bwhat(?:'s|\s+(?:is|are|should|do|would|can|about))\b|"
    r"\bwhy\s+(?:do|does|is|are|would|should|did|can)\b|"
    r"\bhow\s+(?:do|does|should|can|would|to|did)\b|"
    r"\b(?:can|could|would|will)\s+you\b|"
    r"\bshould\s+i\b|"
    r"\b(?:explain|tell me|help me|weigh in|clarify)\b|"
    r"\byour\s+(?:take|thoughts|advice|view|opinion|source)\b|"
    r"\bplease\b"
    r")"
)
_THIRD_PARTY = re.compile(
    r"(?i)(?:\b(?:you|someone|people|we|just|please|go)\s+)?"
    r"(?:\bshould\s+)?\b(?:ask|asking|asked|tell|telling|consult|ping)\s+@MoodyBotAI\b"
)
_VOCATIVE = re.compile(
    r"(?i)(?:^|[\n.!?]\s*)(?:(?:hey|hi|ok|okay)\s+)?@MoodyBotAI\b[,:]?\s*(?P<clause>.*)$",
    re.S,
)
_INVITE = re.compile(
    r"(?i)(?:"
    r"\byour\s+(?:answer|turn)\b|"
    r"\bsame\s+question\b|"
    r"\bsecond\s+opinion\b|"
    r"\bdo\s+you\s+agree\b|"
    r"\bcan\s+you\s+verify\b|"
    r"\bwhat(?:'s|\s+is)\s+your\s+answer\b|"
    r"@MoodyBotAI(?:'s|’s)\s+take\b|"
    r"\bhear\s+@MoodyBotAI(?:'s|’s)?\s+take\b|"
    r"\bexplain\s+why\s+(?:he|she|they)(?:'s|\s+is|\s+are|'re)?\s+wrong\b"
    r")"
)
_UNTRUSTED = re.compile(
    r"(?i)\b(?:ignore (?:your|all|previous) (?:rules|instructions|safety)|"
    r"enable publishing|reset the gate|post anyway|bypass)\b"
)
_DECISION_TTL = timedelta(hours=24)
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
    text, text_complete, text_source = read_post_text(tweet)
    window = _window(tweet, context, user_id)
    base = {
        "post_id": post_id,
        "author_id": author_id,
        "author_username": username,
        "conversation_id": conversation_id,
        "context_ids": window["ids"],
        "safety_flags": [],
        "model": "rules",
        "text_complete": text_complete,
        "text_source": text_source,
    }
    if not post_id.isdigit():
        return _pack(base, AMBIENT, 1.0, "invalid_id", False, "skip", "none", "none")
    if floor.isdigit() and int(post_id) <= int(floor):
        return _pack(base, AMBIENT, 1.0, "historical", False, "skip", "none", "none")
    if user_id and author_id == user_id:
        return _pack(base, AMBIENT, 1.0, "own_post", False, "skip", "none", "none")
    if username.lower().endswith("bot") and author_id != user_id and not _known_ai(author_id, username):
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

    decision = _intent(base, text, body, words, window, tweet)
    if not text_complete:
        flags = list(decision.get("safety_flags") or [])
        if "truncated" not in flags:
            flags.append("truncated")
        decision["safety_flags"] = flags
        decision["text_complete"] = False
        if decision.get("respond"):
            decision["respond"] = False
            decision["action"] = "observe"
            decision["reason"] = "incomplete_text"
            decision["objective"] = "none"
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
    _apply_ai_loop(decision, tweet, username, conversation)
    return decision


def _intent(base: dict, text: str, body: str, words: list[str], window: dict, tweet: dict) -> dict:
    """Request language counts only in a clause addressed to MoodyBot."""
    participating = window["participating"]
    missing = window["missing_parent"]
    if _quoted_only(text):
        return _pack(base, AMBIENT, 0.95, "quotation", False, "observe", "C", "none")
    unquoted = _outside_quotes(text)
    if _direct_invite(unquoted):
        return _invitation(base, text, unquoted, window, tweet)
    if _THIRD_PARTY.search(unquoted):
        return _pack(base, AMBIENT, 0.96, "not_requested", False, "observe", "C", "none")
    clause = _vocative_clause(text)
    if clause is not None and not re.search(r"[A-Za-z0-9]", clause):
        return _pack(base, AMBIENT, 0.94, "not_requested", False, "observe", "C", "none")
    if clause is None:
        if _other_account_question(text) or not participating:
            if missing and not _GENERIC.search(body):
                return _pack(
                    base, AMBIENT, 0.9, "missing_context", False, "observe", "C", "none",
                    ["missing_context"],
                )
            if participating or _GENERIC.search(body) or _EXPERIENCE.search(body):
                return _contribution(base, body, words, participating, missing)
            return _pack(base, AMBIENT, 0.92, "not_requested", False, "observe", "C", "none")
        return _contribution(base, body, words, participating, missing)
    if (_EVIDENCE.search(clause) or _CHALLENGE.search(clause)):
        if missing and not _EVIDENCE.search(clause):
            return _pack(
                base, CHALLENGE, 0.45, "missing_context", False, "observe", "A",
                "answer_substance", ["missing_context"],
            )
        flags = ["evidence"] if _EVIDENCE.search(clause) else []
        objective = "separate_verified_from_uncertain" if flags else "answer_substance"
        return _pack(base, CHALLENGE, 0.92, "challenge", True, "reply", "A", objective, flags)
    if _FOLLOW.search(clause) and participating:
        if missing:
            return _pack(
                base, FOLLOW_UP, 0.44, "missing_context", False, "observe", "A",
                "elaborate", ["missing_context"],
            )
        return _pack(base, FOLLOW_UP, 0.92, "follow_up", True, "reply", "A", "elaborate")
    if _clause_request(clause):
        decision = _pack(
            base, DIRECT_REQUEST, 0.93, "direct_request", True, "reply", "A", "answer_request"
        )
        own_question = _self_contained_question(unquoted)
        if own_question:
            decision["question_text"] = own_question
            decision["original_question_id"] = str(base.get("post_id") or "")
            decision["question_sufficient"] = True
        return decision
    if missing and not participating:
        return _pack(
            base, AMBIENT, 0.7, "missing_context", False, "observe", "C", "none",
            ["missing_context"],
        )
    return _contribution(base, body, words, participating, missing, addressed=True)


def _contribution(
    base: dict,
    body: str,
    words: list[str],
    participating: bool,
    missing: bool,
    addressed: bool = False,
) -> dict:
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
        return _pack(base, CONTRIBUTION, 0.84, "contribution", False, "observe", "B", "none")
    if missing:
        return _pack(
            base, AMBIENT, 0.4, "missing_context", False, "observe", "C", "none",
            ["missing_context"],
        )
    if addressed:
        return _pack(
            base, AMBIENT, 0.5, "review", False, "observe", "C", "none", needs_model=True
        )
    return _pack(base, AMBIENT, 0.92, "not_requested", False, "observe", "C", "none")


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
                "DIRECT_CHALLENGE, CONTRIBUTION, AMBIENT, SPAM, or UNSAFE. "
                "A mention is not enough. Words such as why, how, what, or ask "
                "inside a statement, a quotation, or a suggestion that someone "
                "else consult MoodyBot are not requests. Use AMBIENT when the "
                "person is not addressing MoodyBot. Use UNSAFE for imminent "
                "self-harm and do not joke. Use CHALLENGE only for a dispute "
                "aimed at MoodyBot. Do not invent facts. If unsure, AMBIENT."
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
    if kind in _REPLY_CLASSES and confidence >= reply_confidence_threshold() and not window["missing_parent"]:
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

    def add(post_id: str, author_id: str, text: str, username: str = "", source: dict | None = None) -> None:
        if not post_id or post_id in seen:
            return
        seen.add(post_id)
        post = {
            "id": post_id,
            "author_id": author_id,
            "author_username": username,
            "author_is_bot": bool(user_id) and author_id == user_id,
            "text": text if isinstance(text, str) else "",
        }
        if isinstance(source, dict):
            post["parent_id"] = str(source.get("parent_id") or "")
            post["conversation_id"] = str(source.get("conversation_id") or "")
            post["text_complete"] = source.get("text_complete", True)
            post["status"] = str(source.get("status") or "")
            if isinstance(source.get("note_tweet"), dict):
                post["note_tweet"] = source.get("note_tweet")
        posts.append(post)

    for item in supplied:
        note_text, complete, _source = read_post_text(item)
        add(
            str(item.get("id") or ""),
            str(item.get("author_id") or ""),
            note_text,
            str(item.get("author_username") or ""),
            {**item, "text_complete": complete},
        )
    parent_id = str(tweet.get("parent_id") or "")
    parent_text = tweet.get("parent_text") if isinstance(tweet.get("parent_text"), str) else ""
    if parent_text.strip():
        add(
            parent_id,
            str(tweet.get("parent_author_id") or ""),
            parent_text,
            str(tweet.get("parent_author_username") or ""),
            {
                "parent_id": str(tweet.get("parent_parent_id") or ""),
                "conversation_id": str(tweet.get("conversation_id") or ""),
                "text_complete": tweet.get("parent_text_complete", True),
                "status": str(tweet.get("parent_status") or ""),
            },
        )
    current_name = str(tweet.get("author_username") or "")
    current_text, current_complete, _current_source = read_post_text(tweet)
    add(
        str(tweet.get("id") or ""),
        str(tweet.get("author_id") or ""),
        current_text,
        current_name,
        {**tweet, "text_complete": current_complete},
    )
    posts = posts[-_CONTEXT_LIMIT:]
    parent_author = str(tweet.get("parent_author_id") or "")
    participating = any(post["author_is_bot"] for post in posts[:-1]) or (
        bool(user_id) and parent_author == user_id
    )
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


def read_post_text(tweet: dict) -> tuple[str, bool, str]:
    """Prefer note text. A known truncation is not treated as the whole post."""
    note = tweet.get("note_tweet") if isinstance(tweet.get("note_tweet"), dict) else {}
    note_text = note.get("text") if isinstance(note.get("text"), str) else ""
    preview = tweet.get("text") if isinstance(tweet.get("text"), str) else ""
    if note_text.strip():
        return note_text, True, "note_tweet"
    if tweet.get("text_complete") is False or tweet.get("note_unavailable"):
        return preview, False, "truncated"
    return preview, True, str(tweet.get("text_source") or "text")


def attach_post_text(tweet: dict, *, note_failed: bool = False) -> dict:
    """Copy note text onto the post. A failed note read marks long text incomplete."""
    _text, complete, source = read_post_text(tweet)
    if source == "note_tweet":
        tweet["text"] = _text
        tweet["text_complete"] = True
        tweet["text_source"] = "note_tweet"
        return tweet
    if note_failed or tweet.get("text_complete") is False:
        tweet["text_complete"] = False
        tweet["text_source"] = "truncated"
        return tweet
    if note_failed is False and len(str(tweet.get("text") or "")) >= 270 and tweet.get("note_unavailable"):
        tweet["text_complete"] = False
        tweet["text_source"] = "truncated"
        return tweet
    tweet["text_complete"] = True
    tweet["text_source"] = "text"
    return tweet


def reply_confidence_threshold() -> float:
    import os

    raw = (os.environ.get("X_ENGAGEMENT_CONFIDENCE") or "0.8").strip()
    try:
        value = float(raw)
    except ValueError:
        return 0.8
    if value <= 0 or value > 1:
        return 0.8
    return value


def allows_publish(decision: dict) -> bool:
    """One publish gate. Missing, stale, incomplete, or unsure decisions do not post."""
    if not isinstance(decision, dict):
        return False
    if decision.get("text_complete") is False:
        return False
    if decision.get("classification") not in _REPLY_CLASSES | {CONTRIBUTION}:
        return False
    if not decision.get("respond"):
        return False
    flags = decision.get("safety_flags") or []
    if "crisis" in flags or "truncated" in flags or "missing_context" in flags or "insufficient_context" in flags:
        return False
    try:
        confidence = float(decision.get("confidence"))
    except (TypeError, ValueError):
        return False
    if confidence < reply_confidence_threshold():
        return False
    raw = str(decision.get("decided_at") or "")
    if raw:
        try:
            seen = datetime.fromisoformat(raw)
        except ValueError:
            return False
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - seen > _DECISION_TTL:
            return False
    return True


def authoritative_decision(
    tweet: dict,
    *,
    user_id: str,
    floor: str,
    already_replied: bool,
    context: dict | None = None,
    conversation: dict | None = None,
    complete=None,
) -> dict:
    """The only reply decision used by observation and publishing."""
    decision = decide_engagement(
        tweet,
        user_id=user_id,
        floor=floor,
        already_replied=already_replied,
        context=context,
        conversation=conversation,
        complete=complete,
    )
    decision["decided_at"] = datetime.now(timezone.utc).isoformat()
    decision["publish"] = allows_publish(decision)
    if not decision["publish"] and decision.get("action") == "reply":
        decision["respond"] = False
        decision["action"] = "observe"
    classification, reason = filter_view(decision)
    decision["filter_classification"] = classification
    decision["filter_reason"] = reason
    decision["eligible"] = bool(decision["publish"])
    return decision


def filter_view(decision: dict) -> tuple[str, str]:
    reason = str(decision.get("reason") or "")
    kind = str(decision.get("classification") or "")
    if reason == "bot_loop":
        return "other_bot", "other_bot"
    if reason == "duplicate_parent":
        return "already_replied", "duplicate_parent"
    if reason in {"invalid_id", "historical", "own_post", "empty", "spam", "not_mentioned"}:
        return reason, reason
    if decision.get("publish"):
        mapped = {
            DIRECT_REQUEST: "direct_request",
            FOLLOW_UP: "follow_up",
            CHALLENGE: "challenge",
            DIRECT_CHALLENGE: "direct_challenge",
            CONTRIBUTION: "contribution",
        }.get(kind, "direct_request")
        return "eligible", mapped
    if reason == "ai_loop":
        return "not_requested", "ai_loop"
    if reason == "repeated_question":
        return "not_requested", "repeated_question"
    if reason in {
        "insufficient_context",
        "missing_parent",
        "deleted_parent",
        "protected_parent",
        "cycle",
        "depth_limit",
        "lookup_budget",
        "ambiguous_question",
        "incomplete_text",
    }:
        return "uncertain", reason
    if kind == CONTRIBUTION or reason in {"generic_encouragement", "contribution", "meaningful"}:
        return "not_requested", "contribution"
    if reason == "not_requested":
        return "not_requested", "not_requested"
    if reason == "quotation":
        return "not_requested", "quotation"
    if reason == "incomplete_text":
        return "uncertain", "incomplete_text"
    if reason == "missing_context":
        return "uncertain", "missing_context"
    return "uncertain", "review"


def _outside_quotes(text: str) -> str:
    return re.sub(r'"[^"]*"|“[^”]*”', " ", text)


def _quoted_only(text: str) -> bool:
    return _MENTION.search(text) is not None and _MENTION.search(_outside_quotes(text)) is None


def _vocative_clause(text: str) -> str | None:
    cleaned = _THIRD_PARTY.sub(" ", _outside_quotes(text)).strip()
    match = _VOCATIVE.search(cleaned)
    if match is None:
        return None
    return match.group("clause").strip()


def _direct_invite(text: str) -> bool:
    return _MENTION.search(text) is not None and _INVITE.search(text) is not None


def _pointer_only(sentence: str) -> bool:
    """A question that only points at another post, such as "your turn"."""
    cleaned = _MENTION.sub(" ", sentence)
    if _INVITE.search(cleaned) is None:
        return False
    leftover = _INVITE.sub(" ", cleaned)
    return len(re.findall(r"[A-Za-z0-9']+", leftover)) < 3


def _self_contained_question(text: str) -> str:
    """Questions stated in this post. A pointer still needs an earlier post."""
    from question_scope import extract_questions

    found = extract_questions(text, channel="x")
    parts = [
        item["text"]
        for item in found["questions"]
        if item.get("self_contained") and item.get("origin") == "current"
    ]
    return " ".join(parts)


def _known_ai(author_id: str, username: str) -> bool:
    from x_integration.battle import author_is_ai

    return author_is_ai(author_id, username)


def _invitation(base: dict, text: str, unquoted: str, window: dict, tweet: dict) -> dict:
    from x_integration.battle import trace_question

    recovered = trace_question(
        tweet,
        window["posts"],
        fetch=tweet.get("fetch_post") if callable(tweet.get("fetch_post")) else None,
    )
    flags = ["untrusted_quote"] if _UNTRUSTED.search(text) and not _UNTRUSTED.search(unquoted) else []
    if _UNTRUSTED.search(unquoted):
        return _pack(
            base, AMBIENT, 0.97, "untrusted_instruction", False, "skip", "C", "none",
            ["untrusted_quote"],
        )
    if _EVIDENCE.search(unquoted) or re.search(r"(?i)\bverify\b", unquoted):
        flags.append("evidence")
    if re.search(r"(?i)\bwrong\b", unquoted):
        flags.append("do_not_assume")
    objective = "separate_verified_from_uncertain" if "evidence" in flags else "answer_independently"
    decision = _pack(
        base, DIRECT_CHALLENGE, 0.93, "direct_challenge", True, "reply", "A", objective, flags
    )
    decision["original_question_id"] = recovered.get("question_id") or ""
    decision["question_text"] = recovered.get("question_text") or ""
    decision["question_author_id"] = recovered.get("question_author_id") or ""
    decision["question_conversation_id"] = recovered.get("question_conversation_id") or ""
    decision["reply_parent_id"] = recovered.get("reply_parent_id") or base.get("post_id") or ""
    decision["question_origin"] = recovered.get("question_origin") or ""
    decision["grok_answer"] = recovered.get("grok_answer") or ""
    decision["question_sufficient"] = bool(recovered.get("sufficient"))
    if not recovered.get("sufficient"):
        decision["respond"] = False
        decision["action"] = "observe"
        decision["reason"] = recovered.get("reason") or "insufficient_context"
        decision["objective"] = "clarify"
        decision["question_sufficient"] = False
        flags = list(decision["safety_flags"])
        flags.append("insufficient_context")
        decision["safety_flags"] = flags
    return decision


def _apply_ai_loop(decision: dict, tweet: dict, username: str, conversation: dict | None) -> None:
    """One AI invitation reply per conversation until a later human request."""
    author_id = str(tweet.get("author_id") or "")
    automated = bool(tweet.get("automated"))
    from x_integration.battle import author_is_ai

    ai = author_is_ai(author_id, username, automated)
    if decision.get("classification") == DIRECT_CHALLENGE and not ai:
        decision["loop_outcome"] = "human"
    answered = []
    if isinstance(conversation, dict):
        answered = [str(item) for item in conversation.get("answered_question_ids") or []]
    question_id = str(decision.get("original_question_id") or "")
    if question_id and question_id in answered and decision.get("respond"):
        decision["respond"] = False
        decision["action"] = "skip"
        decision["reason"] = "repeated_question"
        decision["objective"] = "none"
        decision["loop_outcome"] = "blocked"
        return
    if not ai or not decision.get("respond"):
        return
    used = bool(conversation and conversation.get("ai_invitation_used"))
    human_after = bool(conversation and conversation.get("human_after_ai"))
    if used and not human_after:
        decision["respond"] = False
        decision["action"] = "skip"
        decision["reason"] = "ai_loop"
        decision["objective"] = "none"
        decision["loop_outcome"] = "blocked"
        return
    if decision.get("classification") == DIRECT_CHALLENGE:
        decision["loop_outcome"] = "allowed"


def _clause_request(clause: str) -> bool:
    return _CLAUSE_REQUEST.search(clause) is not None


def _other_account_question(text: str) -> bool:
    match = re.match(r"(?i)\s*@(?!MoodyBotAI\b)\w+", text)
    if match is None or _MENTION.search(text) is None:
        return False
    mention = _MENTION.search(text)
    before = text[:mention.start()]
    return "?" in before or _CLAUSE_REQUEST.search(before) is not None


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
