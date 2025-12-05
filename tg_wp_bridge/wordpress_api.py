"""
WordPress REST API helpers.

Responsibilities:
- Use Settings for configuration.
- Provide helpers to:
  * Build auth header
  * Upload media
  * Create posts
"""

import base64
import logging
from typing import Any, Dict, List, Optional

import httpx

from .config import settings
from .schemas import WPMediaResponse, WPPostResponse

log = logging.getLogger("tg-wp-bridge.wordpress")


def _ensure_wp_base_url() -> str:
    if not settings.wp_base_url:
        raise RuntimeError("WP_BASE_URL is not set; cannot talk to WordPress.")
    return str(settings.wp_base_url).rstrip("/")


def _ensure_wp_auth() -> None:
    if not settings.wp_username or not settings.wp_app_password:
        raise RuntimeError(
            "WP_USERNAME / WP_APP_PASSWORD not set; cannot auth to WordPress."
        )


def wp_auth_header() -> Dict[str, str]:
    """Build Basic Auth header for WordPress Application Passwords."""
    _ensure_wp_auth()
    token = f"{settings.wp_username}:{settings.wp_app_password}".encode("utf-8")
    b64 = base64.b64encode(token).decode("ascii")
    return {"Authorization": f"Basic {b64}"}


async def upload_media_to_wp(
    filename: str, content_type: str, data: bytes
) -> Optional[int]:
    """
    Upload a media file to WordPress and return its attachment ID.
    Returns None on error.
    """
    base = _ensure_wp_base_url()
    media_url = f"{base}/wp-json/wp/v2/media"
    headers = {
        **wp_auth_header(),
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": content_type,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                media_url, headers=headers, content=data, timeout=60.0
            )
            resp.raise_for_status()
            payload = resp.json()
            media = WPMediaResponse.model_validate(payload)
            log.info("Uploaded media to WP: id=%s, filename=%s", media.id, filename)
            return media.id
    except Exception as e:
        log.exception("Failed to upload media to WordPress: %s", e)
        return None


async def create_wp_post(
    title: str,
    content_html: str,
    media_ids: Optional[List[int]] = None,
) -> WPPostResponse:
    """
    Create a WordPress post with given content and category.

    media_ids can be used to set featured_media (first image).
    """
    base = _ensure_wp_base_url()
    post_url = f"{base}/wp-json/wp/v2/posts"
    payload: Dict[str, Any] = {
        "title": title or "(no title)",
        "content": content_html,
        "status": settings.wp_publish_status,
    }

    if settings.wp_category_id:
        payload["categories"] = [settings.wp_category_id]

    if media_ids:
        payload["featured_media"] = media_ids[0]

    headers = {
        **wp_auth_header(),
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(post_url, headers=headers, json=payload, timeout=30.0)
        try:
            resp.raise_for_status()
        except Exception:
            log.error("Failed creating WP post: %s / %s", resp.status_code, resp.text)
            raise
        data = resp.json()
        post = WPPostResponse.model_validate(data)
        log.info("Created WP post id=%s", post.id)
        return post
