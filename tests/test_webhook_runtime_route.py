import logging
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from tg_wp_bridge import app as app_module


def _webhook_path(secret: str, prefix: str) -> str:
    safe_prefix = prefix.strip("/")
    if safe_prefix:
        return f"/{safe_prefix}/{secret}"
    return f"/{secret}"


def test_registered_webhook_path_accepts_update_without_query_secret():
    client = TestClient(app_module.app)

    update_data = {
        "update_id": 123,
        "channel_post": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": 1, "type": "channel"},
            "text": "hello",
        },
    }

    webhook_prefix = app_module.settings.webhook_prefix

    with (
        patch.object(app_module.settings, "telegram_webhook_secret", "test-secret"),
        patch("tg_wp_bridge.app.handle_telegram_update", new_callable=AsyncMock) as mock_handle,
    ):
        mock_handle.return_value = None
        response = client.post(
            _webhook_path(secret="test-secret", prefix=webhook_prefix),
            json=update_data,
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_webhook_validation_errors_are_logged(caplog):
    client = TestClient(app_module.app)
    webhook_prefix = app_module.settings.webhook_prefix
    webhook_secret = app_module.settings.telegram_webhook_secret or "test-secret"

    caplog.set_level(logging.WARNING, logger="tg-wp-bridge.app")
    response = client.post(
        _webhook_path(secret=webhook_secret, prefix=webhook_prefix),
        json={"not_a_valid_update": True},
    )

    assert response.status_code == 422
    assert any("Request validation failed" in record.message for record in caplog.records)
