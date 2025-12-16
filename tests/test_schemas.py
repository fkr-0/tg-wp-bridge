"""
Tests for schemas module to ensure Pydantic models work correctly.
"""

import pytest
from pydantic import ValidationError

from tg_wp_bridge.schemas import (
    TgChat,
    TgPhotoSize,
    TgMessage,
    TelegramUpdate,
    WPMediaResponse,
    WPPostResponse,
    TelegramWebhookInfo,
)


class TestTelegramModels:
    """Test Telegram-related schema models."""

    def test_tg_chat_basic(self):
        """Test basic TgChat creation."""
        chat = TgChat(id=123, type="channel")
        assert chat.id == 123
        assert chat.type == "channel"

    def test_tg_chat_with_extra_fields(self):
        """Test TgChat with extra fields (extra='allow')."""
        chat = TgChat(id=123, type="channel", title="Test Channel")
        assert chat.id == 123
        assert chat.type == "channel"
        # Extra fields should be accessible
        assert chat.title == "Test Channel"

    def test_tg_photo_size_basic(self):
        """Test basic TgPhotoSize creation."""
        photo = TgPhotoSize(file_id="abc123", width=100, height=200)
        assert photo.file_id == "abc123"
        assert photo.width == 100
        assert photo.height == 200

    def test_tg_photo_size_with_extra_fields(self):
        """Test TgPhotoSize with extra fields."""
        photo = TgPhotoSize(
            file_id="abc123",
            width=100,
            height=200,
            file_size=1024,
            file_unique_id="unique123",
        )
        assert photo.file_size == 1024
        assert photo.file_unique_id == "unique123"

    def test_tg_message_basic(self):
        """Test basic TgMessage creation."""
        chat = TgChat(id=123, type="channel")
        message = TgMessage(message_id=456, chat=chat, text="Hello world")
        assert message.message_id == 456
        assert message.chat is chat
        assert message.text == "Hello world"
        assert message.caption is None
        assert message.photo is None

    def test_tg_message_with_caption_and_photo(self):
        """Test TgMessage with caption and photo."""
        chat = TgChat(id=123, type="channel")
        photo = TgPhotoSize(file_id="photo123", width=100, height=100)
        message = TgMessage(
            message_id=456, chat=chat, caption="Photo caption", photo=[photo]
        )
        assert message.caption == "Photo caption"
        assert message.photo == [photo]

    def test_telegram_update_basic(self):
        """Test basic TelegramUpdate creation."""
        chat = TgChat(id=123, type="channel")
        message = TgMessage(message_id=456, chat=chat, text="Hello")
        update = TelegramUpdate(update_id=789, message=message)
        assert update.update_id == 789
        assert update.message is message
        assert update.channel_post is None

    def test_telegram_update_with_channel_post(self):
        """Test TelegramUpdate with channel_post."""
        chat = TgChat(id=123, type="channel")
        channel_post = TgMessage(message_id=456, chat=chat, text="Channel message")
        update = TelegramUpdate(update_id=789, channel_post=channel_post)
        assert update.update_id == 789
        assert update.message is None
        assert update.channel_post is channel_post

    def test_telegram_update_both_message_and_channel_post(self):
        """Test TelegramUpdate with both message and channel_post."""
        chat = TgChat(id=123, type="private")
        message = TgMessage(message_id=1, chat=chat, text="Private message")
        channel_chat = TgChat(id=456, type="channel")
        channel_post = TgMessage(
            message_id=2, chat=channel_chat, text="Channel message"
        )

        update = TelegramUpdate(
            update_id=789, message=message, channel_post=channel_post
        )

        assert update.message is message
        assert update.channel_post is channel_post


class TestWordPressModels:
    """Test WordPress-related schema models."""

    def test_wp_media_response_basic(self):
        """Test basic WPMediaResponse creation."""
        media = WPMediaResponse(id=123)
        assert media.id == 123
        assert media.source_url is None

    def test_wp_media_response_with_url(self):
        """Test WPMediaResponse with source_url."""
        media = WPMediaResponse(id=123, source_url="https://example.com/image.jpg")
        assert media.id == 123
        assert str(media.source_url) == "https://example.com/image.jpg"

    def test_wp_media_response_invalid_url(self):
        """Test WPMediaResponse with invalid URL."""
        with pytest.raises(ValidationError):
            WPMediaResponse(id=123, source_url="not-a-url")

    def test_wp_post_response_basic(self):
        """Test basic WPPostResponse creation."""
        post = WPPostResponse(
            id=456,
            title={"rendered": "Test Title"},
            content={"rendered": "<p>Test content</p>"},
        )
        assert post.id == 456
        assert post.title["rendered"] == "Test Title"
        assert post.content["rendered"] == "<p>Test content</p>"
        assert post.link is None

    def test_wp_post_response_with_link(self):
        """Test WPPostResponse with link."""
        post = WPPostResponse(
            id=456,
            link="https://example.com/post/456",
            title={"rendered": "Test Title"},
            content={"rendered": "<p>Test content</p>"},
        )
        assert str(post.link) == "https://example.com/post/456"


class TestTelegramWebhookInfo:
    """Test TelegramWebhookInfo model."""

    def test_webhook_info_basic(self):
        """Test basic TelegramWebhookInfo creation."""
        info = TelegramWebhookInfo(
            url="https://example.com/webhook",
            has_custom_certificate=False,
            pending_update_count=0,
        )
        assert info.url == "https://example.com/webhook"
        assert info.has_custom_certificate is False
        assert info.pending_update_count == 0

    def test_webhook_info_error_response(self):
        """Test TelegramWebhookInfo with error response."""
        info = TelegramWebhookInfo(
            url=None,
            last_error_date=1234567890,
            last_error_message="Bad request",
        )
        assert info.last_error_date == 1234567890
        assert info.last_error_message == "Bad request"

    def test_webhook_info_complex_result(self):
        """Test TelegramWebhookInfo with complex result object."""
        info = TelegramWebhookInfo(
            url="https://example.com/webhook/secret",
            has_custom_certificate=False,
            pending_update_count=0,
            last_error_date=1234567890,
            last_error_message="Wrong response from the host",
            max_connections=40,
            ip_address="1.2.3.4",
            allowed_updates=["message", "channel_post"],
        )
        assert info.url == "https://example.com/webhook/secret"
        assert info.allowed_updates == ["message", "channel_post"]
        assert info.max_connections == 40


class TestModelExtraBehavior:
    """Test that models properly handle extra fields."""

    def test_all_models_allow_extra(self):
        """Test that all models have extra='allow' behavior."""
        # TgChat
        chat = TgChat(id=123, type="channel", extra_field="extra")
        assert chat.extra_field == "extra"

        # TgPhotoSize
        photo = TgPhotoSize(file_id="test", width=100, height=100, extra="extra")
        assert photo.extra == "extra"

        # TgMessage
        msg = TgMessage(message_id=1, chat=chat, extra_field="extra")
        assert msg.extra_field == "extra"

        # TelegramUpdate
        update = TelegramUpdate(update_id=1, message=msg, extra_field="extra")
        assert update.extra_field == "extra"

        # WPMediaResponse
        media = WPMediaResponse(id=1, extra_field="extra")
        assert media.extra_field == "extra"

        # WPPostResponse
        post = WPPostResponse(
            id=1,
            title={"rendered": "Test"},
            content={"rendered": "Test"},
            extra_field="extra",
        )
        assert post.extra_field == "extra"

        # TelegramWebhookInfo
        webhook_info = TelegramWebhookInfo(url="https://example.com", extra_field="extra")
        assert webhook_info.extra_field == "extra"
