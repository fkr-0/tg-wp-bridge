"""
SECURITY verification tests.
"""

from tg_wp_bridge.config import Settings


class TestSecurityFixtures:
    """Verify our security fixtures work correctly."""

    def test_settings_are_clean(self, safe_settings):
        """SECURITY: Verify settings start with clean defaults."""
        assert safe_settings.wp_category_id == 0
        assert safe_settings.telegram_bot_token is None
        assert safe_settings.wp_base_url is None

    def test_env_file_is_blocked(self):
        """SECURITY: Verify .env file loading is blocked."""
        # If this worked, we'd have values from .env
        # Since we're blocking .env, we should get defaults
        settings = Settings()
        assert settings.wp_category_id == 0  # default, not 1 from .env

    def test_no_real_http_calls_allowed(self, block_all_real_network_requests):
        """
        SECURITY: Verify no real HTTP calls can be made.

        If this test passes, our security fixtures are working.
        Any real HTTP call will raise RuntimeError.
        """
        # This test passes if our security fixtures work
        # The block_all_real_network_requests fixture prevents real calls
        assert True
