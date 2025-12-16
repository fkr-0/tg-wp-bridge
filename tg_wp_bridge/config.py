"""
Configuration management using pydantic-settings.

- Loads from environment variables.
- Also loads from a `.env` file in the current working directory (see env.example).
"""

from typing import Optional, Tuple

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, EnvSettingsSource


class LenientEnvSettingsSource(EnvSettingsSource):
    """Env source that falls back to raw strings for complex values."""

    def decode_complex_value(self, field_name, field, value):  # type: ignore[override]
        try:
            return super().decode_complex_value(field_name, field, value)
        except ValueError:
            return value


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

    telegram_api_base: str = Field(
        default="https://api.telegram.org", alias="TELEGRAM_API_BASE"
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
    chat_type_allowlist: Tuple[str, ...] = Field(
        default=("channel",),
        alias="CHAT_TYPE_ALLOWLIST",
        description="Comma-separated chat types to allow (channel,supergroup,group,private).",
    )
    hashtag_allowlist: Optional[Tuple[str, ...]] = Field(
        default=None,
        alias="HASHTAG_ALLOWLIST",
        description="Comma-separated hashtags that must appear (any match).",
    )
    hashtag_blocklist: Optional[Tuple[str, ...]] = Field(
        default=None,
        alias="HASHTAG_BLOCKLIST",
        description="Comma-separated hashtags that will cause messages to be skipped.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            LenientEnvSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    @staticmethod
    def _parse_list_field(value, *, default):
        if value is None:
            return default
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            return tuple(items) if items else default
        if isinstance(value, (list, tuple, set)):
            items = [str(item).strip() for item in value if str(item).strip()]
            return tuple(items) if items else default
        return value

    @field_validator("chat_type_allowlist", mode="before")
    @classmethod
    def _parse_chat_type_allowlist(cls, value):
        parsed = cls._parse_list_field(value, default=("channel",))
        return parsed if parsed is not None else ()

    @field_validator("hashtag_allowlist", "hashtag_blocklist", mode="before")
    @classmethod
    def _parse_hashtag_lists(cls, value):
        return cls._parse_list_field(value, default=None)


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
