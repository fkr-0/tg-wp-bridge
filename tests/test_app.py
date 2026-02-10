"""
Tests for app.py FastAPI application.
"""

import pytest
from unittest.mock import AsyncMock, patch

from tg_wp_bridge import app
from tg_wp_bridge.app import handle_telegram_update
from tg_wp_bridge.update_model import TelegramUpdate

from tg_wp_bridge.schemas import (
    TgMessage,
    TgChat,
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
        assert response.json() == {"status": "ok", "service": "tg-wp-bridge"}

    def test_validation_endpoint_exists(self):
        """Test validation endpoint returns validation information."""
        from fastapi.testclient import TestClient

        client = TestClient(app.app)
        response = client.get("/validation")
        assert response.status_code == 200
        assert "status" in response.json()
        assert "errors" in response.json()
        assert "details" in response.json()


class TestTelegramWebhook:
    """Test /webhook/{secret} endpoint."""

    def test_webhook_invalid_secret(self, monkeypatch):
        """Test webhook rejects invalid secret."""
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "correct_secret")

        from fastapi.testclient import TestClient

        client = TestClient(app.app)

        update_data = {
            "update_id": 123,
            "message": {"message_id": 1, "chat": {"id": 1, "type": "channel"}, "date": 0},
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
                    "date": 0,
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
                    "date": 0,
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

        msg = TgMessage(
            message_id=1, chat=TgChat(id=1, type="private"), date=0, text="Hello"
        )
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
            date=0,
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
            date=0,
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
    async def test_handle_update_with_required_hashtag(self, temp_settings, tmp_path):
        """Test handling message with required hashtag."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            date=0,
            text="#blog Hello world",
        )
        update = TelegramUpdate(update_id=123, message=msg)

        # Set up temp directories for logs
        storage = tmp_path / "logs"
        mapping_file = tmp_path / "message_map.json"

        # Use temp_settings to set required_hashtag and enable wp_skip to avoid HTTP calls
        with temp_settings(
            required_hashtag="#blog",
            chat_type_allowlist=("channel",),
            wp_skip=True,
            tg_skip=False,
        ):
            # Monkeypatch env vars for storage
            import os

            os.environ["STORAGE_DIR"] = str(storage)
            os.environ["TG_WP_MAPPING_FILE"] = str(mapping_file)

            await handle_telegram_update(update)

        # Verify that a log file was created (handler was called)
        tg_logs = sorted(storage.glob("*_tg_1.json"))
        assert len(tg_logs) == 1

        # Verify the log contains the expected data
        import json

        log_data = json.loads(tg_logs[0].read_text())
        # Check that the handler processed the message
        assert log_data["message"]["text"] == "#blog Hello world"
        assert log_data["kind"] == "message"

    @pytest.mark.asyncio
    async def test_handle_update_skips_blocklisted_hashtag(self):
        """Messages containing a blocked hashtag are ignored."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            date=0,
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
    async def test_handle_update_blocklist_overrides_allowlist(self):
        """Blocklist wins even when allowlist would match."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            date=0,
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
