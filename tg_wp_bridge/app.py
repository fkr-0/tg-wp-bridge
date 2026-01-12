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
import mimetypes
import os
from contextlib import asynccontextmanager
from html import escape
from pathlib import PurePosixPath
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import message_parser
from . import startup
from . import telegram_api
from . import wordpress_api
from .config import settings
from .display import DisplayManager
from .schemas import TelegramUpdate, WPMediaResponse

# Configure verbose logging from the start
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)

# Set DEBUG logging if environment variable is set
if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("tg-wp-bridge").setLevel(logging.DEBUG)

log = logging.getLogger("tg-wp-bridge.app")
log.info("Initializing tg-wp-bridge application...")

# Log environment configuration (without sensitive values)
log.debug("Environment configuration:")
log.debug(f"  LOG_LEVEL: {os.getenv('LOG_LEVEL', 'INFO')}")
log.debug(
    f"  TELEGRAM_BOT_TOKEN: {'***SET***' if os.getenv('TELEGRAM_BOT_TOKEN') else 'NOT SET'}"
)
log.debug(f"  PUBLIC_BASE_URL: {os.getenv('PUBLIC_BASE_URL', 'NOT SET')}")
log.debug(f"  WP_BASE_URL: {os.getenv('WP_BASE_URL', 'NOT SET')}")
log.debug(f"  WP_USERNAME: {os.getenv('WP_USERNAME', 'NOT SET')}")
log.debug(f"  REQUIRED_HASHTAG: {os.getenv('REQUIRED_HASHTAG', 'NOT SET')}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with startup validation."""
    # Create display manager with TTY auto-detection
    display = DisplayManager()

    # Startup phase
    if display.is_rich():
        display.print_header("TG-WP-BRIDGE STARTING UP")
    else:
        log.info("=" * 60)
        log.info("TG-WP-BRIDGE STARTING UP")
        log.info("=" * 60)

    try:
        # Run comprehensive startup validation with rich output
        await startup.validate_and_log_startup(
            auto_setup_webhook=True,
            display=display,
        )
        if display.is_rich():
            display.print_success("Application ready to handle requests")
        else:
            log.info("✓ Application startup validation completed successfully")
            log.info("✓ Application is ready to handle requests")
    except Exception as e:
        if display.is_rich():
            display.print_error(f"Startup validation failed: {e}")
            display.print_warning(
                "Application will continue but may not function properly"
            )
        else:
            log.error(f"✗ Startup validation failed: {e}")
            log.error("Application will continue but may not function properly")
        # Continue running despite validation failures (graceful degradation)

    # Application is running
    yield

    # Shutdown phase
    log.info("Application shutting down...")


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Core handler: Telegram update -> WordPress post
# ---------------------------------------------------------------------------


def _filename_from_url(file_url: str) -> Optional[str]:
    path = urlparse(file_url).path
    if not path:
        return None
    name = PurePosixPath(path).name
    return name or None


async def _download_and_upload_media(
    media: message_parser.TelegramMedia,
) -> Optional[WPMediaResponse]:
    """Download a Telegram media file and upload it to WordPress."""

    try:
        file_url = await telegram_api.get_file_direct_url(media.file_id)
        if not file_url:
            log.warning(
                "No file URL resolved for media %s (%s)",
                media.file_id,
                media.media_type,
            )
            return None
        blob = await telegram_api.download_file(file_url)
    except Exception:
        log.exception("Failed to download media %s", media.file_id)
        return None

    filename = media.file_name or _filename_from_url(file_url)
    if not filename:
        filename = f"telegram-{media.media_type}-{media.file_id[:8]}"

    content_type = media.mime_type or mimetypes.guess_type(filename)[0]
    if not content_type:
        content_type = "application/octet-stream"

    try:
        return await wordpress_api.upload_media_to_wp(
            filename=filename,
            content_type=content_type,
            data=blob,
        )
    except Exception:
        log.exception("Failed to upload media %s to WordPress", media.file_id)
        return None


def _build_media_gallery(
    uploaded: List[Tuple[message_parser.TelegramMedia, WPMediaResponse]],
) -> str:
    sections: List[str] = []
    for descriptor, wp_media in uploaded:
        source_url = wp_media.source_url
        if not source_url:
            continue
        safe_url = escape(str(source_url))
        alt = escape(f"Telegram {descriptor.media_type}")
        if descriptor.media_type == "photo":
            sections.append(
                f'<figure class="telegram-media telegram-photo">'
                f'<img src="{safe_url}" alt="{alt}"></figure>'
            )
        elif descriptor.media_type in {"video", "animation"}:
            sections.append(
                (
                    f'<figure class="telegram-media telegram-{descriptor.media_type}">'
                    f'<video controls src="{safe_url}">'
                    f'<a href="{safe_url}">Download media</a></video></figure>'
                )
            )
        else:
            sections.append(
                f'<p class="telegram-media telegram-link">'
                f'<a href="{safe_url}">Download attachment</a></p>'
            )
    return "".join(sections)


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
    allowed_chat_types = getattr(settings, "chat_type_allowlist", ("channel",))
    if allowed_chat_types:
        if chat.type not in allowed_chat_types:
            log.info(
                "Ignoring message from chat type %s (allowed: %s)",
                chat.type,
                ",".join(allowed_chat_types),
            )
            return

    text = message_parser.extract_message_text(update) or ""
    media_entries = message_parser.collect_supported_media(msg)

    if not text.strip() and not media_entries:
        log.info("Message has no text or supported media, ignoring.")
        return

    # Optional hashtag-based filtering
    hashtags = message_parser.extract_hashtags(text) if text else []

    if settings.required_hashtag:
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

    hashtag_allowlist = getattr(settings, "hashtag_allowlist", None)
    if hashtag_allowlist:
        if not any(tag in hashtags for tag in hashtag_allowlist):
            log.info(
                "Message skipped: no allowed hashtags present (allowed: %s)",
                hashtag_allowlist,
            )
            return

    hashtag_blocklist = getattr(settings, "hashtag_blocklist", None)
    if hashtag_blocklist and any(tag in hashtags for tag in hashtag_blocklist):
        log.info(
            "Message skipped: blocked hashtag present (blocked: %s)",
            hashtag_blocklist,
        )
        return

    title = message_parser.build_title_from_text(text)
    content_html = message_parser.text_to_html(text) if text.strip() else ""

    media_ids: List[int] = []
    uploaded_media: List[Tuple[message_parser.TelegramMedia, WPMediaResponse]] = []

    for media in media_entries:
        log.info(
            "Processing Telegram media type=%s file_id=%s",
            media.media_type,
            media.file_id,
        )
        media_info = await _download_and_upload_media(media)
        if media_info:
            media_ids.append(media_info.id)
            uploaded_media.append((media, media_info))

    media_markup = _build_media_gallery(uploaded_media)
    if media_markup:
        content_html = f"{content_html}{media_markup}" if content_html else media_markup

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
    """
    Health check endpoint.

    Returns basic status information. For detailed validation status,
    use the /validation endpoint.
    """
    return {"status": "ok", "service": "tg-wp-bridge"}


@app.get("/validation")
async def validation_status():
    """
    Return the current validation status of all components.

    This endpoint runs a quick validation check without modifying
    any configuration (no automatic webhook setup).
    """
    try:
        results = await startup.run_startup_validation(auto_setup_webhook=False)
        return {
            "status": results["overall"]["status"],
            "errors": results["overall"]["errors"],
            "details": results,
        }
    except Exception as e:
        return {"status": "failed", "errors": [str(e)], "details": None}


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
