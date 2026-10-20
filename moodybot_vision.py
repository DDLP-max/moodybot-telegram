# -*- coding: utf-8 -*-
"""MoodyBot vision: see a Telegram image and answer in character.

The personality engine is unchanged. This module only ingests the picture,
hands the actual pixels to the same model, and keeps a short visual memory
so a later message can point back at the image.

Text-only turns never enter this path.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("moodybot")

MAX_IMAGE_BYTES = 8_000_000
MAX_EDGE = 1600
MAX_IMAGES = 4
ALBUM_WAIT_SECONDS = 0.8
_ANCHOR_RE = re.compile(r"(?im)^\s*ANCHOR:\s*(.+?)\s*$")
_ROAST_RE = re.compile(
    r"\b(roast|drag|destroy|be brutal|be mean|savage this|light (?:them|this|him|her) up)\b",
    re.I,
)
_QUESTION_RE = re.compile(
    r"^(what|why|how|who|when|where|is|are|does|do|did|can|could|should|would)\b",
    re.I,
)
_EXTEND_RE = re.compile(r"\b(meme|joke)\b", re.I)
_EXPLAIN_RE = re.compile(r"\b(explain|what does|why is|mean)\b", re.I)
_PROFILE_RE = re.compile(
    r"\b(dating profile|hinge|bumble|tinder|her profile|his profile|their profile|the profile)\b",
    re.I,
)
_ARGUMENT_RE = re.compile(
    r"\b(tweet|twitter|x post|on x|screenshot|this post|the post|thread)\b",
    re.I,
)
_REFERENCE_RE = re.compile(
    r"\b(remember|you said|earlier|the one|"
    r"(?:that|the|this|last)\s+(?:photo|picture|image|meme|screenshot|profile|post|outfit|poster))\b",
    re.I,
)
_VAGUE_IMAGE_RE = re.compile(
    r"\b(?:that|the|this|last)\s+(?:photo|picture|image|meme|screenshot|profile|post|outfit|poster)\b",
    re.I,
)
_COMPARE_RE = re.compile(
    r"\b(compare|versus|vs\.?|which one|the last two|between these|between them)\b",
    re.I,
)
_STOP = {
    "that", "this", "with", "from", "have", "your", "about", "remember",
    "photo", "picture", "image", "screenshot", "meme", "profile", "post",
    "outfit", "poster", "woman", "whose", "entire", "just", "they", "them",
    "she", "her", "his", "him", "the", "and", "was", "were", "you", "for",
    "when", "what", "earlier", "last", "said", "again", "those", "these",
    "into", "over", "than", "then", "there", "here", "been", "being", "have",
    "personality", "entire", "whose", "woman", "girl", "guy", "dude", "lady",
}

_albums = {}


class ImageRejected(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def vision_enabled() -> bool:
    return os.getenv("MOODYBOT_VISION", "1").strip().lower() not in {
        "0", "off", "false", "no",
    }


def memory_root() -> Path:
    override = os.getenv("MOODYBOT_VISION_MEMORY_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "data" / "vision_memory"


def retention_days() -> int:
    return _positive_int("MOODYBOT_VISION_RETENTION_DAYS", 14)


def memory_limit() -> int:
    return _positive_int("MOODYBOT_VISION_MEMORY_LIMIT", 20)


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def message_has_image(message) -> bool:
    if message is None:
        return False
    if getattr(message, "photo", None):
        return True
    document = getattr(message, "document", None)
    mime = str(getattr(document, "mime_type", "") or "").lower()
    return mime.startswith("image/")


def user_words(message) -> str:
    if message is None:
        return ""
    return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def classify_vision_intent(text: str) -> str:
    """How the picture should be played. The image itself still decides the joke."""
    raw = (text or "").strip()
    if not raw:
        return "auto"
    if _ROAST_RE.search(raw):
        return "roast"
    if "?" in raw or _QUESTION_RE.match(raw):
        return "answer"
    if _EXTEND_RE.search(raw) and not _EXPLAIN_RE.search(raw):
        return "extend"
    if _PROFILE_RE.search(raw):
        return "profile"
    if _ARGUMENT_RE.search(raw):
        return "argument"
    return "auto"


def vision_directive(intent: str, *, caption: str, prior: list, image_count: int) -> str:
    lines = {
        "auto": "They sent the image without explaining the joke. Pick the sharpest true angle. Do not ask what they want.",
        "roast": "They asked for a roast. Be direct. One cut, not a critique.",
        "answer": "They asked a question. Answer it from what the image reveals. Do not roast unless the question itself is a roast.",
        "extend": "This is already a joke. Extend it. Do not explain it.",
        "profile": "Read this as self-presentation. The comedy is how they arranged themselves, not a list of hobbies.",
        "argument": "There is a claim on screen. Answer that claim. Ignore the interface chrome.",
    }
    parts = [
        "You can see the attached image. The pixels are the evidence, not a caption someone else wrote.",
        "Do not describe the image and then attach an insult. Interpret what it unintentionally reveals: posture, expression, framing, the background, and any contradiction between the words and the picture.",
        "Hear what was said. Notice what it implies. Say the thing underneath it.",
        "One reply, in your own voice. The punchline is the exit. Do not explain why it is funny. Do not narrate that you can see an image.",
        "If a person in the image looks underage, do not roast or sexualize them. Say you won't, and stop.",
        lines.get(intent, lines["auto"]),
    ]
    if image_count > 1:
        parts.append(
            "More than one image is attached. Do not review them one by one. Find the contradiction between them and land a single line."
        )
    if not (caption or "").strip():
        parts.append("There is no caption.")
    for record in prior:
        earlier = (record.get("caption") or "(no caption)").strip()
        said = " ".join(record.get("replies") or [])[:500]
        parts.append(
            "They are referring to an earlier image that is attached again. "
            f"They said then: {earlier}. You answered: {said or '(no reply stored)'}. "
            "Use the picture and that history. Do not recap it."
        )
    parts.append(
        "After the reply, on its own last line, write ANCHOR: and one sentence of concrete visible facts a later message might quote "
        "(objects, activities, on-screen claims, contradictions). That line is not part of the reply."
    )
    return "\n".join(parts)


def split_anchor(raw: str) -> tuple:
    if not raw:
        return "", ""
    found = [item.strip() for item in _ANCHOR_RE.findall(raw) if item.strip()]
    spoken = _ANCHOR_RE.sub("", raw).strip()
    return spoken, " ".join(found)


def assemble_messages(system_prompt, structure, closer, directive, user_content) -> list:
    """Same stack the text handler builds, with the visual instruction beside the picture."""
    messages = [{"role": "system", "content": system_prompt}]
    if structure:
        messages.insert(0, {"role": "system", "content": structure})
    messages.insert(0, {"role": "system", "content": closer})
    messages.append({"role": "system", "content": directive})
    messages.append({"role": "user", "content": user_content})
    return messages


def user_content(text: str, images: list) -> list:
    visible = (text or "").strip() or " "
    parts = [{"type": "text", "text": visible}]
    for data, mime in images:
        parts.append({
            "type": "image_url",
            "image_url": {"url": _data_uri(data, mime)},
        })
    return parts


def _data_uri(data: bytes, mime: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def validate_declared_mime(mime: str | None) -> None:
    if not mime:
        return
    clean = mime.split(";", 1)[0].strip().lower()
    if clean in {"application/octet-stream", "binary/octet-stream"}:
        return
    allowed = {
        "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif", "image/bmp",
    }
    if clean not in allowed:
        raise ImageRejected("I can't see that file. Send a photo, screenshot, or image.")


def normalize_image(raw: bytes, mime: str | None = None) -> tuple:
    """Return JPEG bytes small enough to send, with orientation applied and metadata dropped."""
    validate_declared_mime(mime)
    if not raw:
        raise ImageRejected("That file is empty.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ImageRejected("That image is too big. Send it smaller.")
    try:
        from PIL import Image, ImageOps
        import io

        Image.MAX_IMAGE_PIXELS = 24_000_000
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            if getattr(img, "is_animated", False):
                img.seek(0)
            if "A" in img.getbands():
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((MAX_EDGE, MAX_EDGE))
            if min(img.size) < 8:
                raise ImageRejected("That image is too small to read.")
            quality = 88
            data = _encode_jpeg(img, quality)
            while len(data) > 4_000_000 and quality > 50:
                quality -= 10
                data = _encode_jpeg(img, quality)
    except ImageRejected:
        raise
    except Exception:
        raise ImageRejected("I can't see that file. Send a photo, screenshot, or image.")
    return data, "image/jpeg"


def _encode_jpeg(img, quality: int) -> bytes:
    import io

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {word for word in words if len(word) > 2 and word not in _STOP}


def _blob_tokens(record: dict) -> set:
    blob = " ".join([
        record.get("caption") or "",
        record.get("anchor") or "",
        " ".join(record.get("replies") or []),
    ])
    return _tokens(blob)


def _overlap(query: str, record: dict) -> int:
    return len(_tokens(query) & _blob_tokens(record))


def _score(query: str, record: dict) -> float:
    wanted = _tokens(query)
    if not wanted:
        return 0.0
    return _overlap(query, record) / len(wanted)


class ImageMemory:
    """Per-chat images kept until the retention window or the count limit."""

    def __init__(self, root: Path, retention_days: int = 14, limit: int = 20, now=None):
        self.root = Path(root)
        self.retention = timedelta(days=retention_days)
        self.limit = limit
        self._now = now or (lambda: datetime.now(timezone.utc))

    def select(self, chat_id, query: str, reply_to=None) -> list:
        records = self._live(chat_id)
        if not records:
            return []
        pinned = self._match_reply(reply_to, records)
        if pinned:
            return pinned
        if not query:
            return []
        ranked = sorted(records, key=lambda record: _score(query, record), reverse=True)
        pointed = bool(_REFERENCE_RE.search(query) or _COMPARE_RE.search(query))
        best_score = _score(query, ranked[0])
        distinctive = len(_tokens(query))
        if _COMPARE_RE.search(query):
            if re.search(r"\b(last two|these two)\b", query, re.I):
                return records[-2:]
            hits = [record for record in ranked if _overlap(query, record) >= 1]
            if len(hits) >= 2:
                return _chronological(hits[:2])
            if hits:
                return hits[:1]
            return []
        if best_score >= 0.5 and (pointed or (best_score >= 0.67 and distinctive >= 2)):
            return [ranked[0]]
        if pointed and _VAGUE_IMAGE_RE.search(query):
            return [records[-1]]
        return []

    def would_recall(self, chat_id, query: str, reply_to=None) -> bool:
        return bool(self.select(chat_id, query, reply_to))

    def save(self, chat_id, images: list, *, caption: str, intent: str, anchor: str,
             reply: str, user_message_ids: list) -> dict:
        folder = self._folder(chat_id)
        folder.mkdir(parents=True, exist_ok=True)
        files = []
        for data, _mime in images[:MAX_IMAGES]:
            name = f"{uuid.uuid4().hex}.jpg"
            (folder / name).write_bytes(data)
            files.append(name)
        record = {
            "id": uuid.uuid4().hex,
            "user_message_ids": [int(item) for item in user_message_ids if item is not None],
            "created_at": self._now().isoformat(),
            "caption": caption or "",
            "intent": intent,
            "anchor": anchor or "",
            "replies": [reply] if reply else [],
            "files": files,
        }
        records = self._live(chat_id)
        records.append(record)
        self._write(chat_id, records)
        return record

    def touch(self, chat_id, records: list, *, reply: str, anchor: str, user_message_id) -> None:
        if not records:
            return
        live = self._live(chat_id)
        by_id = {item["id"]: item for item in live}
        for record in records:
            current = by_id.get(record.get("id"))
            if not current:
                continue
            if reply:
                replies = list(current.get("replies") or [])
                replies.append(reply)
                current["replies"] = replies[-4:]
            if anchor:
                current["anchor"] = " ".join(part for part in (current.get("anchor"), anchor) if part).strip()
            if user_message_id is not None:
                ids = list(current.get("user_message_ids") or [])
                if int(user_message_id) not in ids:
                    ids.append(int(user_message_id))
                current["user_message_ids"] = ids
        self._write(chat_id, live)

    def load_images(self, records: list) -> list:
        images = []
        for record in records:
            folder = self._folder_for_record(record)
            for name in record.get("files") or []:
                path = folder / name
                if path.is_file():
                    images.append((path.read_bytes(), "image/jpeg"))
                if len(images) >= MAX_IMAGES:
                    return images
        return images

    def _match_reply(self, reply_to, records: list) -> list:
        if reply_to is None:
            return []
        message_id = getattr(reply_to, "message_id", None)
        if message_id is not None:
            for record in records:
                if int(message_id) in set(record.get("user_message_ids") or []):
                    return [record]
        text = user_words(reply_to)
        if text:
            snippet = text[:80]
            for record in records:
                blob = " ".join(record.get("replies") or [])
                if snippet and (snippet in blob or (blob[:80] and blob[:80] in text)):
                    return [record]
        return []

    def _live(self, chat_id) -> list:
        records = self._read(chat_id)
        now = self._now()
        kept = []
        folder = self._folder(chat_id)
        changed = False
        for record in records:
            created = _parse_time(record.get("created_at"))
            if created is None or now - created > self.retention:
                self._delete_files(folder, record)
                changed = True
                continue
            kept.append(record)
        if len(kept) > self.limit:
            overflow = kept[:-self.limit]
            for record in overflow:
                self._delete_files(folder, record)
            kept = kept[-self.limit:]
            changed = True
        if changed:
            self._write(chat_id, kept)
        return kept

    def _folder(self, chat_id) -> Path:
        label = str(chat_id)
        if not re.fullmatch(r"-?\d+", label):
            raise ImageRejected("Bad chat.")
        return self.root / label

    def _folder_for_record(self, record: dict) -> Path:
        return self._folder(record.get("_chat_id")) if record.get("_chat_id") is not None else self.root

    def _read(self, chat_id) -> list:
        path = self._folder(chat_id) / "index.json"
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("vision memory index unreadable for chat %s", chat_id)
            return []
        if not isinstance(data, list):
            return []
        for record in data:
            record["_chat_id"] = chat_id
        return data

    def _write(self, chat_id, records: list) -> None:
        folder = self._folder(chat_id)
        folder.mkdir(parents=True, exist_ok=True)
        clean = []
        for record in records:
            item = {key: value for key, value in record.items() if key != "_chat_id"}
            clean.append(item)
        path = folder / "index.json"
        temp = folder / "index.json.tmp"
        temp.write_text(json.dumps(clean), encoding="utf-8")
        temp.replace(path)

    def _delete_files(self, folder: Path, record: dict) -> None:
        for name in record.get("files") or []:
            try:
                (folder / name).unlink(missing_ok=True)
            except OSError:
                logger.warning("could not delete expired vision file %s", name)


def default_memory() -> ImageMemory:
    return ImageMemory(memory_root(), retention_days(), memory_limit())


def _chronological(records: list) -> list:
    return sorted(records, key=lambda record: record.get("created_at") or "")


def _parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def install_image_handlers() -> None:
    from telegram.ext import Application, MessageHandler, filters

    original = Application.add_handler
    if getattr(original, "_moody_vision_patched", False):
        return

    def add_handler(self, handler, group=0):
        original(self, handler, group)
        if getattr(self, "_moody_vision_photo", False):
            return
        if getattr(handler, "filters", None) == filters.TEXT:
            self._moody_vision_photo = True
            original(
                self,
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, handler.callback),
                group,
            )
            logger.info("MoodyBot vision handlers registered")

    add_handler._moody_vision_patched = True
    Application.add_handler = add_handler


def install(namespace: dict) -> None:
    compiled_handle = namespace["handle_message"]
    compiled_main = namespace["main"]
    module_name = namespace["__name__"]

    async def handle_message(update, context):
        import sys
        module = sys.modules[module_name]
        return await dispatch(update, context, module, compiled_handle)

    def main():
        install_image_handlers()
        return compiled_main()

    namespace["handle_message"] = handle_message
    namespace["main"] = main


async def dispatch(update, context, mb, compiled_handle):
    message = getattr(update, "message", None)
    group_id = getattr(message, "media_group_id", None) if message is not None else None
    if group_id and message_has_image(message):
        bucket = _albums.setdefault(group_id, [])
        bucket.append(update)
        if len(bucket) == 1:
            asyncio.create_task(_flush_album(group_id, context, mb))
        return None
    if _should_see(update):
        return await handle_vision_update(update, context, mb)
    return await compiled_handle(update, context)


def _should_see(update) -> bool:
    message = getattr(update, "message", None)
    if message is None:
        return False
    if message_has_image(message):
        return True
    reply = getattr(message, "reply_to_message", None)
    if message_has_image(reply):
        return True
    text = getattr(message, "text", None) or ""
    chat = getattr(update, "effective_chat", None)
    if not text or chat is None or getattr(chat, "id", None) is None:
        return False
    try:
        return default_memory().would_recall(chat.id, text, reply)
    except Exception:
        logger.exception("vision recall check failed")
        return False


async def _flush_album(group_id, context, mb) -> None:
    await asyncio.sleep(ALBUM_WAIT_SECONDS)
    batch = _albums.pop(group_id, [])
    if not batch:
        return
    await handle_vision_update(batch[0], context, mb, grouped=batch)


async def handle_vision_update(update, context, mb, grouped=None):
    message = update.message
    update_id = getattr(update, "update_id", "?")
    chat = update.effective_chat
    chat_id = getattr(chat, "id", None)
    if not await _allowed(mb, update, chat):
        return None

    stage = "vision_ingest"
    try:
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        images, caption, message_ids, prior, fresh = await _resolve_images(
            message, context, chat_id, grouped,
        )
        if not images:
            await mb.send_simple_message(
                update, "I can't see that file. Send a photo, screenshot, or image.",
            )
            return None
        intent = classify_vision_intent(caption)
        logger.info(
            "[update %s] vision images=%s intent=%s prior=%s",
            update_id, len(images), intent, len(prior),
        )
        await _complete_and_send(
            mb, update, chat, update_id, caption, intent, images, prior, message_ids, fresh,
        )
    except ImageRejected as rejected:
        await mb.send_simple_message(update, rejected.user_message)
    except Exception:
        logger.exception(
            "MoodyBot handler failed update_id=%s chat_id=%s stage=%s",
            update_id, chat_id, stage,
        )
        await mb.send_simple_message(update, "MoodyBot is sulking. Try again later.")
    return None


async def _allowed(mb, update, chat) -> bool:
    if chat is None:
        return False
    if getattr(chat, "type", None) == "private" or getattr(chat, "id", None) == mb.PREMIUM_GROUP_ID:
        return True
    if getattr(chat, "id", None) == mb.FREE_GROUP_CHAT_ID:
        await mb.send_simple_message(update, "Subscribe to Premium for the real shit, Bucky.")
    else:
        await mb.send_simple_message(update, "This feature is exclusive to Premium users. 🥃")
    return False


async def _resolve_images(message, context, chat_id, grouped):
    messages = list(grouped or [message])
    fresh_images = []
    captions = []
    message_ids = []
    rejection = None
    for item in messages:
        words = user_words(item)
        if words:
            captions.append(words)
        message_id = getattr(item, "message_id", None)
        if message_id is not None:
            message_ids.append(message_id)
        if not message_has_image(item):
            continue
        downloaded = await _download(item, context)
        if not downloaded:
            continue
        try:
            fresh_images.append(normalize_image(*downloaded))
        except ImageRejected as exc:
            rejection = exc
        if len(fresh_images) >= MAX_IMAGES:
            break
    caption = captions[0] if captions else ""
    if fresh_images:
        return fresh_images, caption, message_ids, [], True
    if rejection is not None and any(message_has_image(item) for item in messages):
        raise rejection

    memory = default_memory()
    reply = getattr(message, "reply_to_message", None)
    prior = memory.select(chat_id, caption, reply) if chat_id is not None else []
    if prior:
        stored = memory.load_images(prior)
        if stored:
            return stored, caption, message_ids, prior, False
    if message_has_image(reply):
        downloaded = await _download(reply, context)
        if downloaded:
            return [normalize_image(*downloaded)], caption, message_ids, prior, True
    return [], caption, message_ids, prior, False


async def _download(message, context):
    file_id = None
    mime = None
    photos = getattr(message, "photo", None)
    if photos:
        file_id = photos[-1].file_id
        mime = "image/jpeg"
    else:
        document = getattr(message, "document", None)
        mime = str(getattr(document, "mime_type", "") or "")
        if document is not None and mime.lower().startswith("image/"):
            file_id = document.file_id
    if not file_id:
        return None
    telegram_file = await context.bot.get_file(file_id)
    payload = await telegram_file.download_as_bytearray()
    return bytes(payload), mime


def _prepare_model_turn(mb, planner_text, caption, intent, images, prior):
    """Build the model payload from whichever personality runtime is loaded.

    The Render service uses prompt_runtime. The August snapshot still loads
    system_prompt.txt. The picture is attached either way.
    """
    directive = vision_directive(intent, caption=caption, prior=prior, image_count=len(images))
    try:
        from capability_detection import classify_social_mode
        from prompt_runtime import build_openrouter_messages, build_runtime_prompt
        from structure_prompts import structure_prompt_for
    except Exception:
        selected = mb.route_command(planner_text) or mb.select_best_command(planner_text)
        system_prompt = mb.load_system_prompt()
        prompt_hash = mb.prompt_content_hash(system_prompt)
        mode = "validation" if selected == "/validate" else "dynamic"
        response_plan = mb.build_response_plan(
            planner_text,
            selected_command=selected,
            channel="telegram",
            mode=mode,
        )
        prompts = getattr(mb, "STRUCTURE_PROMPTS", None) or {}
        structure = prompts.get(selected) if selected in prompts else None
        closer = ""
        plan_closer = getattr(mb, "plan_closer_instruction", None)
        if callable(plan_closer):
            closer = plan_closer(response_plan)
        messages = assemble_messages(
            system_prompt,
            structure,
            closer,
            directive,
            user_content(caption, images),
        )
        return messages, response_plan, prompt_hash, selected

    slash_commands = (
        "/savage", "/roast", "/cut", "/validate", "/jukebox", "/velvet",
        "/noir", "/clinical", "/dark", "/ghost", "/numb", "/cinema",
        "/sensory", "/tighten", "/contrast", "/godfather", "/spiral",
        "/villain", "/thoughts",
    )
    social = classify_social_mode(planner_text)
    typed_slash = any(cmd in (planner_text or "").lower() for cmd in slash_commands)
    selected = mb.route_command(planner_text)
    if getattr(social, "blocks_topical_auto_route", False) and not typed_slash:
        selected = "/thoughts"
        source = "social-first"
    elif not selected:
        selected = mb.select_best_command(planner_text)
        source = "classifier"
    else:
        source = "explicit" if typed_slash else "auto-route"
    mode = "validation" if selected == "/validate" else "dynamic"
    response_plan = mb.build_response_plan(
        planner_text,
        selected_command=selected,
        channel="telegram",
        mode=mode,
        tone_source=source,
    )
    inject = None
    if not (getattr(social, "blocks_topical_auto_route", False) and not typed_slash):
        inject = structure_prompt_for(selected, social=social, plan=response_plan)
    runtime = build_runtime_prompt(
        response_plan,
        social=social,
        selected_command=selected,
        structure_prompt=inject or "",
    )
    messages = build_openrouter_messages(runtime, planner_text)
    messages.insert(-1, {"role": "system", "content": directive})
    messages[-1] = {"role": "user", "content": user_content(caption, images)}
    return messages, response_plan, runtime.prompt_hash, selected


async def _complete_and_send(mb, update, chat, update_id, caption, intent, images, prior, message_ids, fresh):
    stage = "before_openrouter"
    chat_id = getattr(chat, "id", None)
    try:
        planner_text = caption.strip() or "Look at this image."
        messages, response_plan, prompt_hash, selected = _prepare_model_turn(
            mb, planner_text, caption, intent, images, prior,
        )
        logger.info(
            "[update %s] Response plan: strategy=%s intent=%s capability=%s prompt_hash=%s",
            update_id,
            getattr(response_plan, "closing_strategy", ""),
            response_plan.intent,
            response_plan.primary_capability,
            prompt_hash,
        )
        stage = "openrouter_request"
        started = time.monotonic()
        logger.info("[update %s] OpenRouter request started model=%s", update_id, mb.OPENROUTER_MODEL)
        async with mb.httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {mb.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://moodybot.ai",
                    "X-Title": "MoodyBot",
                },
                json={
                    "model": mb.OPENROUTER_MODEL,
                    "messages": messages,
                    "max_tokens": 1000,
                },
                timeout=45,
            )
            latency_ms = (time.monotonic() - started) * 1000.0
            stage = "openrouter_parse"
            try:
                result = response.json()
            except Exception:
                logger.exception(
                    "[update %s] OpenRouter JSON parse failed status=%s latency_ms=%.0f model=%s body_chars=%s",
                    update_id,
                    response.status_code,
                    latency_ms,
                    mb.OPENROUTER_MODEL,
                    len(response.text or ""),
                )
                await mb.send_simple_message(update, "MoodyBot's signal got scrambled. Try again in a bit.")
                return
        fields = mb._openrouter_error_fields(result)
        has_choices = (
            isinstance(result, dict)
            and isinstance(result.get("choices"), list)
            and bool(result["choices"])
        )
        if response.status_code < 400 and has_choices:
            logger.info(
                "[update %s] OpenRouter response received status=%s latency_ms=%.0f model=%s choices=%s",
                update_id,
                response.status_code,
                latency_ms,
                mb.OPENROUTER_MODEL,
                len(result["choices"]),
            )
        else:
            logger.error(
                "[update %s] OpenRouter failed stage=openrouter_parse status=%s model=%s error_code=%s error_message=%s request_id=%s latency_ms=%.0f",
                update_id,
                response.status_code,
                mb.OPENROUTER_MODEL,
                fields["error_code"],
                fields["error_message"],
                fields["request_id"],
                latency_ms,
            )
            await mb.send_simple_message(update, "MoodyBot's signal got scrambled. Try again in a bit.")
            return

        stage = "response_content"
        raw_content = _message_text(result["choices"][0]["message"]["content"])
        spoken, anchor = split_anchor(raw_content)
        logger.info("[update %s] OpenRouter content ok chars=%s", update_id, len(spoken or ""))
        draft_paragraph_count = mb.paragraph_count(spoken)
        stage = "finalization"
        content = mb.process_bot_output(spoken)
        post_prefab_paragraph_count = mb.paragraph_count(content)
        content = content.replace(" indeed", "").replace("Indeed, ", "").replace("Indeed.", "")
        category = mb.detect_category(planner_text)
        content = mb.replace_category_descriptors(content, category)
        if content.lower().startswith("ah,"):
            content = content[3:].lstrip()
        content = mb.clean_response(content)
        content = mb.re.sub(r"\(([A-Z][a-z]+(?: ?&? [A-Z][a-z]+)?)\)", "", content)
        content = content.replace("—", ", ")
        content = mb.re.sub(r"[ \t]+([.,;!?])", r"\1", content)
        content = mb.polish_sentences(content)
        post_polish_paragraph_count = mb.paragraph_count(content)
        if "\n\n" not in content and content.count("\n") > 6:
            content = mb.auto_paragraph(content)
        logger.info(
            "[update %s] PARA_TRACE draft=%s post_prefab=%s post_polish=%s structure=%s budget=%s",
            update_id,
            draft_paragraph_count,
            post_prefab_paragraph_count,
            post_polish_paragraph_count,
            getattr(response_plan, "preferred_structure", ""),
            getattr(response_plan, "response_budget", ""),
        )
        git_commit = _git_commit()
        finalized = mb.finalize_response(
            content,
            planner_text,
            response_plan,
            selected_command=selected,
            channel="telegram",
            mode=response_plan.mode,
            prompt_hash=prompt_hash,
            git_commit=git_commit,
        )
        content = finalized.text
        logger.info("[update %s] Finalization diagnostics: %s", update_id, finalized.diagnostics)
        diagnostics = finalized.diagnostics or {}
        logger.info(
            "[update %s] PARA_TRACE_FINAL structure=%s budget=%s draft=%s post_editor=%s post_finalizer=%s",
            update_id,
            diagnostics.get("preferred_structure") or diagnostics.get("selected_structure"),
            diagnostics.get("response_budget"),
            diagnostics.get("draft_paragraph_count"),
            diagnostics.get("post_editor_paragraph_count"),
            diagnostics.get("post_finalizer_paragraph_count"),
        )
        is_trial = chat_id == mb.FREE_GROUP_CHAT_ID or getattr(chat, "type", None) == "private"
        mb.log_interaction(planner_text, content, is_trial=is_trial)
        try:
            from inspector.store import record_event
            record_event(planner_text, content, diagnostics, channel="telegram", source="live")
        except Exception as insp_err:
            logger.warning("[update %s] Inspector record failed: %s", update_id, insp_err)
        content = mb.safe_emoji(content)
        if not content or len(content.strip()) < 10:
            logger.error("[update %s] Response too short or empty", update_id)
            await mb.send_simple_message(update, "MoodyBot couldn't generate a proper response. Try again.")
            return
        stage = "telegram_send"
        # Photo messages carry the user's words on caption. The August text
        # helpers read message.text and would throw on a picture.
        outgoing = _update_with_text(update, caption)
        send_mode = mb.resolve_mode(outgoing)
        logger.info("[update %s] Telegram reply send started", update_id)
        await mb.send_message(outgoing, content, send_mode, allow_cta=False)
        logger.info("[update %s] Telegram reply sent complete", update_id)
        _store_turn(
            chat_id, images, caption, intent, anchor, content, message_ids, prior, fresh,
        )
    except Exception:
        logger.exception(
            "MoodyBot handler failed update_id=%s chat_id=%s stage=%s",
            update_id, chat_id, stage,
        )
        await mb.send_simple_message(update, "MoodyBot is sulking. Try again later.")


class _CaptionMessage:
    """Photo message that also exposes the caption as text for the text helpers."""

    def __init__(self, message, text: str):
        self._message = message
        self.text = text

    def __getattr__(self, name):
        return getattr(self._message, name)


class _CaptionUpdate:
    def __init__(self, update, text: str):
        self._update = update
        self.message = _CaptionMessage(update.message, text)

    def __getattr__(self, name):
        return getattr(self._update, name)


def _update_with_text(update, caption: str):
    if getattr(getattr(update, "message", None), "text", None):
        return update
    return _CaptionUpdate(update, caption or "")


def _store_turn(chat_id, images, caption, intent, anchor, reply, message_ids, prior, fresh) -> None:
    if chat_id is None:
        return
    try:
        memory = default_memory()
        if fresh:
            memory.save(
                chat_id,
                images,
                caption=caption,
                intent=intent,
                anchor=anchor,
                reply=reply,
                user_message_ids=message_ids,
            )
        else:
            memory.touch(
                chat_id,
                prior,
                reply=reply,
                anchor=anchor,
                user_message_id=message_ids[-1] if message_ids else None,
            )
    except Exception:
        logger.exception("vision memory save failed")


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces = []
        for part in content:
            if isinstance(part, str):
                pieces.append(part)
            elif isinstance(part, dict):
                pieces.append(str(part.get("text") or ""))
        return "".join(pieces)
    return str(content or "")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return ""
