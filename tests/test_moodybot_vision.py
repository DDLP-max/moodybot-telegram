# -*- coding: utf-8 -*-
"""Vision ingestion, memory, and the multimodal payload. No Telegram, no model."""
from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from moodybot_vision import (
    ImageMemory,
    ImageRejected,
    assemble_messages,
    classify_vision_intent,
    message_has_image,
    normalize_image,
    split_anchor,
    user_content,
    vision_directive,
)


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def __call__(self):
        return self.moment


def _png(width, height, color=(200, 10, 10)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _memory(tmp, **kwargs):
    clock = kwargs.pop("clock", None) or Clock(datetime(2026, 10, 1, tzinfo=timezone.utc))
    return ImageMemory(tmp, retention_days=14, limit=20, now=clock), clock


def _save(memory, chat, caption, anchor, reply, message_id, payload=b"img"):
    return memory.save(
        chat,
        [(payload, "image/jpeg")],
        caption=caption,
        intent="auto",
        anchor=anchor,
        reply=reply,
        user_message_ids=[message_id],
    )


def test_normalize_jpeg_bounds_and_drops_metadata():
    raw = _png(2000, 900)
    data, mime = normalize_image(raw, "image/png")
    assert mime == "image/jpeg"
    assert data[:2] == b"\xff\xd8"
    with Image.open(io.BytesIO(data)) as image:
        assert max(image.size) <= 1600
        assert min(image.size) >= 8


def test_reject_non_image_and_declared_text():
    try:
        normalize_image(b"not a picture", "text/plain")
    except ImageRejected as exc:
        assert "photo or screenshot" in exc.user_message
        assert "can't see" not in exc.user_message
    else:
        raise AssertionError("text should be rejected")
    try:
        normalize_image(b"not a picture", "image/jpeg")
    except ImageRejected as exc:
        assert "couldn't read" in exc.user_message
        assert "can't see" not in exc.user_message
    else:
        raise AssertionError("garbage bytes should be rejected")
    try:
        normalize_image(b"not heic", "image/heic")
    except ImageRejected as exc:
        assert "HEIC" in exc.user_message
        assert "can't see" not in exc.user_message
    else:
        raise AssertionError("heic garbage should be a format failure")


def test_intents():
    assert classify_vision_intent("") == "auto"
    assert classify_vision_intent("Roast this corporate bullshit.") == "roast"
    assert classify_vision_intent("what is this guy arguing?") == "answer"
    assert classify_vision_intent("this meme though") == "extend"
    assert classify_vision_intent("her hinge profile") == "profile"
    assert classify_vision_intent("screenshot of this tweet") == "argument"


def test_directive_asks_for_the_reveal_not_a_caption():
    text = vision_directive("roast", caption="Roast this", prior=[], image_count=1)
    assert "Do not describe the image and then attach an insult" in text
    assert "unintentionally reveals" in text
    assert "specific visible fact" in text
    assert "wrong line" in text
    assert "ANCHOR:" in text
    compare = vision_directive("auto", caption="", prior=[], image_count=2)
    assert "contradiction between them" in compare


def test_anchor_is_removed_from_the_spoken_reply():
    spoken, anchor = split_anchor(
        "Nothing says family like a poster that forgets your name.\n"
        "ANCHOR: teamwork poster telling employees to work harder"
    )
    assert "ANCHOR" not in spoken
    assert anchor.startswith("teamwork poster")


def test_payload_contains_the_image_bytes_not_a_caption():
    image = _png(32, 32)
    normalized, mime = normalize_image(image, "image/png")
    content = user_content("Roast this", [(normalized, mime)])
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "Roast this"
    assert content[1]["type"] == "image_url"
    url = content[1]["image_url"]["url"]
    header, encoded = url.split(",", 1)
    assert header == "data:image/jpeg;base64"
    assert base64.b64decode(encoded) == normalized
    messages = assemble_messages("SYSTEM", "STRUCTURE", "CLOSER", "SEE", content)
    assert [item["content"] for item in messages[:3]] == ["CLOSER", "STRUCTURE", "SYSTEM"]
    assert messages[-2]["content"] == "SEE"
    assert messages[-1]["content"][1]["type"] == "image_url"


def test_memory_finds_the_hiking_profile_later(tmp_path=None):
    import tempfile
    folder = tmp_path or tempfile.mkdtemp()
    memory, _clock = _memory(folder)
    _save(
        memory, 7, "look at this",
        "dating profile whose whole personality is hiking and emotional availability",
        "She listed a trail and a feeling and called it a person.",
        11,
    )
    _save(
        memory, 7, "Roast this corporate bullshit.",
        "teamwork poster telling people to work harder",
        "Nothing says family like a poster that forgets your name.",
        12,
        payload=b"poster",
    )
    query = "Remember the woman whose entire personality was hiking and emotional availability?"
    found = memory.select(7, query, None)
    assert len(found) == 1
    assert "hiking" in found[0]["anchor"]
    images = memory.load_images(found)
    assert images[0][0] == b"img"


def test_unrelated_text_does_not_pull_an_image():
    import tempfile
    memory, _clock = _memory(tempfile.mkdtemp())
    _save(memory, 7, "", "hiking and emotional availability", "A trail and a feeling.", 3)
    assert memory.select(7, "I had a rough day at work", None) == []
    assert memory.select(7, "the hiking was great", None) == []
    assert memory.select(7, "remember my first job", None) == []


def test_vague_photo_reference_uses_the_latest_image():
    import tempfile
    memory, _clock = _memory(tempfile.mkdtemp())
    _save(memory, 4, "first", "hiking profile", "first reply", 1, payload=b"one")
    _save(memory, 4, "second", "office poster", "second reply", 2, payload=b"two")
    found = memory.select(4, "remember that photo", None)
    assert found[0]["files"]
    assert memory.load_images(found)[0][0] == b"two"


def test_reply_to_the_image_message_uses_that_image():
    import tempfile
    memory, _clock = _memory(tempfile.mkdtemp())
    _save(memory, 4, "first", "hiking profile", "first reply", 21, payload=b"one")
    _save(memory, 4, "second", "office poster", "second reply", 22, payload=b"two")
    reply = SimpleNamespace(message_id=21, text=None, caption=None)
    found = memory.select(4, "and another thing", reply)
    assert memory.load_images(found)[0][0] == b"one"


def test_compare_returns_both_matching_images():
    import tempfile
    memory, _clock = _memory(tempfile.mkdtemp())
    _save(memory, 4, "profile", "hiking and emotional availability", "trail", 1, payload=b"one")
    _save(memory, 4, "poster", "teamwork poster", "names", 2, payload=b"two")
    found = memory.select(4, "compare the hiking profile and the teamwork poster", None)
    assert len(found) == 2
    blobs = {memory.load_images([item])[0][0] for item in found}
    assert blobs == {b"one", b"two"}


def test_retention_drops_the_image():
    import tempfile
    memory, clock = _memory(tempfile.mkdtemp())
    _save(memory, 9, "look", "hiking profile", "reply", 5, payload=b"gone")
    clock.moment = clock.moment + timedelta(days=15)
    assert memory.select(9, "remember that photo", None) == []
    assert list(memory.root.joinpath("9").glob("*.jpg")) == []


def test_memory_survives_restart_and_stays_inside_the_chat():
    import asyncio
    import os
    import tempfile

    from moodybot_vision import ImageMemory, _resolve_images

    folder = tempfile.mkdtemp()
    previous = os.environ.get("MOODYBOT_VISION_MEMORY_DIR")
    os.environ["MOODYBOT_VISION_MEMORY_DIR"] = folder
    try:
        first = ImageMemory(folder, retention_days=14, limit=20)
        _save(first, 11, "profile", "hiking and emotional availability", "She listed a trail.", 21, payload=b"older-profile")
        _save(first, 11, "poster", "teamwork poster", "A poster.", 22, payload=b"newer-poster")
        _save(first, 99, "secret", "private joke about kestrel", "other chat", 21, payload=b"other-chat")

        restarted = ImageMemory(folder, retention_days=14, limit=20)
        reply = SimpleNamespace(message_id=21, text=None, caption=None, photo=None, document=None)
        older = restarted.select(11, "ok", reply)
        assert restarted.load_images(older)[0][0] == b"older-profile"
        other = restarted.select(99, "ok", reply)
        assert restarted.load_images(other)[0][0] == b"other-chat"
        assert restarted.select(11, "remember the private joke about kestrel", None) == []

        def refuse_download(*_args, **_kwargs):
            raise AssertionError("reply should use the stored file, not a new download")

        message = SimpleNamespace(
            message_id=50,
            text="ok",
            caption=None,
            photo=None,
            document=None,
            reply_to_message=reply,
        )
        context = SimpleNamespace(bot=SimpleNamespace(get_file=refuse_download))
        images, _caption, _ids, prior, fresh = asyncio.run(
            _resolve_images(message, context, 11, None)
        )
        assert fresh is False
        assert images[0][0] == b"older-profile"
        assert prior[0]["user_message_ids"] == [21]

        old_folder = tempfile.mkdtemp()
        clock = Clock(datetime(2026, 10, 1, tzinfo=timezone.utc))
        aging = ImageMemory(old_folder, retention_days=14, limit=20, now=clock)
        _save(aging, 11, "profile", "hiking and emotional availability", "She listed a trail.", 21, payload=b"older-profile")
        clock.moment = clock.moment + timedelta(days=15)
        expired = ImageMemory(old_folder, retention_days=14, limit=20, now=clock)
        assert expired.select(11, "ok", reply) == []
        assert list(Path(old_folder, "11").glob("*.jpg")) == []
    finally:
        if previous is None:
            os.environ.pop("MOODYBOT_VISION_MEMORY_DIR", None)
        else:
            os.environ["MOODYBOT_VISION_MEMORY_DIR"] = previous


def test_photo_does_not_fall_through_to_the_text_handler():
    import asyncio
    import moodybot_vision

    seen = []

    async def fake_vision(update, context, mb, grouped=None):
        seen.append(update.message.caption)

    async def compiled(update, context):
        raise AssertionError("text handler must not receive a photo")

    original = moodybot_vision.handle_vision_update
    moodybot_vision.handle_vision_update = fake_vision
    try:
        photo = SimpleNamespace(
            photo=[SimpleNamespace(file_id="x")],
            text=None,
            caption="Roast this",
            document=None,
            media_group_id=None,
            message_id=3,
            reply_to_message=None,
        )
        update = SimpleNamespace(
            message=photo,
            effective_chat=SimpleNamespace(id=1, type="private"),
            update_id=9,
        )
        asyncio.run(moodybot_vision.dispatch(update, SimpleNamespace(), object(), compiled))
        assert seen == ["Roast this"]

        called = []

        async def compiled_text(update, context):
            called.append(update.message.text)

        text = SimpleNamespace(
            message=SimpleNamespace(
                photo=None, text="hello", document=None, caption=None,
                reply_to_message=None, media_group_id=None,
            ),
            effective_chat=SimpleNamespace(id=1, type="private"),
        )
        asyncio.run(moodybot_vision.dispatch(text, SimpleNamespace(), object(), compiled_text))
        assert called == ["hello"]
    finally:
        moodybot_vision.handle_vision_update = original


def test_photo_caption_is_visible_to_text_helpers():
    from moodybot_vision import _update_with_text

    calls = []

    class Message:
        text = None
        caption = "Roast this"

        async def reply_text(self, body):
            calls.append(body)

    update = SimpleNamespace(message=Message(), effective_chat=SimpleNamespace(id=1))
    wrapped = _update_with_text(update, "Roast this")
    assert wrapped.message.text == "Roast this"
    assert wrapped.effective_chat.id == 1
    assert wrapped.message.caption == "Roast this"


def _photo(file_id, size, width, height):
    return SimpleNamespace(file_id=file_id, file_size=size, width=width, height=height)


def _message(**kwargs):
    base = dict(
        message_id=1,
        text=None,
        caption=None,
        photo=None,
        document=None,
        reply_to_message=None,
        external_reply=None,
        forward_origin=None,
        media_group_id=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_largest_photo_is_chosen_even_when_it_is_not_last():
    from moodybot_vision import image_candidates

    message = _message(photo=[
        _photo("thumb", 400, 90, 90),
        _photo("biggest", 180000, 1280, 960),
        _photo("middle", 4000, 320, 240),
    ])
    assert image_candidates(message)[0][0] == "biggest"


def test_forwarded_screenshot_uses_the_photo_on_the_message():
    from moodybot_vision import image_candidates

    message = _message(
        caption="Looked at my yoga teacher and sighed smh",
        forward_origin=SimpleNamespace(type="user"),
        photo=[_photo("forwarded", 90000, 1000, 800)],
    )
    assert message_has_image(message) is True
    assert image_candidates(message)[0] == ("forwarded", "image/jpeg")


def test_image_document_and_extension_only_file_are_images():
    png = _message(document=SimpleNamespace(
        file_id="png", mime_type="image/png", file_name="shot.png",
    ))
    heic = _message(document=SimpleNamespace(
        file_id="heic", mime_type="image/heic", file_name="Photo.HEIC",
    ))
    nameless = _message(document=SimpleNamespace(
        file_id="jpg", mime_type="application/octet-stream", file_name="Photo.jpg",
    ))
    pdf = _message(document=SimpleNamespace(
        file_id="pdf", mime_type="application/pdf", file_name="notes.pdf",
    ))
    assert [item[0] for item in __import__("moodybot_vision").image_candidates(png)] == ["png"]
    assert message_has_image(heic) is True
    assert message_has_image(nameless) is True
    assert message_has_image(pdf) is False


def test_external_reply_photo_counts_as_the_attachment():
    message = _message(
        text="roast this",
        external_reply=SimpleNamespace(
            photo=[_photo("outside", 5000, 800, 600)],
            document=None,
        ),
    )
    assert message_has_image(message) is True
    from moodybot_vision import image_candidates
    assert image_candidates(message)[0][0] == "outside"


def test_reply_to_an_image_keeps_the_instruction_and_the_pixels():
    import asyncio
    from moodybot_vision import _resolve_images

    path = _write_png()
    reply = _message(
        message_id=21,
        caption="gym thread",
        photo=[
            _photo("small", 100, 40, 40),
            _photo("large", 8000, 900, 700),
        ],
    )
    message = _message(
        message_id=22,
        text="roast the teacher",
        reply_to_message=reply,
    )

    class Bot:
        async def get_file(self, file_id):
            assert file_id == "large"
            from telegram import File
            return File(file_id=file_id, file_unique_id="u", file_path=str(path))

    images, caption, _ids, prior, fresh = asyncio.run(
        _resolve_images(message, SimpleNamespace(bot=Bot()), 7, None)
    )
    assert fresh is True
    assert prior == []
    assert caption == "roast the teacher\ngym thread"
    assert images[0][0][:2] == b"\xff\xd8"
    assert "can't see" not in caption


def test_retrieval_failure_is_not_the_generic_blind_reply():
    import asyncio
    from moodybot_vision import ImageRetrievalFailed, _resolve_images

    message = _message(
        caption="Photo",
        photo=[_photo("native", 12000, 1280, 720)],
    )

    class Bot:
        async def get_file(self, file_id):
            raise RuntimeError("getFile failed")

    try:
        asyncio.run(_resolve_images(message, SimpleNamespace(bot=Bot()), 7, None))
    except ImageRetrievalFailed as exc:
        assert "download" in exc.user_message
        assert "can't see" not in exc.user_message
    else:
        raise AssertionError("a failed download must not look like a successful read")


def test_file_named_photo_is_downloaded_not_remembered():
    """A file Telegram shows as 'Photo' is a new upload, not a memory lookup."""
    import asyncio
    from moodybot_vision import ImageRetrievalFailed, _resolve_images, has_own_media

    path = Path(__import__("tempfile").mkdtemp()) / "bare.jpg"
    Image.new("RGB", (240, 80), (10, 20, 200)).save(path, format="JPEG", quality=90)
    message = _message(
        caption="Describe exactly what you see in this image.",
        document=SimpleNamespace(
            file_id="bare-photo", mime_type="application/octet-stream", file_name="Photo",
        ),
    )
    assert has_own_media(message)

    class Bot:
        async def get_file(self, file_id):
            assert file_id == "bare-photo"
            from telegram import File
            return File(file_id=file_id, file_unique_id="b", file_path=str(path))

    images, caption, _ids, prior, fresh = asyncio.run(
        _resolve_images(message, SimpleNamespace(bot=Bot()), 7, None)
    )
    assert fresh is True and prior == []
    assert images[0][0][:2] == b"\xff\xd8"
    assert caption.startswith("Describe exactly")

    class DeadBot:
        async def get_file(self, file_id):
            raise RuntimeError("telegram getFile failed")

    try:
        asyncio.run(_resolve_images(message, SimpleNamespace(bot=DeadBot()), 7, None))
    except ImageRetrievalFailed as exc:
        assert "don't still have" not in exc.user_message
    else:
        raise AssertionError("a new Photo file must not fall through to memory")


def test_fresh_photo_is_not_answered_from_memory():
    import asyncio
    from moodybot_vision import ImageRetrievalFailed, _resolve_images

    class Remembered:
        def select(self, *args, **kwargs):
            raise AssertionError("a new photo must not be looked up in memory")

    message = _message(
        caption="Describe exactly what you see in this image.",
        photo=[_photo("new-photo", 20000, 800, 600)],
    )

    class Bot:
        async def get_file(self, file_id):
            raise RuntimeError("telegram getFile failed")

    try:
        asyncio.run(_resolve_images(message, SimpleNamespace(bot=Bot()), 7, None))
    except ImageRetrievalFailed as exc:
        assert "download" in exc.user_message
        assert "don't still have" not in exc.user_message
    else:
        raise AssertionError("failed download of a new photo must not fall through to memory")
    Remembered()


def test_ptb_photo_update_puts_pixels_in_the_model_request():
    import asyncio
    from telegram import Update
    from moodybot_vision import _payload_shape, _resolve_images, user_content

    path = Path(__import__("tempfile").mkdtemp()) / "seen.jpg"
    Image.new("RGB", (320, 200), (220, 30, 40)).save(path, format="JPEG", quality=90)
    update = Update.de_json(
        {
            "update_id": 501,
            "message": {
                "message_id": 77,
                "date": 1760000000,
                "chat": {"id": 42, "type": "private"},
                "caption": "Describe exactly what you see in this image.",
                "photo": [
                    {"file_id": "small", "file_unique_id": "s", "width": 40, "height": 25, "file_size": 400},
                    {"file_id": "full", "file_unique_id": "f", "width": 320, "height": 200, "file_size": 12000},
                ],
            },
        },
        bot=None,
    )

    class Bot:
        async def get_file(self, file_id):
            assert file_id == "full"
            from telegram import File
            return File(file_id=file_id, file_unique_id="f", file_path=str(path))

    images, caption, _ids, prior, fresh = asyncio.run(
        _resolve_images(update.message, SimpleNamespace(bot=Bot()), 42, None)
    )
    assert fresh is True and prior == []
    assert caption.startswith("Describe exactly")
    content = user_content(caption, images)
    assert content[1]["type"] == "image_url"
    assert _payload_shape([{"role": "user", "content": content}]).startswith("user[text,image:")


def test_real_jpeg_reaches_the_model_payload():
    """Read a real JPEG through Telegram's file object, then into the model payload."""
    import asyncio
    from telegram import File
    from moodybot_vision import _resolve_images, user_content

    folder = Path(__import__("tempfile").mkdtemp())
    path = folder / "native.jpg"
    Image.new("RGB", (640, 480), (12, 40, 90)).save(path, format="JPEG", quality=90)

    message = _message(
        caption="Photo",
        forward_origin=None,
        photo=[
            _photo("thumb", 200, 80, 60),
            _photo("native-full", 40000, 640, 480),
        ],
    )

    class Bot:
        async def get_file(self, file_id):
            assert file_id == "native-full"
            return File(file_id=file_id, file_unique_id="native", file_path=str(path))

    images, caption, _ids, _prior, fresh = asyncio.run(
        _resolve_images(message, SimpleNamespace(bot=Bot()), 3, None)
    )
    assert fresh is True
    assert caption == "Photo"
    content = user_content(caption, images)
    header, encoded = content[1]["image_url"]["url"].split(",", 1)
    assert header == "data:image/jpeg;base64"
    decoded = base64.b64decode(encoded)
    assert decoded[:2] == b"\xff\xd8"
    with Image.open(io.BytesIO(decoded)) as image:
        assert image.size == (640, 480)


def _write_png() -> Path:
    folder = Path(__import__("tempfile").mkdtemp())
    path = folder / "reply.png"
    Image.new("RGB", (120, 80), (200, 10, 10)).save(path, format="PNG")
    return path


def test_photo_message_is_not_a_text_turn():
    photo = SimpleNamespace(file_id="abc")
    message = SimpleNamespace(photo=[photo], text=None, document=None, caption="Roast this")
    assert message_has_image(message) is True
    text = SimpleNamespace(photo=None, text="hello", document=None, caption=None)
    assert message_has_image(text) is False
    document = SimpleNamespace(
        photo=None,
        text=None,
        caption=None,
        document=SimpleNamespace(mime_type="image/png", file_id="doc"),
    )
    assert message_has_image(document) is True


def _run() -> None:
    test_normalize_jpeg_bounds_and_drops_metadata()
    test_reject_non_image_and_declared_text()
    test_intents()
    test_directive_asks_for_the_reveal_not_a_caption()
    test_anchor_is_removed_from_the_spoken_reply()
    test_payload_contains_the_image_bytes_not_a_caption()
    test_memory_finds_the_hiking_profile_later()
    test_unrelated_text_does_not_pull_an_image()
    test_vague_photo_reference_uses_the_latest_image()
    test_reply_to_the_image_message_uses_that_image()
    test_compare_returns_both_matching_images()
    test_retention_drops_the_image()
    test_memory_survives_restart_and_stays_inside_the_chat()
    test_photo_does_not_fall_through_to_the_text_handler()
    test_photo_caption_is_visible_to_text_helpers()
    test_photo_message_is_not_a_text_turn()
    test_largest_photo_is_chosen_even_when_it_is_not_last()
    test_forwarded_screenshot_uses_the_photo_on_the_message()
    test_image_document_and_extension_only_file_are_images()
    test_external_reply_photo_counts_as_the_attachment()
    test_reply_to_an_image_keeps_the_instruction_and_the_pixels()
    test_retrieval_failure_is_not_the_generic_blind_reply()
    test_file_named_photo_is_downloaded_not_remembered()
    test_fresh_photo_is_not_answered_from_memory()
    test_ptb_photo_update_puts_pixels_in_the_model_request()
    test_real_jpeg_reaches_the_model_payload()
    print("vision tests ok")


if __name__ == "__main__":
    _run()
