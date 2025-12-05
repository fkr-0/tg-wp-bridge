"""
Telegram HTTP API helpers.

Responsibilities:
- Use Settings for configuration.
- Provide functions for:
  * get_file_direct_url(file_id)
  * download_file(file_url)
  * set_webhook()
  * get_webhook_info()
"""

import logging
from typing import Optional, Dict, Any

import httpx

from .config import settings
from .schemas import TelegramWebhookInfo

log = logging.getLogger("tg-wp-bridge.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org"


def _ensure_bot_token() -> str:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set; cannot call Telegram API.")
    return settings.telegram_bot_token


def _bot_url(path: str) -> str:
    token = _ensure_bot_token()
    return f"{TELEGRAM_API_BASE}/bot{token}/{path.lstrip('/')}"


async def get_file_direct_url(file_id: str) -> Optional[str]:
    """
    Given a Telegram file_id, return a direct HTTPS URL for that file.

    Note:
      - This URL is temporary and should be used only to download once.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _bot_url("getFile"), params={"file_id": file_id}, timeout=10.0
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            log.warning("getFile failed: %s", data)
            return None

        file_path = data["result"]["file_path"]
        url = f"{TELEGRAM_API_BASE}/file/bot{_ensure_bot_token()}/{file_path}"
        return url


async def download_file(file_url: str) -> bytes:
    """Download a Telegram file via HTTPS."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(file_url, timeout=30.0)
        resp.raise_for_status()
        return resp.content


async def set_webhook() -> Dict[str, Any]:
    """
    Configure Telegram webhook to point to this service.

    Requires:
      - TELEGRAM_BOT_TOKEN
      - PUBLIC_BASE_URL
      - TELEGRAM_WEBHOOK_SECRET

    This is the programmatic equivalent of the curl command:

      curl "https://api.telegram.org/botTOKEN/setWebhook" \
           -d "url=https://your-domain.example/tg-webhook/SECRET"
    """
    _ensure_bot_token()

    if not settings.public_base_url:
        raise RuntimeError("PUBLIC_BASE_URL is not set; cannot compute webhook URL.")
    if not settings.telegram_webhook_secret:
        raise RuntimeError(
            "TELEGRAM_WEBHOOK_SECRET is not set; webhook would be unprotected."
        )

    webhook_url = (
        f"{settings.public_base_url}/webhook/{settings.telegram_webhook_secret}"
    )
    payload = {"url": webhook_url}

    log.info("Setting Telegram webhook to: %s", webhook_url)

    async with httpx.AsyncClient() as client:
        resp = await client.post(_bot_url("setWebhook"), data=payload, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            log.error("Failed to set webhook: %s", data)
        else:
            log.info("Webhook set response: %s", data)
        return data


async def get_webhook_info() -> TelegramWebhookInfo:
    """
    Inspect current webhook status from Telegram.

    Returns TelegramWebhookInfo model.
    """
    _ensure_bot_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(_bot_url("getWebhookInfo"), timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        log.info("Webhook info: %s", data)
        return TelegramWebhookInfo.model_validate(data)
