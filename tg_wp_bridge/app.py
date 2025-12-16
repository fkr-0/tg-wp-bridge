# == tg_wp_bridge/app.py ==
"""
FastAPI application wiring Telegram updates to WordPress posts.

Orchestration layer:
- Uses typed schemas (pydantic) for Telegram updates.
- Uses Settings via config.py.
- Defines FastAPI routes:
  * POST /webhook/{secret}       – Telegram webhook endpoint
  * GET  /healthz                – health check
  * POST /telegram/set_webhook   – configure webhook
  * GET  /telegram/webhook_info  – inspect webhook status
"""

import logging
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import message_parser
from . import telegram_api
from . import wordpress_api
from .config import settings
from .schemas import TelegramUpdate

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tg-wp-bridge.app")

app = FastAPI()


# ---------------------------------------------------------------------------
# Core handler: Telegram update -> WordPress post
# ---------------------------------------------------------------------------


async def handle_telegram_update(update: TelegramUpdate) -> None:
    """
    Given a Telegram update, create a WordPress post if it is a channel message.

    Logic:
      - Ignore anything that is not a "channel" chat.
      - Optionally filter by REQUIRED_HASHTAG.
      - Use first non-empty line (minus leading hashtags) as title.
      - Use simple paragraph-aware HTML rendering for content.
      - If a photo is attached, upload it to WP and set as featured media.
    """
    msg = message_parser.extract_message_entity(update)
    if not msg:
        log.info("Update has no message/channel_post, ignoring.")
        return

    chat = msg.chat
    if chat.type != "channel":
        log.info("Ignoring non-channel message (chat type: %s)", chat.type)
        return

    text = msg.text or msg.caption or ""
    if not text.strip():
        log.info("Message has no text, ignoring.")
        return

    # Optional hashtag-based filtering
    if settings.required_hashtag:
        hashtags = message_parser.extract_hashtags(text)
        if settings.required_hashtag not in hashtags:
            log.info(
                "Message skipped: required hashtag %r missing (found: %s)",
                settings.required_hashtag,
                hashtags,
            )
            return
        log.info(
            "Message contains required hashtag %r, proceeding",
            settings.required_hashtag,
        )

    title = message_parser.build_title_from_text(text)
    content_html = message_parser.text_to_html(text)

    media_ids: List[int] = []

    photo = message_parser.find_photo_with_max_size(msg)
    if photo:
        log.info("Message has photo, file_id=%s", photo.file_id)
        try:
            file_url = await telegram_api.get_file_direct_url(photo.file_id)
            if file_url:
                img_data = await telegram_api.download_file(file_url)
                media_id = await wordpress_api.upload_media_to_wp(
                    filename="telegram-photo.jpg",
                    content_type="image/jpeg",
                    data=img_data,
                )
                if media_id:
                    media_ids.append(media_id)
        except Exception:
            log.exception("Failed handling Telegram photo, continuing without media")

    await wordpress_api.create_wp_post(
        title=title,
        content_html=content_html,
        media_ids=media_ids,
    )


# ---------------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------------


@app.post("/webhook/{secret}")
async def telegram_webhook(secret: str, update: TelegramUpdate):
    """
    Telegram webhook endpoint – secret is a simple path-level shared secret.

    Telegram is configured (via telegram_api.set_webhook) to call:

      PUBLIC_BASE_URL/webhook/TELEGRAM_WEBHOOK_SECRET
    """
    expected = settings.telegram_webhook_secret
    if expected and secret != expected:
        log.warning("Invalid webhook secret: %s", secret)
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        await handle_telegram_update(update)
    except Exception as e:
        log.exception("Error while handling Telegram update: %s", e)
        # Return 200 so Telegram doesn't hammer retries forever.
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)

    return {"ok": True}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/telegram/set_webhook")
async def http_set_webhook():
    """
    Convenience endpoint to configure the Telegram webhook.

    NOTE: In production you probably want to:
      - Restrict access to this endpoint (e.g. IP allowlist, auth).
      - Or run telegram_api.set_webhook() from a one-off script instead.
    """
    try:
        result = await telegram_api.set_webhook()
    except Exception as e:
        log.exception("Failed to set webhook: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return result


@app.get("/telegram/webhook_info")
async def http_webhook_info():
    """
    Inspect current Telegram webhook status.

    This simply wraps telegram_api.get_webhook_info().
    """
    try:
        result = await telegram_api.get_webhook_info()
    except Exception as e:
        log.exception("Failed to get webhook info: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return result


# == end/tg_wp_bridge/app.py ==
