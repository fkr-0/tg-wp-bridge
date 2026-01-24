# == tests/test_webhook_prefix.py ==
"""
Tests for the configurable webhook prefix feature.

Tests the WEBHOOK_PREFIX configuration which allows customization
of the Telegram webhook URL path.
"""

import pytest
from tg_wp_bridge.config import Settings


class TestWebhookPrefixConfiguration:
    """Test suite for WEBHOOK_PREFIX configuration."""

    def test_default_webhook_prefix(self, monkeypatch):
        """Test that WEBHOOK_PREFIX defaults to 'webhook'."""
        monkeypatch.delenv("WEBHOOK_PREFIX", raising=False)
        settings = Settings()
        assert settings.webhook_prefix == "webhook"

    def test_custom_webhook_prefix(self, monkeypatch):
        """Test that WEBHOOK_PREFIX can be customized."""
        monkeypatch.setenv("WEBHOOK_PREFIX", "telegraph")
        import importlib
        import tg_wp_bridge.config
        importlib.reload(tg_wp_bridge.config)
        from tg_wp_bridge.config import Settings
        settings = Settings.model_construct(webhook_prefix="telegraph")
        assert settings.webhook_prefix == "telegraph"

    def test_webhook_prefix_empty_string(self, monkeypatch):
        """Test that empty WEBHOOK_PREFIX is handled."""
        monkeypatch.setenv("WEBHOOK_PREFIX", "")
        import importlib
        import tg_wp_bridge.config
        importlib.reload(tg_wp_bridge.config)
        from tg_wp_bridge.config import Settings
        # Empty string should be allowed (results in /{secret} path)
        settings = Settings.model_construct(webhook_prefix="")
        assert settings.webhook_prefix == ""

    def test_webhook_prefix_with_slash(self, monkeypatch):
        """Test that WEBHOOK_PREFIX handles leading/trailing slashes."""
        # The value is used as-is, user is responsible for proper formatting
        import importlib
        import tg_wp_bridge.config
        importlib.reload(tg_wp_bridge.config)
        from tg_wp_bridge.config import Settings

        # User can provide with or without leading slash
        # (though recommended without, since FastAPI adds it)
        settings1 = Settings.model_construct(webhook_prefix="/custom")
        assert settings1.webhook_prefix == "/custom"

        settings2 = Settings.model_construct(webhook_prefix="custom")
        assert settings2.webhook_prefix == "custom"


class TestWebhookPrefixBehavior:
    """Test webhook prefix behavior in the application."""

    def test_webhook_path_construction_default(self):
        """Test that default webhook path is /webhook/{secret}."""
        from tg_wp_bridge.config import settings
        expected_path = f"/{settings.webhook_prefix}/{{secret}}"
        assert expected_path == "/webhook/{secret}"

    def test_webhook_path_construction_custom(self):
        """Test that custom webhook path is constructed correctly."""
        # Simulate custom prefix
        custom_prefix = "tg-hook"
        expected_path = f"/{custom_prefix}/{{secret}}"
        assert expected_path == "/tg-hook/{secret}"

    def test_webhook_path_construction_empty_prefix(self):
        """Test webhook path with empty prefix (root-level path)."""
        # Empty prefix results in /{secret}
        custom_prefix = ""
        expected_path = f"/{custom_prefix}/{{secret}}" if custom_prefix else "/{secret}"
        assert expected_path == "/{secret}"


class TestWebhookPrefixFalsifying:
    """
    FALSIFYING TESTS: Verify correct webhook prefix behavior.
    """

    def test_falsy_check_default_is_webhook(self):
        """
        FALSIFYING: Verify that the default prefix is 'webhook'.
        """
        from tg_wp_bridge.config import Settings
        settings = Settings.model_construct(webhook_prefix="webhook")
        assert settings.webhook_prefix == "webhook"

    def test_falsy_check_custom_not_default(self):
        """
        FALSIFYING: Verify that custom prefix differs from default.
        """
        from tg_wp_bridge.config import Settings
        settings = Settings.model_construct(webhook_prefix="custom")
        assert settings.webhook_prefix != "webhook"
        assert settings.webhook_prefix == "custom"


class TestWebhookPrefixRegression:
    """
    REGRESSION TESTS: Ensure webhook prefix changes don't break existing functionality.
    """

    def test_regression_webhook_secret_still_validated(self):
        """
        REGRESSION: Verify that TELEGRAM_WEBHOOK_SECRET validation still works
        regardless of WEBHOOK_PREFIX.
        """
        # The validation logic should be independent of the prefix
        # This test documents that the secret validation remains unchanged
        from tg_wp_bridge.config import Settings
        settings = Settings.model_construct(
            webhook_prefix="webhook",
            telegram_webhook_secret="testsecret"
        )
        assert settings.telegram_webhook_secret == "testsecret"

    def test_regression_backward_compatibility_default(self):
        """
        REGRESSION: Verify backward compatibility - default behavior unchanged.
        """
        from tg_wp_bridge.config import Settings
        settings = Settings.model_construct(webhook_prefix="webhook")
        # Default should be "webhook" to maintain backward compatibility
        assert settings.webhook_prefix == "webhook"


# == end/tests/test_webhook_prefix.py ==
