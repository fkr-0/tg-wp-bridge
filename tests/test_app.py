"""
Tests for app.py FastAPI application.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from tg_wp_bridge import app
from tg_wp_bridge.app import handle_telegram_update
from tg_wp_bridge.schemas import (
    TelegramUpdate,
    TgMessage,
    TgChat,
    TgPhotoSize,
    TgDocument,
    TgVideo,
    TelegramWebhookInfo,
    WPMediaResponse,
)


def make_wp_media(media_id=456, url="https://example.com/media.jpg"):
    return WPMediaResponse(id=media_id, source_url=url)


class TestHealthEndpoint:
    """Test /healthz endpoint."""

    def test_healthz_success(self):
        """Test health check returns ok status."""
        from fastapi.testclient import TestClient

        client = TestClient(app.app)
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestTelegramWebhook:
    """Test /webhook/{secret} endpoint."""

    def test_webhook_invalid_secret(self, monkeypatch):
        """Test webhook rejects invalid secret."""
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "correct_secret")

        from fastapi.testclient import TestClient

        client = TestClient(app.app)

        update_data = {
            "update_id": 123,
            "message": {"message_id": 1, "chat": {"id": 1, "type": "channel"}},
        }

        response = client.post("/webhook/wrong_secret", json=update_data)
        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"

    def test_webhook_valid_secret_success(self, monkeypatch):
        """Test webhook accepts valid secret and processes update."""
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test_secret")

        from fastapi.testclient import TestClient

        # Mock the settings directly in the app module
        with patch("tg_wp_bridge.app.settings") as mock_settings:
            mock_settings.telegram_webhook_secret = "test_secret"

            client = TestClient(app.app)

            update_data = {
                "update_id": 123,
                "channel_post": {
                    "message_id": 1,
                    "chat": {"id": 1, "type": "channel"},
                    "text": "Test message",
                },
            }

            with patch(
                "tg_wp_bridge.app.handle_telegram_update", new_callable=AsyncMock
            ) as mock_handle:
                mock_handle.return_value = None

                response = client.post("/webhook/test_secret", json=update_data)
                assert response.status_code == 200
                assert response.json() == {"ok": True}
                mock_handle.assert_called_once()

    def test_webhook_processing_error_returns_200(self, monkeypatch):
        """Test webhook returns 200 even when processing fails."""
        from fastapi.testclient import TestClient

        # Mock the settings directly in the app module
        with patch("tg_wp_bridge.app.settings") as mock_settings:
            mock_settings.telegram_webhook_secret = "test_secret"

            client = TestClient(app.app)

            update_data = {
                "update_id": 123,
                "channel_post": {
                    "message_id": 1,
                    "chat": {"id": 1, "type": "channel"},
                    "text": "Test message",
                },
            }

            with patch(
                "tg_wp_bridge.app.handle_telegram_update", new_callable=AsyncMock
            ) as mock_handle:
                mock_handle.side_effect = Exception("Processing error")

                response = client.post("/webhook/test_secret", json=update_data)
                assert response.status_code == 200
                assert response.json()["ok"] is False
                assert "Processing error" in response.json()["error"]


class TestTelegramManagementEndpoints:
    """Test Telegram webhook management endpoints."""

    @pytest.mark.asyncio
    async def test_set_webhook_success(self, monkeypatch):
        """Test successful webhook setup via HTTP endpoint."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
        monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "webhook_secret")

        mock_response = {"ok": True, "result": True}

        with patch(
            "tg_wp_bridge.telegram_api.set_webhook", new_callable=AsyncMock
        ) as mock_set:
            mock_set.return_value = mock_response

            from fastapi.testclient import TestClient

            client = TestClient(app.app)
            response = client.post("/telegram/set_webhook")
            assert response.status_code == 200
            assert response.json() == mock_response

    @pytest.mark.asyncio
    async def test_set_webhook_error(self, monkeypatch):
        """Test webhook setup error via HTTP endpoint."""
        with patch(
            "tg_wp_bridge.telegram_api.set_webhook", new_callable=AsyncMock
        ) as mock_set:
            mock_set.side_effect = Exception("API error")

            from fastapi.testclient import TestClient

            client = TestClient(app.app)
            response = client.post("/telegram/set_webhook")
            assert response.status_code == 500
            assert "API error" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_webhook_info_success(self, monkeypatch):
        """Test successful webhook info retrieval via HTTP endpoint."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")

        mock_response = TelegramWebhookInfo(
            url="https://example.com/webhook/secret",
            pending_update_count=0,
        )

        with patch(
            "tg_wp_bridge.telegram_api.get_webhook_info", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            from fastapi.testclient import TestClient

            client = TestClient(app.app)
            response = client.get("/telegram/webhook_info")
            assert response.status_code == 200
            assert response.json() == mock_response.model_dump()

    @pytest.mark.asyncio
    async def test_get_webhook_info_error(self, monkeypatch):
        """Test webhook info error via HTTP endpoint."""
        with patch(
            "tg_wp_bridge.telegram_api.get_webhook_info", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = Exception("API error")

            from fastapi.testclient import TestClient

            client = TestClient(app.app)
            response = client.get("/telegram/webhook_info")
            assert response.status_code == 500
            assert "API error" in response.json()["detail"]


class TestHandleTelegramUpdate:
    """Test handle_telegram_update function."""

    @pytest.mark.asyncio
    async def test_handle_update_no_message(self, monkeypatch):
        """Test handling update with no message or channel_post."""
        # Mock settings
        monkeypatch.setenv("REQUIRED_HASHTAG", "")

        update = TelegramUpdate(update_id=123)

        # Should not raise any exception
        await handle_telegram_update(update)

    @pytest.mark.asyncio
    async def test_handle_update_non_channel_ignored(self, monkeypatch):
        """Test handling non-channel message is ignored."""
        monkeypatch.setenv("REQUIRED_HASHTAG", "")

        msg = TgMessage(message_id=1, chat=TgChat(id=1, type="private"), text="Hello")
        update = TelegramUpdate(update_id=123, message=msg)

        # Should not raise any exception
        await handle_telegram_update(update)

    @pytest.mark.asyncio
    async def test_handle_update_empty_text_ignored(self, monkeypatch):
        """Test handling message with empty text is ignored."""
        monkeypatch.setenv("REQUIRED_HASHTAG", "")

        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="   ",  # whitespace only
        )
        update = TelegramUpdate(update_id=123, message=msg)

        # Should not raise any exception
        await handle_telegram_update(update)

    @pytest.mark.asyncio
    async def test_handle_update_missing_hashtag_ignored(self, monkeypatch):
        """Test handling message without required hashtag is ignored."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="Hello world",  # no #blog hashtag
        )
        update = TelegramUpdate(update_id=123, message=msg)

        # Mock the settings directly in the app module
        with patch("tg_wp_bridge.app.settings") as mock_settings:
            mock_settings.required_hashtag = "#blog"
            mock_settings.chat_type_allowlist = ("channel",)
            mock_settings.hashtag_allowlist = None
            mock_settings.hashtag_blocklist = None

            # Mock wordpress_api.create_wp_post to avoid actual HTTP calls
            with patch(
                "tg_wp_bridge.wordpress_api.create_wp_post", new_callable=AsyncMock
            ) as mock_create:
                # Should not raise any exception
                await handle_telegram_update(update)
                # Should not be called since hashtag is missing
                mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_update_with_required_hashtag(self, monkeypatch):
        """Test handling message with required hashtag."""
        msg = TgMessage(
            message_id=1, chat=TgChat(id=1, type="channel"), text="#blog Hello world"
        )
        update = TelegramUpdate(update_id=123, message=msg)

        # Mock the settings directly in the app module
        with patch("tg_wp_bridge.app.settings") as mock_settings:
            mock_settings.required_hashtag = "#blog"
            mock_settings.chat_type_allowlist = ("channel",)
            mock_settings.hashtag_allowlist = None
            mock_settings.hashtag_blocklist = None

            with patch(
                "tg_wp_bridge.wordpress_api.create_wp_post", new_callable=AsyncMock
            ) as mock_create:
                mock_post = MagicMock()
                mock_post.id = 456
                mock_post.link = "https://example.com/post/456"
                mock_create.return_value = mock_post

                await handle_telegram_update(update)

                mock_create.assert_called_once()
                call_args = mock_create.call_args[1]
                assert (
                    call_args["title"] == "Hello world"
                )  # hashtag stripped from title
                assert "#blog" in call_args["content_html"]

    @pytest.mark.asyncio
    async def test_handle_update_with_photo(self, monkeypatch):
        """Test handling message with photo."""
        monkeypatch.setenv("REQUIRED_HASHTAG", "")
        monkeypatch.setenv("WP_BASE_URL", "https://wordpress.example.com")
        monkeypatch.setenv("WP_USERNAME", "testuser")
        monkeypatch.setenv("WP_APP_PASSWORD", "testpass")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")

        photos = [TgPhotoSize(file_id="photo123", width=100, height=100)]

        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="Photo post",
            photo=photos,
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with (
            patch(
                "tg_wp_bridge.telegram_api.get_file_direct_url", new_callable=AsyncMock
            ) as mock_url,
            patch(
                "tg_wp_bridge.telegram_api.download_file", new_callable=AsyncMock
            ) as mock_download,
            patch(
                "tg_wp_bridge.wordpress_api.upload_media_to_wp", new_callable=AsyncMock
            ) as mock_upload,
            patch(
                "tg_wp_bridge.wordpress_api.create_wp_post", new_callable=AsyncMock
            ) as mock_create,
        ):
            mock_url.return_value = "https://api.telegram.org/file/bottoken/photo.jpg"
            mock_download.return_value = b"fake image data"
            mock_upload.return_value = make_wp_media(456, "https://example.com/photo.jpg")
            mock_post = MagicMock()
            mock_post.id = 789
            mock_post.link = "https://example.com/post/789"
            mock_create.return_value = mock_post

            await handle_telegram_update(update)

            # Verify photo processing chain
            mock_url.assert_called_once_with("photo123")
            mock_download.assert_called_once()
            mock_upload.assert_called_once()
            mock_create.assert_called_once()

            # Verify media ID is passed to create post
            call_args = mock_create.call_args[1]
            assert call_args["media_ids"] == [456]
            assert '<img src="https://example.com/photo.jpg"' in call_args["content_html"]

    @pytest.mark.asyncio
    async def test_handle_update_photo_error_continues(self, monkeypatch):
        """Test handling message with photo when photo processing fails."""
        monkeypatch.setenv("REQUIRED_HASHTAG", "")
        monkeypatch.setenv("WP_BASE_URL", "https://wordpress.example.com")
        monkeypatch.setenv("WP_USERNAME", "testuser")
        monkeypatch.setenv("WP_APP_PASSWORD", "testpass")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")

        photos = [TgPhotoSize(file_id="photo123", width=100, height=100)]

        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="Photo post with error",
            photo=photos,
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with (
            patch(
                "tg_wp_bridge.telegram_api.get_file_direct_url", new_callable=AsyncMock
            ) as mock_url,
            patch(
                "tg_wp_bridge.wordpress_api.create_wp_post", new_callable=AsyncMock
            ) as mock_create,
        ):
            mock_url.side_effect = Exception("Telegram API error")
            mock_post = MagicMock()
            mock_post.id = 123
            mock_post.link = "https://example.com/post/123"
            mock_create.return_value = mock_post

            # Should not raise exception despite photo error
            await handle_telegram_update(update)

            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            assert call_args["media_ids"] == []  # empty due to photo error

    @pytest.mark.asyncio
    async def test_handle_update_media_only_photo(self):
        """Photo-only posts should still be mirrored."""
        photos = [TgPhotoSize(file_id="photo123", width=100, height=200)]
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="",
            photo=photos,
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with (
            patch(
                "tg_wp_bridge.telegram_api.get_file_direct_url", new_callable=AsyncMock
            ) as mock_url,
            patch(
                "tg_wp_bridge.telegram_api.download_file", new_callable=AsyncMock
            ) as mock_download,
            patch(
                "tg_wp_bridge.wordpress_api.upload_media_to_wp",
                new_callable=AsyncMock,
            ) as mock_upload,
            patch(
                "tg_wp_bridge.wordpress_api.create_wp_post",
                new_callable=AsyncMock,
            ) as mock_create,
        ):
            mock_url.return_value = "https://api.telegram.org/file/bottoken/photo.jpg"
            mock_download.return_value = b"img"
            mock_upload.return_value = make_wp_media(99, "https://example.com/photo.jpg")

            await handle_telegram_update(update)

            mock_create.assert_called_once()
            assert mock_create.call_args[1]["media_ids"] == [99]
            assert mock_create.call_args[1]["content_html"].startswith('<figure class="telegram-media telegram-photo">')

    @pytest.mark.asyncio
    async def test_handle_update_video_without_text(self):
        """Video-only posts are uploaded as media."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text=None,
            video=TgVideo(file_id="video1", file_name="clip.mp4", mime_type="video/mp4"),
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with (
            patch(
                "tg_wp_bridge.telegram_api.get_file_direct_url", new_callable=AsyncMock
            ) as mock_url,
            patch(
                "tg_wp_bridge.telegram_api.download_file", new_callable=AsyncMock
            ) as mock_download,
            patch(
                "tg_wp_bridge.wordpress_api.upload_media_to_wp",
                new_callable=AsyncMock,
            ) as mock_upload,
            patch(
                "tg_wp_bridge.wordpress_api.create_wp_post",
                new_callable=AsyncMock,
            ) as mock_create,
        ):
            mock_url.return_value = "https://api.telegram.org/file/bottoken/video.mp4"
            mock_download.return_value = b"video"
            mock_upload.return_value = make_wp_media(101, "https://example.com/video.mp4")

            await handle_telegram_update(update)

            mock_upload.assert_called_once()
            mock_create.assert_called_once()
            assert mock_create.call_args[1]["media_ids"] == [101]
            assert '<video controls src="https://example.com/video.mp4"' in mock_create.call_args[1]["content_html"]

    @pytest.mark.asyncio
    async def test_handle_update_document_link(self):
        """Document uploads become download links."""
        from tg_wp_bridge.schemas import TgDocument

        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="",
            document=TgDocument(file_id="doc1", file_name="story.pdf"),
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with (
            patch(
                "tg_wp_bridge.telegram_api.get_file_direct_url", new_callable=AsyncMock
            ) as mock_url,
            patch(
                "tg_wp_bridge.telegram_api.download_file", new_callable=AsyncMock
            ) as mock_download,
            patch(
                "tg_wp_bridge.wordpress_api.upload_media_to_wp",
                new_callable=AsyncMock,
            ) as mock_upload,
            patch(
                "tg_wp_bridge.wordpress_api.create_wp_post",
                new_callable=AsyncMock,
            ) as mock_create,
        ):
            mock_url.return_value = "https://api.telegram.org/file/bottoken/doc.pdf"
            mock_download.return_value = b"pdf"
            mock_upload.return_value = make_wp_media(77, "https://example.com/doc.pdf")

            await handle_telegram_update(update)

            mock_create.assert_called_once()
            html = mock_create.call_args[1]["content_html"]
            assert "Download attachment" in html
            assert "doc.pdf" in html

    @pytest.mark.asyncio
    async def test_handle_update_respects_chat_type_allowlist(self):
        """Chat types listed in allowlist are processed."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="supergroup"),
            text="Hello from group",
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with patch("tg_wp_bridge.app.settings") as mock_settings:
            mock_settings.required_hashtag = None
            mock_settings.chat_type_allowlist = ("channel", "supergroup")
            mock_settings.hashtag_allowlist = None
            mock_settings.hashtag_blocklist = None

            with patch(
                "tg_wp_bridge.wordpress_api.create_wp_post", new_callable=AsyncMock
            ) as mock_create:
                mock_post = MagicMock()
                mock_post.id = 1
                mock_create.return_value = mock_post

                await handle_telegram_update(update)
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_update_skips_blocklisted_hashtag(self):
        """Messages containing a blocked hashtag are ignored."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="News #spam",
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with patch("tg_wp_bridge.app.settings") as mock_settings:
            mock_settings.required_hashtag = None
            mock_settings.chat_type_allowlist = ("channel",)
            mock_settings.hashtag_allowlist = None
            mock_settings.hashtag_blocklist = ("#spam",)

            with patch(
                "tg_wp_bridge.wordpress_api.create_wp_post", new_callable=AsyncMock
            ) as mock_create:
                await handle_telegram_update(update)
                mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_update_requires_allowlisted_hashtag(self):
        """Allowlist requires at least one matching hashtag."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="#news Update",
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with patch("tg_wp_bridge.app.settings") as mock_settings:
            mock_settings.required_hashtag = None
            mock_settings.chat_type_allowlist = ("channel",)
            mock_settings.hashtag_allowlist = ("#news",)
            mock_settings.hashtag_blocklist = None

            with patch(
                "tg_wp_bridge.wordpress_api.create_wp_post", new_callable=AsyncMock
            ) as mock_create:
                mock_post = MagicMock()
                mock_post.id = 55
                mock_create.return_value = mock_post

                await handle_telegram_update(update)
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_update_blocklist_overrides_allowlist(self):
        """Blocklist wins even when allowlist would match."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            text="#news but also #spam",
        )
        update = TelegramUpdate(update_id=123, message=msg)

        with patch("tg_wp_bridge.app.settings") as mock_settings:
            mock_settings.required_hashtag = None
            mock_settings.chat_type_allowlist = ("channel",)
            mock_settings.hashtag_allowlist = ("#news",)
            mock_settings.hashtag_blocklist = ("#spam",)

            with patch(
                "tg_wp_bridge.wordpress_api.create_wp_post", new_callable=AsyncMock
            ) as mock_create:
                await handle_telegram_update(update)
                mock_create.assert_not_called()
