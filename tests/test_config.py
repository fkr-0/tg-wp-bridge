# == tests/test_config.py (extended) ==
from tg_wp_bridge.config import Settings


def test_settings_defaults_ok():
    """
    Ensure Settings can be instantiated with no env and has sane defaults.
    """
    s = Settings()  # uses env / .env; here we rely only on defaults
    assert s.wp_category_id == 0
    assert s.wp_publish_status == "publish"
    # Telegram/WordPress tokens may be None by default, that is fine.
    assert getattr(s, "telegram_bot_token", None) is None
    # REQUIRED_HASHTAG should default to None
    assert s.required_hashtag is None


def test_settings_env_aliases(monkeypatch):
    """
    Ensure environment aliases are wired correctly.
    """
    monkeypatch.setenv("WP_BASE_URL", "https://example.com")
    monkeypatch.setenv("WP_USERNAME", "user")
    monkeypatch.setenv("WP_APP_PASSWORD", "pass")
    monkeypatch.setenv("WP_CATEGORY_ID", "5")
    monkeypatch.setenv("WP_PUBLISH_STATUS", "draft")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://bridge.example.com")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("REQUIRED_HASHTAG", "#blog")

    s = Settings()  # reloads from env
    assert str(s.wp_base_url) == "https://example.com/"
    assert s.wp_username == "user"
    assert s.wp_app_password == "pass"
    assert s.wp_category_id == 5
    assert s.wp_publish_status == "draft"
    assert s.telegram_bot_token == "123:abc"
    assert str(s.public_base_url) == "https://bridge.example.com/"
    assert s.telegram_webhook_secret == "secret"
    assert s.required_hashtag == "#blog"


def test_settings_loads_from_dotenv(tmp_path, monkeypatch):
    """
    Ensure .env file is honored by pydantic-settings.

    We simulate a clean environment and a temporary working directory
    with a .env file, then instantiate Settings.
    """
    # Ensure no conflicting env vars
    for key in [
        "WP_BASE_URL",
        "WP_CATEGORY_ID",
        "WP_PUBLISH_STATUS",
        "REQUIRED_HASHTAG",
    ]:
        monkeypatch.delenv(key, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        'WP_BASE_URL="https://dot-env.example"\n'
        "WP_CATEGORY_ID=3\n"
        'WP_PUBLISH_STATUS="pending"\n'
        'REQUIRED_HASHTAG="#dotenv"\n'
    )

    # Change working directory so Settings(env_file=".env") finds our file
    monkeypatch.chdir(tmp_path)

    s = Settings()
    assert str(s.wp_base_url) == "https://dot-env.example/"
    assert s.wp_category_id == 3
    assert s.wp_publish_status == "pending"
    assert s.required_hashtag == "#dotenv"


# == end/tests/test_config.py ==
