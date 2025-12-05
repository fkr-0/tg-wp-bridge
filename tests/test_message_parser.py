# == tests/test_message_parser.py (extended) ==
import pytest
from tg_wp_bridge.schemas import (
    TelegramUpdate,
    TgMessage,
    TgChat,
    TgPhotoSize,
)
from tg_wp_bridge import message_parser


def make_update(
    *,
    chat_type="channel",
    text="hello world",
    caption=None,
    photos=None,
):
    msg = TgMessage(
        message_id=1,
        chat=TgChat(id=123, type=chat_type),
        text=text,
        caption=caption,
        photo=photos,
    )
    return TelegramUpdate(update_id=42, message=msg)


def test_extract_message_entity_prefers_channel_post_when_present():
    msg_channel = TgMessage(
        message_id=2,
        chat=TgChat(id=1, type="channel"),
        text="from channel",
    )
    msg_normal = TgMessage(
        message_id=1,
        chat=TgChat(id=1, type="private"),
        text="from message",
    )
    update = TelegramUpdate(
        update_id=1,
        message=msg_normal,
        channel_post=msg_channel,
    )

    entity = message_parser.extract_message_entity(update)
    assert entity is msg_channel
    assert entity.text == "from channel"


def test_extract_message_text_prefers_text_over_caption():
    update = make_update(text="main text", caption="caption text")
    text = message_parser.extract_message_text(update)
    assert text == "main text"


def test_extract_message_text_uses_caption_if_no_text():
    update = make_update(text=None, caption="caption only")
    text = message_parser.extract_message_text(update)
    assert text == "caption only"


def test_find_photo_with_max_size_returns_largest():
    photos = [
        TgPhotoSize(file_id="a", width=100, height=100),
        TgPhotoSize(file_id="b", width=200, height=100),
        TgPhotoSize(file_id="c", width=150, height=150),
    ]
    msg = TgMessage(
        message_id=10,
        chat=TgChat(id=1, type="channel"),
        text="",
        photo=photos,
    )

    largest = message_parser.find_photo_with_max_size(msg)
    # areas: a=10_000, b=20_000, c=22_500 => c wins
    assert largest is not None
    assert largest.file_id == "c"


def test_find_photo_with_max_size_none_when_no_photos():
    msg = TgMessage(
        message_id=11,
        chat=TgChat(id=1, type="channel"),
        text="",
        photo=None,
    )
    assert message_parser.find_photo_with_max_size(msg) is None


def test_extract_hashtags_simple():
    text = "Hello #world this is a #test."
    tags = message_parser.extract_hashtags(text)
    assert tags == ["#world", "#test"]


def test_extract_hashtags_strips_trailing_punctuation_and_dedupes():
    text = "#blog, #blog! #news? text #end."
    tags = message_parser.extract_hashtags(text)
    assert tags == ["#blog", "#news", "#end"]


def test_build_title_from_text_strips_leading_hashtags():
    text = "#blog #news My title line\nRest of the text"
    title = message_parser.build_title_from_text(text)
    assert title == "My title line"


def test_build_title_from_text_uses_first_nonempty_line():
    text = "\n\n   \nSecond line title\nThird"
    title = message_parser.build_title_from_text(text)
    assert title == "Second line title"


def test_build_title_from_text_fallback_when_empty():
    text = "   \n   "
    title = message_parser.build_title_from_text(text)
    assert title == "(no title)"


def test_text_to_html_single_paragraph():
    html = message_parser.text_to_html("Hello\nworld")
    assert html == "<p>Hello<br>world</p>"


def test_text_to_html_multiple_paragraphs():
    text = "First line\nsecond line\n\nNext paragraph"
    html = message_parser.text_to_html(text)
    # Two paragraphs, first with <br>, second without
    assert html == "<p>First line<br>second line</p><p>Next paragraph</p>"
