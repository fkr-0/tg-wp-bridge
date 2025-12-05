"""
Configuration management using pydantic-settings.

- Loads from environment variables.
- Also loads from a `.env` file in the current working directory (see env.example).
"""

from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: Optional[str] = Field(
        default=None,
        alias="TELEGRAM_BOT_TOKEN",
        description="Telegram Bot API token from BotFather",
    )
    telegram_webhook_secret: Optional[str] = Field(
        default=None,
        alias="TELEGRAM_WEBHOOK_SECRET",
        description="Path-level shared secret for webhook URL",
    )
    public_base_url: Optional[AnyHttpUrl] = Field(
        default=None,
        alias="PUBLIC_BASE_URL",
        description="Public base URL where this service is reachable (for setWebhook)",
    )

    # WordPress
    wp_base_url: Optional[AnyHttpUrl] = Field(
        default=None,
        alias="WP_BASE_URL",
        description="Base URL of the WordPress site, e.g. https://example.com",
    )
    wp_username: Optional[str] = Field(
        default=None,
        alias="WP_USERNAME",
        description="WordPress username for Application Password auth",
    )
    wp_app_password: Optional[str] = Field(
        default=None,
        alias="WP_APP_PASSWORD",
        description="WordPress Application Password",
    )
    wp_category_id: int = Field(
        default=0,
        alias="WP_CATEGORY_ID",
        description="Numeric category ID to assign mirrored posts to",
    )
    wp_publish_status: str = Field(
        default="publish",
        alias="WP_PUBLISH_STATUS",
        description="Default status for new posts (publish|draft|pending)",
    )

    # Optional filtering: only mirror messages that contain this hashtag.
    # Example: "#blog". Leave unset (None) to mirror all channel messages.
    required_hashtag: Optional[str] = Field(
        default=None,
        alias="REQUIRED_HASHTAG",
        description="If set, only mirror messages that contain this hashtag (including #).",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
"""
Singleton settings object used across modules.

Usage:
    from .config import settings
    settings.telegram_bot_token
    settings.wp_base_url
    settings.required_hashtag
"""
# == end/tg_wp_bridge/config.py ==
