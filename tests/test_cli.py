"""Tests for CLI commands."""

from types import SimpleNamespace
from click.testing import CliRunner
from unittest.mock import AsyncMock, patch

from tg_wp_bridge.cli import cli
from tg_wp_bridge.schemas import TelegramWebhookInfo


def make_settings(**overrides):
    defaults = dict(
        telegram_bot_token="123:abc",
        public_base_url="https://example.com",
        telegram_webhook_secret="secret",
        required_hashtag=None,
        wp_base_url="https://wordpress.example.com",
        wp_username="writer",
        wp_app_password="pass",
        wp_category_id=1,
        wp_publish_status="publish",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_webhook_info_table_output(monkeypatch):
    runner = CliRunner()
    info = TelegramWebhookInfo(
        url="https://example.com/webhook",
        has_custom_certificate=False,
        pending_update_count=2,
        last_error_message=None,
        ip_address=None,
    )

    with patch("tg_wp_bridge.cli.get_webhook_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = info
        result = runner.invoke(cli, ["webhook-info"])

    assert result.exit_code == 0
    assert "URL: https://example.com/webhook" in result.output
    assert "Pending updates: 2" in result.output


def test_webhook_info_handles_error(monkeypatch):
    runner = CliRunner()
    with patch(
        "tg_wp_bridge.cli.get_webhook_info", new_callable=AsyncMock
    ) as mock_info:
        mock_info.side_effect = RuntimeError("boom")
        result = runner.invoke(cli, ["webhook-info"])

    assert result.exit_code == 1
    assert "Failed to get webhook info" in result.output


def test_set_webhook_success(monkeypatch):
    runner = CliRunner()
    dummy_settings = make_settings()

    with patch("tg_wp_bridge.cli.settings", dummy_settings):
        with patch(
            "tg_wp_bridge.cli.set_webhook", new_callable=AsyncMock
        ) as mock_set:
            mock_set.return_value = {
                "ok": True,
                "result": True,
                "description": "Webhook was set",
            }
            result = runner.invoke(cli, ["set-webhook"])

    assert result.exit_code == 0
    assert "Webhook configured successfully" in result.output
    assert "Telegram response: Webhook was set" in result.output


def test_set_webhook_reports_failure(monkeypatch):
    runner = CliRunner()
    dummy_settings = make_settings()

    with patch("tg_wp_bridge.cli.settings", dummy_settings):
        with patch(
            "tg_wp_bridge.cli.set_webhook", new_callable=AsyncMock
        ) as mock_set:
            mock_set.return_value = {"ok": False, "description": "bad"}
            result = runner.invoke(cli, ["set-webhook"])

    assert result.exit_code == 1
    assert "Webhook configuration failed" in result.output


def test_wp_info_command(monkeypatch):
    runner = CliRunner()
    dummy_settings = make_settings(wp_category_id=5, wp_publish_status="draft")

    with patch("tg_wp_bridge.cli.settings", dummy_settings):
        result = runner.invoke(cli, ["wp-info"])

    assert result.exit_code == 0
    assert "WordPress API configuration" in result.output
    assert "draft" in result.output
    assert "wp-json/wp/v2/media" in result.output


def test_wp_check_success(monkeypatch):
    runner = CliRunner()
    dummy_settings = make_settings()

    with patch("tg_wp_bridge.cli.settings", dummy_settings):
        with (
            patch(
                "tg_wp_bridge.cli.wordpress_api.ping_wp_api", new_callable=AsyncMock
            ) as mock_ping,
            patch(
                "tg_wp_bridge.cli.wordpress_api.check_wp_credentials",
                new_callable=AsyncMock,
            ) as mock_creds,
        ):
            mock_ping.return_value = {"name": "Site"}
            mock_creds.return_value = {"id": 1, "name": "Admin"}

            result = runner.invoke(cli, ["wp-check"])

    assert result.exit_code == 0
    assert "WordPress reachable" in result.output
    assert "WordPress credentials valid" in result.output


def test_wp_check_failure(monkeypatch):
    runner = CliRunner()
    dummy_settings = make_settings()

    with patch("tg_wp_bridge.cli.settings", dummy_settings):
        with (
            patch(
                "tg_wp_bridge.cli.wordpress_api.ping_wp_api", new_callable=AsyncMock
            ) as mock_ping,
            patch(
                "tg_wp_bridge.cli.wordpress_api.check_wp_credentials",
                new_callable=AsyncMock,
            ) as mock_creds,
        ):
            mock_ping.side_effect = Exception("down")
            mock_creds.return_value = {"id": 1}
            result = runner.invoke(cli, ["wp-check"])

    assert result.exit_code == 1
    assert "WordPress check failed" in result.output


def test_startup_check_sets_webhook(monkeypatch):
    runner = CliRunner()
    dummy_settings = make_settings()

    with patch("tg_wp_bridge.cli.settings", dummy_settings):
        with (
            patch("tg_wp_bridge.cli.get_webhook_info", new_callable=AsyncMock) as mock_info,
            patch("tg_wp_bridge.cli.set_webhook", new_callable=AsyncMock) as mock_set,
            patch(
                "tg_wp_bridge.cli.wordpress_api.ping_wp_api", new_callable=AsyncMock
            ) as mock_ping,
            patch(
                "tg_wp_bridge.cli.wordpress_api.check_wp_credentials",
                new_callable=AsyncMock,
            ) as mock_creds,
        ):
            mock_info.side_effect = [
                TelegramWebhookInfo(url=None),
                TelegramWebhookInfo(url="https://example.com/webhook"),
            ]
            mock_set.return_value = {"ok": True, "result": True}
            mock_ping.return_value = {"name": "Site"}
            mock_creds.return_value = {"id": 1, "name": "Admin"}

            result = runner.invoke(cli, ["startup-check"])

    assert result.exit_code == 0
    assert "Webhook configured successfully" in result.output
    assert "Startup summary" in result.output


def test_startup_check_wp_failure(monkeypatch):
    runner = CliRunner()
    dummy_settings = make_settings()

    with patch("tg_wp_bridge.cli.settings", dummy_settings):
        with (
            patch("tg_wp_bridge.cli.get_webhook_info", new_callable=AsyncMock) as mock_info,
            patch(
                "tg_wp_bridge.cli.wordpress_api.ping_wp_api", new_callable=AsyncMock
            ) as mock_ping,
            patch(
                "tg_wp_bridge.cli.wordpress_api.check_wp_credentials",
                new_callable=AsyncMock,
            ) as mock_creds,
        ):
            mock_info.return_value = TelegramWebhookInfo(url="https://example.com/webhook")
            mock_ping.side_effect = Exception("down")
            mock_creds.return_value = {"id": 1}

            result = runner.invoke(cli, ["startup-check"])

    assert result.exit_code == 1
    assert "Startup check reported failures" in result.output
