# -*- coding: utf-8 -*-
"""Normalize an X Activity API delivery.

Only an explicit public @mention is actionable. X Chat and legacy DMs
are acknowledged and dropped.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


MENTION_EVENT = "post.mention.create"
CHAT_EVENTS = frozenset({
    "chat.received",
    "chat.sent",
    "chat.conversation_join",
    "dm.received",
    "dm.sent",
    "dm.read",
    "dm.indicate_typing",
})


@dataclass(frozen=True)
class Mention:
    event_id: str
    post_id: str
    author_id: str
    text: str
    conversation_id: str


@dataclass(frozen=True)
class Ignored:
    reason: str
    event_id: str = ""
    event_type: str = ""


Delivery = Union[Mention, Ignored]


def parse_delivery(payload) -> Delivery:
    if not isinstance(payload, dict):
        return Ignored("malformed")
    event = _event_object(payload)
    if event is None:
        return Ignored("malformed")
    event_type = str(event.get("event_type") or event.get("type") or "").strip()
    event_id = str(event.get("id") or event.get("event_id") or "").strip()
    if event_type in CHAT_EVENTS:
        return Ignored("chat", event_id=event_id, event_type=event_type)
    if event_type != MENTION_EVENT:
        return Ignored("unsupported_event", event_id=event_id, event_type=event_type)
    post = event.get("post") if isinstance(event.get("post"), dict) else {}
    if not post and isinstance(event.get("tweet"), dict):
        post = event["tweet"]
    post_id = str(post.get("id") or event.get("post_id") or "").strip()
    author_id = str(
        post.get("author_id")
        or event.get("author_id")
        or _nested_id(event.get("user"))
        or ""
    ).strip()
    text = post.get("text") if isinstance(post.get("text"), str) else ""
    if not text and isinstance(event.get("text"), str):
        text = event["text"]
    conversation_id = str(
        post.get("conversation_id") or event.get("conversation_id") or post_id
    ).strip()
    if not event_id or not post_id or not author_id or not text.strip():
        return Ignored("incomplete_mention", event_id=event_id, event_type=event_type)
    return Mention(
        event_id=event_id,
        post_id=post_id,
        author_id=author_id,
        text=text.strip(),
        conversation_id=conversation_id or post_id,
    )


def _event_object(payload: dict) -> Optional[dict]:
    data = payload.get("data")
    if isinstance(data, dict) and (data.get("event_type") or data.get("type") or data.get("post")):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if payload.get("event_type") or payload.get("type"):
        return payload
    return None


def _nested_id(value) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or "")
    return ""
