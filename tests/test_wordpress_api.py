"""
Tests for wordpress_api.py module.
"""

import base64
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from tg_wp_bridge import wordpress_api


class TestWordPressHelpers:
    """Test helper functions."""

    def test_ensure_wp_base_url_success(self, monkeypatch):
        """Test successful base URL retrieval."""
        with patch("tg_wp_bridge.wordpress_api.settings") as mock_settings:
            mock_settings.wp_base_url = "https://wordpress.example.com/"
            result = wordpress_api._ensure_wp_base_url()
            assert result == "https://wordpress.example.com"

    def test_ensure_wp_base_url_trailing_slash(self, monkeypatch):
        """Test base URL without trailing slash."""
        with patch("tg_wp_bridge.wordpress_api.settings") as mock_settings:
            mock_settings.wp_base_url = "https://wordpress.example.com"
            result = wordpress_api._ensure_wp_base_url()
            assert result == "https://wordpress.example.com"

    def test_ensure_wp_base_url_missing(self, monkeypatch):
        """Test RuntimeError when base URL is missing."""
        with patch("tg_wp_bridge.wordpress_api.settings") as mock_settings:
            mock_settings.wp_base_url = None
            with pytest.raises(RuntimeError, match="WP_BASE_URL is not set"):
                wordpress_api._ensure_wp_base_url()

    def test_ensure_wp_auth_missing_username(self, monkeypatch):
        """Test auth check fails without username."""
        with patch("tg_wp_bridge.wordpress_api.settings") as mock_settings:
            mock_settings.wp_username = None
            mock_settings.wp_app_password = "testpass"
            with pytest.raises(
                RuntimeError, match="WP_USERNAME / WP_APP_PASSWORD not set"
            ):
                wordpress_api._ensure_wp_auth()

    def test_ensure_wp_auth_missing_password(self, monkeypatch):
        """Test auth check fails without password."""
        with patch("tg_wp_bridge.wordpress_api.settings") as mock_settings:
            mock_settings.wp_username = "testuser"
            mock_settings.wp_app_password = None
            with pytest.raises(
                RuntimeError, match="WP_USERNAME / WP_APP_PASSWORD not set"
            ):
                wordpress_api._ensure_wp_auth()

    def test_wp_auth_header(self, monkeypatch):
        """Test Basic Auth header generation."""
        with patch("tg_wp_bridge.wordpress_api.settings") as mock_settings:
            mock_settings.wp_username = "testuser"
            mock_settings.wp_app_password = "testpass"

            header = wordpress_api.wp_auth_header()

            expected_token = base64.b64encode(b"testuser:testpass").decode("ascii")
            assert header == {"Authorization": f"Basic {expected_token}"}


class TestUploadMediaToWP:
    """Test upload_media_to_wp function."""

    @pytest.mark.asyncio
    async def test_upload_media_success(self, monkeypatch):
        """Test successful media upload."""
        test_data = b"fake image data"
        mock_response_data = {"id": 123, "source_url": "https://example.com/image.jpg"}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=mock_response_data)

        with (
            patch("tg_wp_bridge.wordpress_api.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_async_client,
        ):
            mock_settings.wp_base_url = "https://wordpress.example.com"
            mock_settings.wp_username = "testuser"
            mock_settings.wp_app_password = "testpass"

            mock_client = AsyncMock()
            mock_async_client.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await wordpress_api.upload_media_to_wp(
                filename="test.jpg", content_type="image/jpeg", data=test_data
            )

            assert result is not None
            assert result.id == 123
            assert str(result.source_url) == "https://example.com/image.jpg"

            # Check call arguments
            call_args = mock_client.post.call_args
            assert "wp-json/wp/v2/media" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_upload_media_error(self, monkeypatch):
        """Test media upload error handling."""
        test_data = b"fake image data"

        with (
            patch("tg_wp_bridge.wordpress_api.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_async_client,
        ):
            mock_settings.wp_base_url = "https://wordpress.example.com"
            mock_settings.wp_username = "testuser"
            mock_settings.wp_app_password = "testpass"

            mock_client = AsyncMock()
            mock_async_client.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Bad Request", request=MagicMock(), response=MagicMock()
            )

            result = await wordpress_api.upload_media_to_wp(
                filename="test.jpg", content_type="image/jpeg", data=test_data
            )

            assert result is None


class TestCreateWPPost:
    """Test create_wp_post function."""

    @pytest.mark.asyncio
    async def test_create_post_success(self, monkeypatch):
        """Test successful post creation."""
        mock_response_data = {
            "id": 456,
            "link": "https://example.com/post/456",
            "title": {"rendered": "Test Post"},
            "content": {"rendered": "<p>Test content</p>"},
        }

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=mock_response_data)

        with (
            patch("tg_wp_bridge.wordpress_api.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_async_client,
        ):
            mock_settings.wp_base_url = "https://wordpress.example.com"
            mock_settings.wp_username = "testuser"
            mock_settings.wp_app_password = "testpass"
            mock_settings.wp_publish_status = "publish"
            mock_settings.wp_category_id = 5

            mock_client = AsyncMock()
            mock_async_client.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await wordpress_api.create_wp_post(
                title="Test Post", content_html="<p>Test content</p>", media_ids=[123]
            )

            assert result.id == 456
            assert str(result.link) == "https://example.com/post/456"

            # Check call arguments
            call_args = mock_client.post.call_args
            assert "wp-json/wp/v2/posts" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_post_minimal(self, monkeypatch):
        """Test post creation with minimal parameters."""
        mock_response_data = {
            "id": 789,
            "title": {"rendered": "Minimal Post"},
            "content": {"rendered": "<p>Minimal content</p>"},
        }

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = mock_response_data

        with (
            patch("tg_wp_bridge.wordpress_api.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_async_client,
        ):
            mock_settings.wp_base_url = "https://wordpress.example.com"
            mock_settings.wp_username = "testuser"
            mock_settings.wp_app_password = "testpass"
            mock_settings.wp_publish_status = "publish"
            mock_settings.wp_category_id = 0  # No category

            mock_client = AsyncMock()
            mock_async_client.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await wordpress_api.create_wp_post(
                title="Minimal Post", content_html="<p>Minimal content</p>"
            )

            assert result.id == 789

            # Check call arguments for defaults
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["status"] == "publish"  # default
            assert "categories" not in payload  # not set when WP_CATEGORY_ID is 0
            assert "featured_media" not in payload  # not set when no media_ids

    @pytest.mark.asyncio
    async def test_create_post_http_error(self, monkeypatch):
        """Test post creation with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with (
            patch("tg_wp_bridge.wordpress_api.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_async_client,
        ):
            mock_settings.wp_base_url = "https://wordpress.example.com"
            mock_settings.wp_username = "testuser"
            mock_settings.wp_app_password = "testpass"

            mock_client = AsyncMock()
            mock_async_client.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Bad Request", request=MagicMock(), response=mock_response
            )

            with pytest.raises(httpx.HTTPStatusError):
                await wordpress_api.create_wp_post(
                    title="Test Post", content_html="<p>Test</p>"
                )

    @pytest.mark.asyncio
    async def test_create_post_missing_config(self, monkeypatch):
        """Test post creation fails without proper config."""
        with patch("tg_wp_bridge.wordpress_api.settings") as mock_settings:
            mock_settings.wp_base_url = None

            with pytest.raises(RuntimeError, match="WP_BASE_URL is not set"):
                await wordpress_api.create_wp_post(
                    title="Test Post", content_html="<p>Test</p>"
                )


class TestWordPressDiagnostics:
    """Test WordPress diagnostic helpers."""

    @pytest.mark.asyncio
    async def test_ping_wp_api_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"name": "Site"}

        with (
            patch("tg_wp_bridge.wordpress_api.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.wp_base_url = "https://wordpress.example.com"
            client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = client
            client.get.return_value = mock_response

            result = await wordpress_api.ping_wp_api()
            assert result["name"] == "Site"

    @pytest.mark.asyncio
    async def test_check_wp_credentials_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": 42, "name": "Admin"}

        with (
            patch("tg_wp_bridge.wordpress_api.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_settings.wp_base_url = "https://wordpress.example.com"
            mock_settings.wp_username = "admin"
            mock_settings.wp_app_password = "pass"

            client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = client
            client.get.return_value = mock_response

            result = await wordpress_api.check_wp_credentials()
            assert result["id"] == 42
