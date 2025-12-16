"""
Tests for telegram_api module.
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from tg_wp_bridge import telegram_api
from tg_wp_bridge.schemas import TelegramWebhookInfo


class TestEnsureBotToken:
    """Test _ensure_bot_token function."""

    def test_ensure_bot_token_success(self):
        """Test successful token retrieval."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            assert telegram_api._ensure_bot_token() == "test_token"

    def test_ensure_bot_token_missing(self):
        """Test RuntimeError when token is missing."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = None
            with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN is not set"):
                telegram_api._ensure_bot_token()

    def test_bot_url_construction(self):
        """Test _bot_url constructs correct URL."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_api_base = "https://api.telegram.org"
            result = telegram_api._bot_url("getFile")
            expected = "https://api.telegram.org/bottest_token/getFile"
            assert result == expected


class TestGetFileDirectUrl:
    """Test get_file_direct_url function."""

    @pytest.mark.asyncio
    async def test_get_file_direct_url_success(self, safe_httpx_client):
        """Test successful file URL retrieval."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_api_base = "https://api.telegram.org"

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "ok": True,
                "result": {"file_path": "photos/file_123.jpg"},
            }

            safe_httpx_client.get.return_value = mock_response

            # CRITICAL: Mock httpx.AsyncClient to prevent real API calls
            with patch("httpx.AsyncClient", return_value=safe_httpx_client):
                result = await telegram_api.get_file_direct_url("file_123")

            expected = "https://api.telegram.org/file/bottest_token/photos/file_123.jpg"
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_file_direct_url_api_error(self, safe_httpx_client):
        """Test API returns ok=False."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_api_base = "https://api.telegram.org"

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "ok": False,
                "description": "File not found",
            }

            safe_httpx_client.get.return_value = mock_response

            # CRITICAL: Mock httpx.AsyncClient to prevent real API calls
            with patch("httpx.AsyncClient", return_value=safe_httpx_client):
                result = await telegram_api.get_file_direct_url("invalid_file")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_file_direct_url_http_error(self, safe_httpx_client):
        """Test HTTP error during request."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_api_base = "https://api.telegram.org"

            safe_httpx_client.get.side_effect = httpx.HTTPStatusError(
                "404 Not Found", request=MagicMock(), response=MagicMock()
            )

            # CRITICAL: Mock httpx.AsyncClient to prevent real API calls
            with patch("httpx.AsyncClient", return_value=safe_httpx_client):
                # HTTP errors should be raised, not return None
                with pytest.raises(httpx.HTTPStatusError):
                    await telegram_api.get_file_direct_url("file_123")


class TestDownloadFile:
    """Test download_file function."""

    @pytest.mark.asyncio
    async def test_download_file_success(self, safe_httpx_client):
        """Test successful file download."""
        test_content = b"test image data"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.content = test_content

        safe_httpx_client.get.return_value = mock_response

        # CRITICAL: Mock httpx.AsyncClient to prevent real API calls
        with patch("httpx.AsyncClient", return_value=safe_httpx_client):
            result = await telegram_api.download_file("https://example.com/file.jpg")
        assert result == test_content

    @pytest.mark.asyncio
    async def test_download_file_http_error(self, safe_httpx_client):
        """Test HTTP error during download."""
        safe_httpx_client.get.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )

        # CRITICAL: Mock httpx.AsyncClient to prevent real API calls
        with patch("httpx.AsyncClient", return_value=safe_httpx_client):
            with pytest.raises(httpx.HTTPStatusError):
                await telegram_api.download_file("https://example.com/invalid.jpg")


class TestSetWebhook:
    """Test set_webhook function."""

    @pytest.mark.asyncio
    async def test_set_webhook_success(self, safe_httpx_client):
        """Test successful webhook setup."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.public_base_url = "https://example.com"
            mock_settings.telegram_webhook_secret = "webhook_secret"
            mock_settings.telegram_api_base = "https://api.telegram.org"

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "ok": True,
                "result": True,
                "description": "Webhook was set",
            }

            safe_httpx_client.post.return_value = mock_response

            # CRITICAL: Mock httpx.AsyncClient to prevent real API calls
            with patch("httpx.AsyncClient", return_value=safe_httpx_client):
                result = await telegram_api.set_webhook()

            assert result["ok"] is True
            safe_httpx_client.post.assert_called_once()

            # Check the call arguments
            call_args = safe_httpx_client.post.call_args
            assert "setWebhook" in call_args[0][0]
            assert (
                call_args[1]["data"]["url"]
                == "https://example.com/webhook/webhook_secret"
            )

    @pytest.mark.asyncio
    async def test_set_webhook_missing_token(self):
        """Test webhook setup fails without token."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = None
            with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN is not set"):
                await telegram_api.set_webhook()

    @pytest.mark.asyncio
    async def test_set_webhook_missing_base_url(self):
        """Test webhook setup fails without base URL."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.public_base_url = None
            with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL is not set"):
                await telegram_api.set_webhook()

    @pytest.mark.asyncio
    async def test_set_webhook_missing_secret(self):
        """Test webhook setup fails without secret."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.public_base_url = "https://example.com"
            mock_settings.telegram_webhook_secret = None
            with pytest.raises(
                RuntimeError, match="TELEGRAM_WEBHOOK_SECRET is not set"
            ):
                await telegram_api.set_webhook()


class TestGetWebhookInfo:
    """Test get_webhook_info function."""

    @pytest.mark.asyncio
    async def test_get_webhook_info_success(self, safe_httpx_client):
        """Test successful webhook info retrieval."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_api_base = "https://api.telegram.org"

            mock_response_data = {
                "ok": True,
                "result": {
                    "url": "https://example.com/webhook/secret",
                    "has_custom_certificate": False,
                    "pending_update_count": 0,
                    "is_running": True,
                },
            }

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = mock_response_data

            safe_httpx_client.get.return_value = mock_response

            # CRITICAL: Mock httpx.AsyncClient to prevent real API calls
            with patch("httpx.AsyncClient", return_value=safe_httpx_client):
                result = await telegram_api.get_webhook_info()

            expected_info = TelegramWebhookInfo(
                url="https://example.com/webhook/secret",
                has_custom_certificate=False,
                pending_update_count=0,
                is_running=True,
            )
            assert result == expected_info

    @pytest.mark.asyncio
    async def test_get_webhook_info_missing_token(self):
        """Test webhook info fails without token."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = None
            with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN is not set"):
                await telegram_api.get_webhook_info()

    @pytest.mark.asyncio
    async def test_get_webhook_info_telegram_error(self, safe_httpx_client):
        """Test API error response surfaces as RuntimeError."""
        with patch("tg_wp_bridge.telegram_api.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_api_base = "https://api.telegram.org"

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "ok": False,
                "description": "Unauthorized",
            }

            safe_httpx_client.get.return_value = mock_response

            with patch("httpx.AsyncClient", return_value=safe_httpx_client):
                with pytest.raises(RuntimeError, match="Unauthorized"):
                    await telegram_api.get_webhook_info()
