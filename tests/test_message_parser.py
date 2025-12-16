# == tests/test_message_parser.py (extended) ==
from tg_wp_bridge.schemas import (
    TelegramUpdate,
    TgMessage,
    TgChat,
    TgPhotoSize,
    TgVideo,
    TgAnimation,
    TgDocument,
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


def test_text_to_html_preserves_html_entities():
    """Test that HTML entities are preserved."""
    text = 'First line & second line < > "quotes"'
    html = message_parser.text_to_html(text)
    assert "First line" in html
    assert "second line" in html


def test_extract_hashtags_special_characters():
    """Test hashtag extraction with special characters."""
    text = "Check out #test_case and #123numbers and #混合语言"
    tags = message_parser.extract_hashtags(text)
    assert "#test_case" in tags
    assert "#123numbers" in tags
    assert "#混合语言" in tags


def test_extract_hashtags_complex_punctuation():
    """Test hashtag extraction with complex punctuation scenarios."""
    text = "#tag1; #tag2: #tag3) #tag4( #tag5[ #tag6]"
    tags = message_parser.extract_hashtags(text)
    assert "#tag1" in tags
    assert "#tag2" in tags
    assert "#tag3" in tags
    assert "#tag4" in tags
    assert "#tag5" in tags
    assert "#tag6" in tags


def test_find_photo_with_max_size_equal_areas():
    """Test photo selection when multiple photos have equal areas."""
    photos = [
        TgPhotoSize(file_id="a", width=100, height=100),  # area: 10_000
        TgPhotoSize(file_id="b", width=100, height=100),  # area: 10_000
        TgPhotoSize(file_id="c", width=50, height=200),  # area: 10_000
    ]
    msg = TgMessage(
        message_id=10,
        chat=TgChat(id=1, type="channel"),
        text="",
        photo=photos,
    )

    largest = message_parser.find_photo_with_max_size(msg)
    # Should return the first one when areas are equal
    assert largest is not None
    assert largest.file_id == "a"


def test_extract_message_entity_favors_channel_post():
    """Test that channel_post is preferred over message."""
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

    # Also test the reverse - message only
    update_message_only = TelegramUpdate(
        update_id=2,
        message=msg_normal,
    )
    entity = message_parser.extract_message_entity(update_message_only)
    assert entity is msg_normal

    # Test with neither present
    update_empty = TelegramUpdate(update_id=3)
    entity = message_parser.extract_message_entity(update_empty)
    assert entity is None


def test_build_title_from_text_unicode_handling():
    """Test title building with Unicode characters."""
    text = "#blog 🌟 My title with émojis and càracters\nMore text"
    title = message_parser.build_title_from_text(text)
    assert title == "🌟 My title with émojis and càracters"


def test_build_title_from_text_very_long_line():
    """Test title building with very long first line."""
    long_text = "A" * 200 + "\nSecond line"
    title = message_parser.build_title_from_text(long_text, max_length=200)
    assert title == "A" * 200


def test_extract_message_text_with_empty_string():
    """Test message text extraction when both text and caption are empty strings."""
    update = make_update(text="", caption="")
    text = message_parser.extract_message_text(update)
    assert text == ""


def test_extract_hashtags_empty_text():
    """Test hashtag extraction with empty text."""
    tags = message_parser.extract_hashtags("")
    assert tags == []


def test_text_to_html_empty_text():
    """Test HTML conversion with empty text."""
    html = message_parser.text_to_html("")
    assert html == "<p></p>"


def test_text_to_html_only_whitespace():
    """Test HTML conversion with only whitespace."""
    html = message_parser.text_to_html("   \n  \n   ")
    # After strip, empty string should return empty paragraph
    assert html == "<p></p>"


def test_collect_supported_media_photo_and_video():
    """Collect both photos and videos in order."""
    photos = [
        TgPhotoSize(file_id="small", width=50, height=50),
        TgPhotoSize(file_id="large", width=200, height=100),
    ]
    msg = TgMessage(
        message_id=1,
        chat=TgChat(id=1, type="channel"),
        text="",
        photo=photos,
        video=TgVideo(file_id="vid123", file_name="clip.mp4", mime_type="video/mp4"),
    )
    media = message_parser.collect_supported_media(msg)
    assert [m.media_type for m in media] == ["photo", "video"]
    assert media[0].file_id == "large"
    assert media[1].file_name == "clip.mp4"


def test_collect_supported_media_deduplicates_file_ids():
    """Ensure duplicate file IDs are not added multiple times."""
    msg = TgMessage(
        message_id=2,
        chat=TgChat(id=1, type="channel"),
        text="",
        animation=TgAnimation(file_id="dup", file_name="fun.gif"),
        document=TgDocument(file_id="dup", file_name="fun.gif"),
    )
    media = message_parser.collect_supported_media(msg)
    assert len(media) == 1
    assert media[0].media_type == "animation"


def test_collect_supported_media_document_only():
    """Document attachments should be surfaced as media entries."""
    msg = TgMessage(
        message_id=3,
        chat=TgChat(id=1, type="channel"),
        text="",
        document=TgDocument(file_id="doc1", file_name="file.pdf", mime_type="application/pdf"),
    )
    media = message_parser.collect_supported_media(msg)
    assert len(media) == 1
    assert media[0].media_type == "document"
    assert media[0].mime_type == "application/pdf"


# == end/tests/test_message_parser.py ==
