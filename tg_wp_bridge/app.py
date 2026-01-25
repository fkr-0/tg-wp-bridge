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

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse

from . import message_parser
from . import startup
from . import telegram_api
from . import wordpress_api
from .config import settings
from .display import DisplayManager
from .update_model import TelegramUpdate  # enhanced update model
from .schemas import WPMediaResponse  # WordPress types remain here

# Import dispatcher and handlers to register update handlers
from .dispatcher import dispatch_update  # noqa: F401
from . import handlers  # noqa: F401  # ensure handlers are imported and registered

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
    # Deprecated monolithic handler: replaced by dispatcher.
    # This function is retained for backward compatibility but now simply
    # forwards the update to the dispatcher.
    log.debug(
        "handle_telegram_update called for update %s; delegating to dispatcher",
        update.update_id,
    )
    await dispatch_update(update)


# ---------------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------------


async def telegram_webhook(secret: str, update: TelegramUpdate):
    """
    Telegram webhook endpoint – secret is a simple path-level shared secret.

    Telegram is configured (via telegram_api.set_webhook) to call:

      PUBLIC_BASE_URL/{WEBHOOK_PREFIX}/TELEGRAM_WEBHOOK_SECRET

    The WEBHOOK_PREFIX defaults to "webhook" but can be customized.
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

# ---------------------------------------------------------------------------
# Simulation endpoint
# ---------------------------------------------------------------------------

@app.post("/simulate-update")
async def simulate_update_endpoint(
    update: TelegramUpdate,
    force: bool = False,
    secret: str | None = None,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> dict:
    """
    Manually simulate processing of a Telegram update.

    This endpoint is useful when ``TG_SKIP`` is enabled to bypass the
    Telegram webhook mechanism and test WordPress integration.  The
    request body must contain a valid Telegram update JSON payload.  If
    ``force`` is true, the dispatcher will temporarily ignore the
    ``tg_skip`` setting and process the update normally.  Otherwise,
    ``tg_skip`` is respected.

    Returns a JSON object summarizing the result.
    """
    expected = settings.telegram_webhook_secret
    provided = secret or x_webhook_secret
    if expected and provided != expected:
        # Keep the simulation endpoint guarded when a webhook secret is configured.
        raise HTTPException(status_code=403, detail="Forbidden")

    previous_tg_skip = settings.tg_skip
    if force:
        # Temporarily disable tg_skip to force processing
        object.__setattr__(settings, "tg_skip", False)
    try:
        await dispatch_update(update)
    finally:
        # Restore original flag
        if force:
            object.__setattr__(settings, "tg_skip", previous_tg_skip)
    return {"ok": True}


# Register webhook route with configurable path prefix
# This must be done after the function definition and app creation
_webhook_path = f"/{settings.webhook_prefix}/{{secret}}"
app.post(_webhook_path.replace("//", "/"))(telegram_webhook)
log.info("Registered Telegram webhook endpoint at path: %s", _webhook_path)


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
