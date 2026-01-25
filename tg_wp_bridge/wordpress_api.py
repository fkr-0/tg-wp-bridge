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


async def update_wp_post(
    *, post_id: int,
    title: Optional[str] = None,
    content_html: Optional[str] = None,
    slug: Optional[str] = None,
    media_ids: Optional[List[int]] = None,
    status: Optional[str] = None,
    categories: Optional[List[int]] = None,
) -> WPPostResponse:
    """Update an existing WordPress post.

    This helper issues a ``PATCH`` request to the WordPress REST API to
    update the specified post.  Fields that are ``None`` are omitted
    from the payload.  Respecting ``settings.wp_skip``, when skip is
    enabled this function does not perform network calls and instead
    returns a dummy response.

    Args:
        post_id: The numeric ID of the post to update.
        title: New title for the post (optional).
        content_html: New HTML content for the post (optional).
        slug: New slug for the post (optional).
        media_ids: List of attachment IDs to set as featured_media
            (only the first is used).
        status: New status for the post (publish, draft, etc.).
        categories: List of category IDs to assign.

    Returns:
        A :class:`WPPostResponse` with updated fields.
    """
    base = _ensure_wp_base_url()
    post_type = settings.wp_post_type or "post"
    wp_endpoint = "posts" if post_type == "post" else post_type
    url = f"{base}/wp-json/wp/v2/{wp_endpoint}/{post_id}"
    payload: Dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if content_html is not None:
        payload["content"] = content_html
    if slug is not None:
        payload["slug"] = slug
    if status is not None:
        payload["status"] = status
    if categories:
        payload["categories"] = categories
    if media_ids:
        payload["featured_media"] = media_ids[0]

    # Respect wp_skip: return dummy response
    if settings.wp_skip:
        log.info(
            "wp_skip is enabled; skipping update of WordPress post id=%s", post_id
        )
        return WPPostResponse(
            id=post_id,
            link=None,
            title={"rendered": title or ""},
            content={"rendered": content_html or ""},
        )

    headers = {**wp_auth_header(), "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        resp = await client.patch(url, headers=headers, json=payload, timeout=30.0)
        try:
            resp.raise_for_status()
        except Exception:
            log.error(
                "Failed updating WP post %s: %s / %s", post_id, resp.status_code, resp.text
            )
            raise
        data = resp.json()
        post = WPPostResponse.model_validate(data)
        log.info("Updated WP post id=%s", post.id)
        return post


async def list_wp_post_types() -> Dict[str, Any]:
    """Retrieve the list of WordPress post types.

    Returns the raw JSON mapping of post type names to their schemas.
    If ``wp_skip`` is enabled, returns an empty dict.
    """
    if settings.wp_skip:
        log.info("wp_skip enabled; returning empty post type list")
        return {}
    base = _ensure_wp_base_url()
    url = f"{base}/wp-json/wp/v2/types"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        return resp.json()


async def list_wp_categories(per_page: int = 100) -> Any:
    """Retrieve WordPress categories via the REST API.

    Args:
        per_page: Number of results to request per page (default 100).

    Returns:
        A list of category objects.  Returns an empty list if ``wp_skip``
        is enabled or an error occurs.
    """
    if settings.wp_skip:
        log.info("wp_skip enabled; returning empty category list")
        return []
    base = _ensure_wp_base_url()
    url = f"{base}/wp-json/wp/v2/categories"
    params = {"per_page": per_page}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()


async def list_wp_tags(per_page: int = 100) -> Any:
    """Retrieve WordPress tags via the REST API.

    Args:
        per_page: Number of results to request per page (default 100).

    Returns:
        A list of tag objects.  Returns an empty list if ``wp_skip`` is
        enabled or an error occurs.
    """
    if settings.wp_skip:
        log.info("wp_skip enabled; returning empty tag list")
        return []
    base = _ensure_wp_base_url()
    url = f"{base}/wp-json/wp/v2/tags"
    params = {"per_page": per_page}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()


async def get_wp_schema() -> Any:
    """Fetch the WordPress REST API root schema.

    This function returns the raw JSON describing the available endpoints
    and resources.  If ``wp_skip`` is enabled, an empty dict is
    returned instead.
    """
    if settings.wp_skip:
        log.info("wp_skip enabled; returning empty schema")
        return {}
    base = _ensure_wp_base_url()
    url = f"{base}/wp-json"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        return resp.json()


async def upload_media_to_wp(
    filename: str, content_type: str, data: bytes
) -> Optional[WPMediaResponse]:
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

    # Respect wp_skip flag: when enabled, do not perform network requests
    if settings.wp_skip:
        log.info(
            "wp_skip is enabled; skipping media upload for filename=%s",
            filename,
        )
        # Return a dummy response with id=0 and no source_url
        return WPMediaResponse(id=0, source_url=None)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                media_url, headers=headers, content=data, timeout=60.0
            )
            resp.raise_for_status()
            payload = resp.json()
            media = WPMediaResponse.model_validate(payload)
            log.info(
                "Uploaded media to WP: id=%s filename=%s mime=%s",
                media.id,
                filename,
                getattr(media, "mime_type", content_type),
            )
            return media
    except Exception as e:
        log.exception("Failed to upload media to WordPress: %s", e)
        return None


async def ping_wp_api() -> Dict[str, Any]:
    """Fetch /wp-json to ensure WordPress is reachable."""

    if settings.wp_skip:
        log.info("wp_skip enabled; skipping WordPress ping")
        return {}

    base = _ensure_wp_base_url()
    url = f"{base}/wp-json"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        payload = resp.json()
        log.info("WordPress ping succeeded: %s", url)
        return payload


async def check_wp_credentials() -> Dict[str, Any]:
    """Validate WordPress credentials via /wp-json/wp/v2/users/me."""

    if settings.wp_skip:
        log.info("wp_skip enabled; skipping WordPress credential check")
        return {}

    base = _ensure_wp_base_url()
    url = f"{base}/wp-json/wp/v2/users/me"
    headers = wp_auth_header()

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        payload = resp.json()
        log.info("WordPress credentials OK for user id=%s", payload.get("id"))
        return payload


async def create_wp_post(
    title: str,
    content_html: str,
    media_ids: Optional[List[int]] = None,
    slug: Optional[str] = None,
) -> WPPostResponse:
    """
    Create a WordPress post with given content and category.

    media_ids can be used to set featured_media (first image).
    slug can be provided for a custom permalink slug.
    """
    base = _ensure_wp_base_url()
    post_type = settings.wp_post_type or "post"
    # WordPress REST API uses plural form for standard post types
    # "post" -> "posts", "page" -> "pages", but custom post types vary
    wp_endpoint = "posts" if post_type == "post" else post_type
    post_url = f"{base}/wp-json/wp/v2/{wp_endpoint}"
    payload: Dict[str, Any] = {
        "title": title or "(no title)",
        "content": content_html,
        "status": settings.wp_publish_status,
    }

    if slug:
        payload["slug"] = slug

    if settings.wp_category_id:
        payload["categories"] = [settings.wp_category_id]

    if media_ids:
        payload["featured_media"] = media_ids[0]

    headers = {
        **wp_auth_header(),
        "Content-Type": "application/json",
    }

    # Respect wp_skip: if enabled, do not create a post via network
    if settings.wp_skip:
        log.info(
            "wp_skip is enabled; skipping creation of WordPress post titled %r", title
        )
        # Simulate a WordPress post response
        dummy = WPPostResponse(
            id=0,
            link=None,
            title={"rendered": title},
            content={"rendered": content_html},
        )
        return dummy

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
