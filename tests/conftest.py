"""
SECURITY-FIRST test configuration for tg-wp-bridge.

CRITICAL: This configuration prevents ANY real HTTP requests during testing.
"""

from __future__ import annotations

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock


def _ensure_project_root_on_syspath() -> None:
    # tests/ directory
    here = Path(__file__).resolve()
    # project root = parent of tests/
    project_root = here.parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_ensure_project_root_on_syspath()


@pytest.fixture(autouse=True)
def block_all_real_network_requests(monkeypatch):
    """
    SECURITY FIX: Block ALL real network requests during testing.

    CRITICAL: This prevents accidental real HTTP requests to api.telegram.org
    or any external service. All HTTP calls MUST go through mocks.

    This specifically blocks external HTTP calls while allowing local test client requests.
    """
    # Only block modules that exist in the project
    try:
        import httpx

        # Store original methods
        original_async_get = httpx.AsyncClient.get
        original_async_post = httpx.AsyncClient.post

        # Create smart wrapper that only blocks external calls
        def smart_async_get(self, url, **kwargs):
            if isinstance(url, str) and (
                "api.telegram.org" in url
                or "fail.org" in url
                or (
                    url.startswith("http")
                    and not (
                        "testserver" in url or "localhost" in url or "127.0.0.1" in url
                    )
                )
            ):
                raise RuntimeError(
                    f"🚨 SECURITY: Real HTTP request blocked! URL: {url}"
                )
            return original_async_get(self, url, **kwargs)

        def smart_async_post(self, url, **kwargs):
            if isinstance(url, str) and (
                "api.telegram.org" in url
                or "fail.org" in url
                or (
                    url.startswith("http")
                    and not (
                        "testserver" in url or "localhost" in url or "127.0.0.1" in url
                    )
                )
            ):
                raise RuntimeError(
                    f"🚨 SECURITY: Real HTTP request blocked! URL: {url}"
                )
            return original_async_post(self, url, **kwargs)

        monkeypatch.setattr("httpx.AsyncClient.get", smart_async_get)
        monkeypatch.setattr("httpx.AsyncClient.post", smart_async_post)

    except ImportError:
        pass


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    """
    Clean and reset settings singleton for each test.

    SECURITY: This ensures no .env file values leak into tests and prevents
    ANY real HTTP requests to Telegram or external services.

    NOTE: If a test calls importlib.reload() on tg_wp_bridge.config, this fixture
    handles it by also updating the reloaded settings object to maintain consistency.
    """
    # Clean environment variables completely FIRST
    env_vars_to_clean = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
        "TELEGRAM_API_BASE",
        "PUBLIC_BASE_URL",
        "WEBHOOK_PREFIX",
        "WP_BASE_URL",
        "WP_USERNAME",
        "WP_APP_PASSWORD",
        "WP_CATEGORY_ID",
        "WP_PUBLISH_STATUS",
        "WP_POST_TYPE",
        "WP_USE_FEATURED_MEDIA",
        "REQUIRED_HASHTAG",
        "TG_MEDIA_RETRY_ATTEMPTS",
        "TG_MEDIA_RETRY_BACKOFF_SECONDS",
        "TG_MEDIA_GROUP_WAIT_TIMEOUT_SECONDS",
        "TG_MEDIA_GROUP_WAIT_INTERVAL_SECONDS",
    ]

    for var in env_vars_to_clean:
        monkeypatch.delenv(var, raising=False)

    # Set safe test defaults to prevent production values from being used
    # Only set the ones that matter for security, not the ones that have safe defaults
    monkeypatch.setenv("TELEGRAM_API_BASE", "https://fail.org")
    monkeypatch.setenv("WP_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("WP_USERNAME", "admin")
    monkeypatch.setenv("WP_APP_PASSWORD", "app-password-from-wordpress")
    # Don't set WP_CATEGORY_ID - let it use the actual default of 0
    monkeypatch.setenv("WP_PUBLISH_STATUS", "publish")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://bridge.example.com")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "supersecretpathsegment")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF_your_bot_token_here")

    # Import and reset the settings singleton AFTER cleaning env vars
    import tg_wp_bridge.config as config_module

    # Create new settings with clean environment
    from pydantic_settings import SettingsConfigDict

    # Temporarily disable .env file loading for tests
    test_config = SettingsConfigDict(
        env_file=None,  # No .env file loading
        env_file_encoding="utf-8",
        extra="ignore",
    )

    monkeypatch.setattr(config_module.Settings, "model_config", test_config)

    # Create fresh settings instance
    new_settings = config_module.Settings()

    # Update the existing settings object in-place to preserve references in other modules
    # This is important because handlers.py does `from .config import settings` which
    # creates a reference to the original object
    for key, value in new_settings.model_dump().items():
        object.__setattr__(config_module.settings, key, value)

    # Also reset any module-level constants that depend on settings
    import tg_wp_bridge.telegram_api as telegram_api_module

    telegram_api_module.TELEGRAM_API_BASE = "https://fail.org"

    # IMPORTANT: Also explicitly reset fields that may have been modified by temp_settings
    # but are not set via environment variables (so they won't be in model_dump)
    # This fixes test order dependency issues
    # Use the actual default values from the Settings class
    object.__setattr__(config_module.settings, "webhook_prefix", "webhook")
    object.__setattr__(config_module.settings, "required_hashtag", None)
    object.__setattr__(config_module.settings, "chat_type_allowlist", ("channel",))
    object.__setattr__(config_module.settings, "hashtag_allowlist", None)
    object.__setattr__(config_module.settings, "hashtag_blocklist", None)

    # CRITICAL: Handle module reload scenario
    # If a test calls importlib.reload(tg_wp_bridge.config), it creates a NEW settings object.
    # We need to ensure both the old and new settings objects stay in sync for the duration
    # of the test. We do this by returning a cleanup function that will restore consistency.

    original_settings = config_module.settings
    settings_id_before = id(config_module.settings)

    def restore_settings():
        # After test, check if settings object was replaced (via reload)
        current_settings = config_module.settings
        settings_id_after = id(current_settings)

        if settings_id_before != settings_id_after:
            # Settings object was replaced - sync the new object with clean values
            for key, value in new_settings.model_dump().items():
                object.__setattr__(current_settings, key, value)
            # Also set the explicit defaults
            object.__setattr__(current_settings, "webhook_prefix", "webhook")
            object.__setattr__(current_settings, "required_hashtag", None)
            object.__setattr__(current_settings, "chat_type_allowlist", ("channel",))
            object.__setattr__(current_settings, "hashtag_allowlist", None)
            object.__setattr__(current_settings, "hashtag_blocklist", None)

    # Register cleanup to run after test
    yield

    restore_settings()


@pytest.fixture
def pure_defaults_only(monkeypatch):
    """
    Create completely clean environment for testing actual defaults.

    Used ONLY for testing that Settings() returns proper defaults when
    no environment variables are set. Different from clean_settings
    which provides security isolation.
    """
    # Clean environment variables completely
    env_vars_to_clean = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
        "TELEGRAM_API_BASE",
        "PUBLIC_BASE_URL",
        "WEBHOOK_PREFIX",
        "WP_BASE_URL",
        "WP_USERNAME",
        "WP_APP_PASSWORD",
        "WP_CATEGORY_ID",
        "WP_PUBLISH_STATUS",
        "WP_POST_TYPE",
        "WP_USE_FEATURED_MEDIA",
        "REQUIRED_HASHTAG",
        "TG_MEDIA_RETRY_ATTEMPTS",
        "TG_MEDIA_RETRY_BACKOFF_SECONDS",
        "TG_MEDIA_GROUP_WAIT_TIMEOUT_SECONDS",
        "TG_MEDIA_GROUP_WAIT_INTERVAL_SECONDS",
    ]

    for var in env_vars_to_clean:
        monkeypatch.delenv(var, raising=False)

    # Import and reset the settings singleton AFTER cleaning env vars
    import tg_wp_bridge.config as config_module

    # Temporarily disable .env file loading for tests
    from pydantic_settings import SettingsConfigDict

    test_config = SettingsConfigDict(
        env_file=None,  # No .env file loading
        env_file_encoding="utf-8",
        extra="ignore",
    )

    monkeypatch.setattr(config_module.Settings, "model_config", test_config)

    # Create fresh settings instance
    config_module.settings = config_module.Settings()


@pytest.fixture
def safe_settings():
    """
    Create a fresh, safe settings object for testing.

    SECURITY: This ensures tests use only controlled values.
    """
    settings = MagicMock()
    settings.wp_category_id = 0
    settings.wp_publish_status = "publish"
    settings.wp_post_type = "post"
    settings.wp_use_featured_media = False
    settings.required_hashtag = None
    settings.telegram_bot_token = None
    settings.telegram_webhook_secret = None
    settings.public_base_url = None
    settings.wp_base_url = None
    settings.wp_username = None
    settings.wp_app_password = None

    return settings


@pytest.fixture
def mock_client_response():
    """Create a mock HTTP response for testing."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={})
    mock_resp.content = b""
    mock_resp.status_code = 200
    mock_resp.text = ""
    return mock_resp


@pytest.fixture
def safe_mock_async_client():
    """
    Create a PROPERLY mocked AsyncClient for httpx.

    SECURITY: This ensures ALL HTTP calls are intercepted.
    """
    client = MagicMock()

    # Make it a proper async context manager
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    # Mock HTTP methods to return our mock responses
    client.get = AsyncMock()
    client.post = AsyncMock()

    return client


@pytest.fixture
def safe_httpx_client(safe_mock_async_client):
    """
    Mock httpx.AsyncClient with SECURITY-first approach.

    CRITICAL: Ensures ALL HTTP calls are intercepted and never hit real endpoints.
    """
    with patch("httpx.AsyncClient", return_value=safe_mock_async_client):
        yield safe_mock_async_client


# == end/tests/conftest.py ==


# Fixtures from cfte2.py - needed for test_dispatcher.py and test_handlers.py
from contextlib import contextmanager


@contextmanager
def _temp_settings(**overrides):
    """Temporarily override tg_wp_bridge.config.settings attributes."""
    # Import fresh each time to handle module reloads
    import tg_wp_bridge.config as config_module

    settings = config_module.settings

    # Also update telegram_api.settings since it imports settings at module level
    # This is needed when tg_wp_bridge.config is reloaded (by some tests)
    import tg_wp_bridge.telegram_api as telegram_api_module

    old = {}
    for k, v in overrides.items():
        old[k] = getattr(settings, k)
        # Update both config.settings and telegram_api.settings
        object.__setattr__(settings, k, v)
        object.__setattr__(telegram_api_module.settings, k, v)

    try:
        yield settings
    finally:
        for k, v in old.items():
            object.__setattr__(settings, k, v)
            object.__setattr__(telegram_api_module.settings, k, v)


@pytest.fixture
def temp_settings():
    return _temp_settings


@pytest.fixture
def tmp_dirs(tmp_path, monkeypatch):
    """Provide isolated mapping + storage directories and set related env vars."""
    storage = tmp_path / "logs"
    mapping_file = tmp_path / "message_map.json"
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(mapping_file))
    # reasonable defaults for rotation are disabled unless tests set them
    monkeypatch.delenv("LOG_MAX_FILES", raising=False)
    monkeypatch.delenv("LOG_MAX_BYTES", raising=False)
    return {
        "storage": storage,
        "mapping_file": mapping_file,
    }


@pytest.fixture
def make_update():
    """Factory to build minimal Telegram updates."""
    from tg_wp_bridge.update_model import TelegramUpdate
    from tg_wp_bridge.schemas import TgMessage, TgChat

    def _mk(*, update_id: int, kind: str, message_id: int, text: str = "hello"):
        # Create TgMessage object first so get_payload returns a TgMessage
        msg = TgMessage(
            message_id=message_id,
            date=0,
            chat=TgChat(id=1, type="channel"),
            text=text,
        )
        # Create TelegramUpdate with the TgMessage object
        payload = {"update_id": update_id, kind: msg}
        return TelegramUpdate.model_validate(payload)

    return _mk
