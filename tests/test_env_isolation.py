"""
Test environment isolation is working.
"""

from tg_wp_bridge.config import Settings


def test_clean_environment_fixture_works(pure_defaults_only):
    """Test that our fixture properly isolates environment."""
    # This should use defaults since env is clean
    settings = Settings()

    # Check that defaults are used (not values from .env)
    assert settings.wp_category_id == 0  # default, not 1 from .env
    assert settings.telegram_bot_token is None  # default, not from .env
    assert settings.wp_base_url is None  # default, not from .env
