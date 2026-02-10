"""
Handlers for various Telegram update kinds.

This module defines coroutine functions to process Telegram updates
based on their kind.  Handlers are registered with the dispatcher
using the :func:`register_handler` decorator.  Each handler receives
the full :class:`TelegramUpdate` object as well as the specific
payload extracted via :meth:`TelegramUpdate.get_payload`.

Features provided here include:

* Creating WordPress posts from new messages or channel posts.
* Updating existing posts when edited messages are received.
* Recording a mapping between Telegram message IDs and WordPress post IDs.
* Respecting ``settings.tg_skip`` and ``settings.wp_skip`` flags to
  skip processing or WordPress writes.
* Logging updates and WordPress interactions to a structured
  storage directory for later inspection.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple

from .config import settings
from .dispatcher import register_handler
from .message_parser import (
    TelegramMedia,
    collect_supported_media,
    extract_hashtags,
    extract_message_text,
    build_title_from_text,
    build_slug_from_text,
    text_to_html,
)
from .schemas import TgMessage  # message model
from .update_model import TelegramUpdate, UpdateKind
from .telegram_api import get_file_direct_url, download_file
from .wordpress_api import (
    create_wp_post,
    update_wp_post,
    upload_media_to_wp,
    get_wp_post_content,
    get_wp_post_featured_media,
)

log = logging.getLogger("tg-wp-bridge.handlers")


def _resolve_writable_dir(
    preferred: Path,
    *,
    fallback_env_var: str,
    fallback_subdir: str,
) -> Path:
    """Return a writable directory path, falling back to /tmp when needed."""
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except PermissionError as exc:
        fallback_root = Path(
            os.getenv(
                fallback_env_var,
                str(Path(tempfile.gettempdir()) / "tg-wp-bridge" / fallback_subdir),
            )
        )
        fallback_root.mkdir(parents=True, exist_ok=True)
        log.warning(
            "Directory %s is not writable (%s); falling back to %s",
            preferred,
            exc,
            fallback_root,
        )
        return fallback_root


def _mapping_file() -> Path:
    """Return the current mapping file path.

    Reads ``TG_WP_MAPPING_FILE`` on each call so tests and deployments can
    override it without needing to reload the module.
    """
    path = Path(os.getenv("TG_WP_MAPPING_FILE", "data/message_map.json"))
    parent = _resolve_writable_dir(
        path.parent,
        fallback_env_var="TG_WP_MAPPING_FALLBACK_DIR",
        fallback_subdir="mapping",
    )
    return parent / path.name


def _load_mapping() -> Dict[str, int]:
    """Load the persistent message→post mapping from JSON.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    mapping_path = _mapping_file()
    if not mapping_path.exists():
        return {}
    try:
        with mapping_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return {str(k): int(v) for k, v in data.items()}
    except Exception:
        log.warning("Failed to load mapping from %s", mapping_path)
        return {}


def _save_mapping(mapping: Dict[str, int]) -> None:
    """Save the message→post mapping to JSON atomically."""
    mapping_path = _mapping_file()
    tmp_path = mapping_path.with_suffix(".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(mapping, fh, indent=2, ensure_ascii=False)
        tmp_path.replace(mapping_path)
    except Exception:
        log.exception("Failed to save mapping to %s", mapping_path)


def _record_update_log(
    update: TelegramUpdate,
    wp_result: Optional[Dict[str, Any]] = None,
    *,
    tg_message_id: Optional[int] = None,
) -> Dict[str, Optional[str]]:
    """Record raw update and optional WordPress result to disk.

    A log directory is defined by the ``STORAGE_DIR`` environment variable
    or defaults to ``logs``.  Files are named using ISO timestamps and the
    Telegram update ID.  WordPress results include the post ID in the
    filename when available.
    """
    preferred_storage_dir = Path(os.getenv("STORAGE_DIR", "logs"))
    storage_dir = _resolve_writable_dir(
        preferred_storage_dir,
        fallback_env_var="STORAGE_FALLBACK_DIR",
        fallback_subdir="logs",
    )
    # Include microseconds to avoid collisions when multiple updates are
    # processed within the same second.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    tgid = tg_message_id if tg_message_id is not None else update.update_id
    out: Dict[str, Optional[str]] = {"tg_path": None, "wp_path": None}

    # Write Telegram update JSON
    tg_filename = f"{ts}_tg_{tgid}.json"
    try:
        with (storage_dir / tg_filename).open("w", encoding="utf-8") as fh:
            json.dump(update.model_dump(mode="json", exclude_none=True), fh, indent=2)
        out["tg_path"] = str(storage_dir / tg_filename)
    except Exception:
        log.exception("Failed to write Telegram update log")
    # Write WordPress response if provided
    if wp_result is not None:
        post_id = wp_result.get("id") if isinstance(wp_result, dict) else None
        wp_filename = f"{ts}_wp_{tgid}_{post_id or 'unknown'}.json"
        try:
            with (storage_dir / wp_filename).open("w", encoding="utf-8") as fh:
                json.dump(wp_result, fh, indent=2)
            out["wp_path"] = str(storage_dir / wp_filename)
        except Exception:
            log.exception("Failed to write WordPress response log")

    # After writing logs, perform rotation if limits are configured
    _rotate_logs(storage_dir)

    return out


def _stats_for_text(text: str) -> Dict[str, int]:
    stripped = text or ""
    return {
        "chars": len(stripped),
        "lines": len(stripped.splitlines()) if stripped else 0,
        "words": len([w for w in stripped.split() if w]) if stripped else 0,
    }


def _media_counts(media: List[TelegramMedia]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for m in media:
        out[m.media_type] = out.get(m.media_type, 0) + 1
    return out


def _media_group_mapping_key(msg: TgMessage) -> Optional[str]:
    """Build a stable mapping key for Telegram media groups (albums)."""
    media_group_id = getattr(msg, "media_group_id", None)
    chat = getattr(msg, "chat", None)
    chat_id = getattr(chat, "id", None) if chat is not None else None
    if media_group_id is None or chat_id is None:
        return None
    return f"mg:{chat_id}:{media_group_id}"


def _extract_video_preview_media(msg: TgMessage) -> Optional[TelegramMedia]:
    """Return a thumbnail media descriptor for video/animation when available."""
    for attr in ("video", "animation"):
        candidate = getattr(msg, attr, None)
        if candidate is None:
            continue
        thumb = getattr(candidate, "thumbnail", None) or getattr(candidate, "thumb", None)
        file_id = getattr(thumb, "file_id", None) if thumb is not None else None
        if file_id:
            return TelegramMedia(
                file_id=file_id,
                media_type="photo",
                file_name=f"{file_id}.jpg",
                mime_type="image/jpeg",
            )
    return None


async def _upload_single_media(media: TelegramMedia) -> Optional[Any]:
    """Upload one Telegram media descriptor to WordPress."""
    file_url = await get_file_direct_url(media.file_id)
    if not file_url:
        log.warning(
            "No file URL resolved for media %s (%s)",
            media.file_id,
            media.media_type,
        )
        return None
    blob = await download_file(file_url)
    file_name = media.file_name or media.file_id
    mime = media.mime_type or "application/octet-stream"
    log.info(
        "Uploading media to WP: file_id=%s filename=%s mime=%s bytes=%s",
        media.file_id,
        file_name,
        mime,
        len(blob),
    )
    return await upload_media_to_wp(file_name, mime, blob)


def _build_media_gallery(
    items: List[Tuple[TelegramMedia, Any]],
) -> str:
    """Build a minimal HTML gallery for uploaded media.

    Expects tuples of (TelegramMedia, WPMediaResponse-like) where the second
    element has a `source_url` attribute.
    """
    sections: List[str] = []
    for descriptor, wp_media in items:
        source_url = getattr(wp_media, "source_url", None)
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
                f'<figure class="telegram-media telegram-{descriptor.media_type}">'
                f'<video controls src="{safe_url}"></video></figure>'
            )
        else:
            sections.append(
                f'<p class="telegram-media telegram-link">'
                f'<a href="{safe_url}">Download attachment</a></p>'
            )
    return "".join(sections)


def _log_semantic_summary(
    *,
    kind: str,
    tgid: int,
    title: str,
    slug: str,
    text: str,
    media: List[TelegramMedia],
    media_wp_paths: List[str],
    wp_post_id: Optional[int],
    tg_log_path: Optional[str] = None,
    wp_log_path: Optional[str] = None,
    status: str = "SUCCESS",
) -> None:
    stats = _stats_for_text(text)
    counts = _media_counts(media)
    iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: List[str] = []
    lines.append(f"=== {iso}<{tgid}> Update: {kind} ===")
    if tg_log_path:
        lines.append(f"  stored: {tg_log_path}")
    lines.append(f"  title: {title!r}")
    lines.append(f"  slug: {slug!r}")
    lines.append(
        f"  content: {stats['words']} words, {stats['lines']} lines, {stats['chars']} chars"
    )
    if counts:
        parts = [f"{v} {k}{'' if v == 1 else 's'}" for k, v in sorted(counts.items())]
        lines.append("  media: " + ", ".join(parts))
    else:
        lines.append("  media: none")
    for p in media_wp_paths:
        lines.append(f"    => {p}")
    if wp_post_id is not None:
        post_type = getattr(settings, "wp_post_type", None) or "post"
        endpoint = "posts" if post_type == "post" else post_type
        lines.append(f"  post: => wp/{endpoint}?id={wp_post_id}")
    if wp_log_path:
        lines.append(f"  stored: {wp_log_path}")
    lines.append(f"=== {iso} :: {status} ===")
    log.info("\n".join(lines))


def _rotate_logs(storage_dir: Path) -> None:
    """Rotate log files based on count or size limits.

    This helper enforces optional limits on the number of log files
    (``LOG_MAX_FILES``) and the cumulative size in bytes of the log
    directory (``LOG_MAX_BYTES``).  If limits are not set (0 or
    undefined), no rotation occurs.  When limits are exceeded, the
    oldest files are removed until within the limits.

    Args:
        storage_dir: Path to the directory containing log files.
    """
    try:
        # Collect JSON log files only
        files = sorted(
            (p for p in storage_dir.glob("*.json") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
        )
        # Enforce max files limit
        max_files = int(os.getenv("LOG_MAX_FILES", "0") or 0)
        if max_files > 0 and len(files) > max_files:
            to_remove = files[: len(files) - max_files]
            for f in to_remove:
                try:
                    f.unlink()
                    log.debug("Rotated log file %s (exceeded max files)", f)
                except Exception:
                    log.warning("Failed to remove old log file %s", f)
            # refresh file list after deletion
            files = files[len(files) - max_files :]
        # Enforce max bytes limit
        max_bytes = int(os.getenv("LOG_MAX_BYTES", "0") or 0)
        if max_bytes > 0:
            total = sum(f.stat().st_size for f in files)
            idx = 0
            while total > max_bytes and idx < len(files):
                f = files[idx]
                try:
                    size = f.stat().st_size
                    f.unlink()
                    log.debug("Rotated log file %s (exceeded max bytes)", f)
                    total -= size
                except Exception:
                    log.warning("Failed to remove old log file %s", f)
                idx += 1
    except Exception:
        log.exception("Error while rotating log files in %s", storage_dir)


async def _process_new_message(update: TelegramUpdate, msg: TgMessage) -> None:
    """Process a new Telegram message or channel post.

    This function mirrors the original logic from ``handle_telegram_update``
    but adds persistent mapping and logging.  It respects the
    ``required_hashtag``, ``hashtag_allowlist``, and ``hashtag_blocklist``
    configuration values.
    """
    # Skip processing entirely if tg_skip is set
    if settings.tg_skip:
        log.info(
            "tg_skip enabled; logging update %s and skipping processing",
            update.update_id,
        )
        _record_update_log(update, tg_message_id=msg.message_id)
        return

    text = extract_message_text(update) or ""
    media_entries = collect_supported_media(msg)

    # Ignore empty messages
    if not text.strip() and not media_entries:
        log.info(
            "Message %s has no text or supported media; ignoring.", update.update_id
        )
        return

    # Hashtag-based filtering
    hashtags = extract_hashtags(text) if text else []
    if settings.required_hashtag:
        if settings.required_hashtag not in hashtags:
            log.info(
                "Message %s skipped: required hashtag %r missing (found: %s)",
                update.update_id,
                settings.required_hashtag,
                hashtags,
            )
            return
        log.info(
            "Message %s contains required hashtag %r; processing",
            update.update_id,
            settings.required_hashtag,
        )
    allowlist = getattr(settings, "hashtag_allowlist", None)
    if allowlist:
        if not any(tag in hashtags for tag in allowlist):
            log.info(
                "Message %s skipped: no allowed hashtags present (allowed: %s)",
                update.update_id,
                allowlist,
            )
            return
    blocklist = getattr(settings, "hashtag_blocklist", None)
    if blocklist and any(tag in hashtags for tag in blocklist):
        log.info(
            "Message %s skipped: blocked hashtag present (blocked: %s)",
            update.update_id,
            blocklist,
        )
        return

    # Build post title and slug
    title = build_title_from_text(text)
    slug = build_slug_from_text(text)
    content_html = text_to_html(text) if text.strip() else ""

    # Idempotency: Telegram may deliver duplicates; avoid creating multiple posts.
    mapping = _load_mapping()
    media_group_key = _media_group_mapping_key(msg)
    existing_wp_id = mapping.get(str(msg.message_id))
    if existing_wp_id is None and media_group_key:
        existing_wp_id = mapping.get(media_group_key)
    if existing_wp_id:
        if media_group_key and str(msg.message_id) not in mapping:
            # Merge later media-group parts into the original WordPress post.
            media_wp_paths: List[str] = []
            uploaded: List[Tuple[TelegramMedia, Any]] = []
            for media in media_entries:
                log.info(
                    "Processing media-group continuation type=%s file_id=%s",
                    media.media_type,
                    media.file_id,
                )
                if settings.wp_skip:
                    media_wp_paths.append(
                        f"wp/{media.media_type}/{media.file_name or media.file_id}"
                    )
                    continue
                try:
                    media_info = await _upload_single_media(media)
                    if media_info:
                        uploaded.append((media, media_info))
                        if getattr(media_info, "source_url", None):
                            media_wp_paths.append(str(getattr(media_info, "source_url")))
                        else:
                            media_wp_paths.append(f"wp/media/{media_info.id}")
                except Exception:
                    log.exception(
                        "Failed to process media-group continuation media %s",
                        media.file_id,
                    )

            wp_result: Optional[Dict[str, Any]] = None
            if settings.wp_skip:
                wp_result = {"id": int(existing_wp_id)}
            elif uploaded:
                use_featured = getattr(settings, "wp_use_featured_media", True)
                featured_media_id: Optional[int] = None
                featured_item_for_fallback: List[Tuple[TelegramMedia, Any]] = []
                gallery_items = uploaded
                if use_featured:
                    try:
                        current_featured = await get_wp_post_featured_media(
                            int(existing_wp_id)
                        )
                    except Exception:
                        log.exception(
                            "Failed to inspect featured media for WP post id=%s",
                            existing_wp_id,
                        )
                        current_featured = None
                    if current_featured is None:
                        preview_media = _extract_video_preview_media(msg)
                        if preview_media:
                            try:
                                preview_upload = await _upload_single_media(preview_media)
                                if preview_upload:
                                    featured_media_id = getattr(preview_upload, "id", None)
                            except Exception:
                                log.exception(
                                    "Failed to upload video preview for featured media on post id=%s",
                                    existing_wp_id,
                                )
                        if featured_media_id is None:
                            first_media = uploaded[0][1]
                            featured_media_id = getattr(first_media, "id", None)
                            if featured_media_id:
                                featured_item_for_fallback = [uploaded[0]]
                                gallery_items = uploaded[1:]
                media_markup = _build_media_gallery(gallery_items)
                try:
                    current_content = await get_wp_post_content(int(existing_wp_id))
                    merged_content = (
                        f"{current_content}{media_markup}"
                        if current_content
                        else media_markup
                    )
                    post = await update_wp_post(
                        post_id=int(existing_wp_id),
                        content_html=merged_content,
                        media_ids=[featured_media_id] if featured_media_id else None,
                    )
                    wp_result = post.model_dump(mode="json")
                    if featured_media_id and featured_item_for_fallback:
                        confirmed_featured = await get_wp_post_featured_media(
                            int(existing_wp_id)
                        )
                        if confirmed_featured != featured_media_id:
                            log.warning(
                                "Featured media assignment did not stick for post id=%s; appending first media to content instead",
                                existing_wp_id,
                            )
                            fallback_markup = _build_media_gallery(featured_item_for_fallback)
                            patched_content = f"{merged_content}{fallback_markup}"
                            post = await update_wp_post(
                                post_id=int(existing_wp_id),
                                content_html=patched_content,
                            )
                            wp_result = post.model_dump(mode="json")
                except Exception:
                    log.exception(
                        "Failed to merge media-group continuation into WP post id=%s",
                        existing_wp_id,
                    )

            mapping[str(msg.message_id)] = int(existing_wp_id)
            mapping[media_group_key] = int(existing_wp_id)
            _save_mapping(mapping)
            paths = _record_update_log(
                update, wp_result=wp_result, tg_message_id=msg.message_id
            )
            _log_semantic_summary(
                kind="MediaGroupContinuation",
                tgid=msg.message_id,
                title=title,
                slug=slug,
                text=text,
                media=media_entries,
                media_wp_paths=media_wp_paths,
                wp_post_id=int(existing_wp_id),
                tg_log_path=paths.get("tg_path"),
                wp_log_path=paths.get("wp_path"),
                status="MERGED (media_group continuation)",
            )
            return

        mapping[str(msg.message_id)] = int(existing_wp_id)
        if media_group_key:
            mapping[media_group_key] = int(existing_wp_id)
        _save_mapping(mapping)
        paths = _record_update_log(update, tg_message_id=msg.message_id)
        status = "SKIPPED (already mirrored)"
        if media_group_key:
            status = "SKIPPED (media_group already mirrored)"
        _log_semantic_summary(
            kind="DuplicateMessage",
            tgid=msg.message_id,
            title=title,
            slug=slug,
            text=text,
            media=media_entries,
            media_wp_paths=[],
            wp_post_id=existing_wp_id,
            tg_log_path=paths.get("tg_path"),
            wp_log_path=paths.get("wp_path"),
            status=status,
        )
        return

    media_ids: List[int] = []
    uploaded: List[Tuple[TelegramMedia, Any]] = []
    media_wp_paths: List[str] = []
    # Download and upload media to WordPress (unless wp_skip)
    for media in media_entries:
        log.info(
            "Processing Telegram media type=%s file_id=%s",
            media.media_type,
            media.file_id,
        )
        if settings.wp_skip:
            media_wp_paths.append(
                f"wp/{media.media_type}/{media.file_name or media.file_id}"
            )
            continue
        try:
            media_info = await _upload_single_media(media)
            if media_info:
                media_ids.append(media_info.id)
                uploaded.append((media, media_info))
                if getattr(media_info, "source_url", None):
                    media_wp_paths.append(str(getattr(media_info, "source_url")))
                else:
                    media_wp_paths.append(f"wp/media/{media_info.id}")
        except Exception:
            log.exception("Failed to process media %s", media.file_id)

    # Determine featured media vs gallery
    use_featured = getattr(settings, "wp_use_featured_media", True)
    featured_id: Optional[int] = None
    featured_from_uploaded_item = False
    featured_item_for_fallback: List[Tuple[TelegramMedia, Any]] = []
    gallery_items = uploaded
    if use_featured and uploaded:
        preview_media = _extract_video_preview_media(msg)
        if preview_media and not settings.wp_skip:
            try:
                preview_upload = await _upload_single_media(preview_media)
                if preview_upload:
                    featured_id = getattr(preview_upload, "id", None)
            except Exception:
                log.exception("Failed to upload video preview for featured media")
        if featured_id is None:
            first_media = uploaded[0][1]
            featured_id = getattr(first_media, "id", None)
            featured_from_uploaded_item = featured_id is not None
        if featured_id:
            if featured_from_uploaded_item:
                featured_item_for_fallback = [uploaded[0]]
                gallery_items = uploaded[1:]
    if featured_id:
        media_ids = [featured_id]

    # Compose HTML with media gallery (same semantics as the legacy app.py version)
    media_markup = ""
    if not settings.wp_skip:
        media_markup = _build_media_gallery(gallery_items)
    if media_markup:
        content_html = f"{content_html}{media_markup}" if content_html else media_markup

    # Create or simulate WP post
    wp_result: Optional[Dict[str, Any]] = None
    paths: Dict[str, Optional[str]] = {"tg_path": None, "wp_path": None}
    if settings.wp_skip:
        log.info(
            "wp_skip enabled; would create WP post with title=%r, slug=%r", title, slug
        )
        # Simulate a WordPress response
        pseudo_id = int(msg.message_id)
        wp_result = {
            "id": pseudo_id,
            "title": {"rendered": title},
            "content": {"rendered": content_html},
            "slug": slug,
        }
        # Still record mapping in skip mode to support edit-message simulations.
        mapping[str(msg.message_id)] = pseudo_id
        if media_group_key:
            mapping[media_group_key] = pseudo_id
        _save_mapping(mapping)
    else:
        try:
            post = await create_wp_post(
                title=title,
                content_html=content_html,
                media_ids=media_ids if featured_id else None,
                slug=slug,
            )
            wp_result = post.model_dump(mode="json")
            if featured_id and featured_item_for_fallback:
                created_featured = wp_result.get("featured_media")
                if created_featured is None and not settings.wp_skip:
                    try:
                        created_featured = await get_wp_post_featured_media(post.id)
                    except Exception:
                        log.exception(
                            "Failed to verify featured media for post id=%s after creation",
                            post.id,
                        )
                if created_featured != featured_id:
                    log.warning(
                        "Featured media assignment did not stick for post id=%s; appending first media to content instead",
                        post.id,
                    )
                    fallback_markup = _build_media_gallery(featured_item_for_fallback)
                    patched_content = (
                        f"{content_html}{fallback_markup}"
                        if content_html
                        else fallback_markup
                    )
                    post = await update_wp_post(
                        post_id=post.id,
                        content_html=patched_content,
                    )
                    wp_result = post.model_dump(mode="json")
            mapping[str(msg.message_id)] = post.id
            if media_group_key:
                mapping[media_group_key] = post.id
            _save_mapping(mapping)
        except Exception:
            log.exception("Failed to create WP post for message %s", msg.message_id)

    # Record log after processing
    paths = _record_update_log(
        update, wp_result=wp_result, tg_message_id=msg.message_id
    )
    _log_semantic_summary(
        kind="NewMessage",
        tgid=msg.message_id,
        title=title,
        slug=slug,
        text=text,
        media=media_entries,
        media_wp_paths=media_wp_paths,
        wp_post_id=(wp_result.get("id") if wp_result else None) if wp_result else None,
        tg_log_path=paths.get("tg_path"),
        wp_log_path=paths.get("wp_path"),
        status="SUCCESS" if wp_result else "FAILED",
    )


async def _process_edited_message(update: TelegramUpdate, msg: TgMessage) -> None:
    """Process an edited Telegram message or channel post.

    Attempts to find the corresponding WordPress post via the message→post
    mapping.  If found, updates the post title and content.  If not
    found, logs the event and stores the update for future reference.
    """
    # Skip entirely if tg_skip
    if settings.tg_skip:
        log.info(
            "tg_skip enabled; logging edited update %s and skipping", update.update_id
        )
        _record_update_log(update, tg_message_id=msg.message_id)
        return

    text = extract_message_text(update) or ""
    title = build_title_from_text(text)
    slug = build_slug_from_text(text)
    content_html = text_to_html(text) if text.strip() else ""

    # Look up WordPress post ID
    mapping = _load_mapping()
    wp_id = mapping.get(str(msg.message_id))
    if not wp_id:
        media_group_key = _media_group_mapping_key(msg)
        if media_group_key:
            wp_id = mapping.get(media_group_key)
    if not wp_id:
        log.warning(
            "Edited message %s has no known WordPress post mapping; storing update only",
            msg.message_id,
        )
        paths = _record_update_log(update, tg_message_id=msg.message_id)
        _log_semantic_summary(
            kind="EditedMessage",
            tgid=msg.message_id,
            title=title,
            slug=slug,
            text=text,
            media=[],
            media_wp_paths=[],
            wp_post_id=None,
            tg_log_path=paths.get("tg_path"),
            wp_log_path=paths.get("wp_path"),
            status="SKIPPED (no mapping)",
        )
        return

    # Update WP post if not skipping
    wp_result: Optional[Dict[str, Any]] = None
    if settings.wp_skip:
        log.info(
            "wp_skip enabled; would update WP post id=%s with title=%r", wp_id, title
        )
        wp_result = {
            "id": wp_id,
            "title": {"rendered": title},
            "content": {"rendered": content_html},
            "slug": slug,
        }
    else:
        try:
            post = await update_wp_post(
                post_id=wp_id,
                title=title,
                content_html=content_html,
                slug=slug,
            )
            wp_result = post.model_dump(mode="json")
        except Exception:
            log.exception("Failed to update WP post id=%s", wp_id)
    # Record logs
    paths = _record_update_log(update, wp_result, tg_message_id=msg.message_id)
    _log_semantic_summary(
        kind="EditedMessage",
        tgid=msg.message_id,
        title=title,
        slug=slug,
        text=text,
        media=[],
        media_wp_paths=[],
        wp_post_id=wp_id,
        tg_log_path=paths.get("tg_path"),
        wp_log_path=paths.get("wp_path"),
        status="SUCCESS" if wp_result else "FAILED",
    )


# Register handlers with dispatcher


@register_handler(UpdateKind.message)
@register_handler(UpdateKind.channel_post)
async def handle_new_message(update: TelegramUpdate, payload: Any) -> None:
    """Handler for new messages and channel posts."""
    if not isinstance(payload, TgMessage):
        log.warning(
            "Expected TgMessage payload for update %s, got %r",
            update.update_id,
            type(payload),
        )
        return
    await _process_new_message(update, payload)


@register_handler(UpdateKind.edited_message)
@register_handler(UpdateKind.edited_channel_post)
async def handle_edited_message(update: TelegramUpdate, payload: Any) -> None:
    """Handler for edited messages and channel posts."""
    if not isinstance(payload, TgMessage):
        log.warning(
            "Expected TgMessage payload for edited update %s, got %r",
            update.update_id,
            type(payload),
        )
        return
    await _process_edited_message(update, payload)
