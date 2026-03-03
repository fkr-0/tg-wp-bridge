"""
Event dispatcher for Telegram update types.

This module provides a simple decorator-based registration system for
handling different kinds of Telegram updates.  Each update kind is
represented by the :class:`UpdateKind` enum from ``tg_wp_bridge.schemas``.

Usage::

    from tg_wp_bridge.schemas import UpdateKind, TelegramUpdate
    from tg_wp_bridge.dispatcher import register_handler, dispatch_update

    @register_handler(UpdateKind.message)
    async def handle_new_message(update: TelegramUpdate, payload: TgMessage) -> None:
        ...

When an update arrives, call :func:`dispatch_update` with the
``TelegramUpdate`` instance.  The dispatcher will determine the
``update.kind`` and forward the update and its payload to the
registered handler.  If no handler is registered for the given kind,
the update is ignored.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

from .update_model import TelegramUpdate, UpdateKind

log = logging.getLogger("tg-wp-bridge.dispatcher")

HandlerFunc = Callable[[TelegramUpdate, Any], Awaitable[None]]

# Registry mapping update kinds to handler functions
_handlers: Dict[UpdateKind, HandlerFunc] = {}


def _resolve_writable_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except PermissionError:
        fallback = Path(
            os.getenv(
                "STORAGE_FALLBACK_DIR",
                str(Path(tempfile.gettempdir()) / "tg-wp-bridge" / "logs"),
            )
        )
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _record_dispatch_error(update: TelegramUpdate, exc: BaseException) -> None:
    storage_dir = _resolve_writable_dir(Path(os.getenv("STORAGE_DIR", "data/logs")))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    error_path = storage_dir / f"{ts}.error"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message_id": getattr(update.get_payload(), "message_id", None),
        "telegram_update": update.model_dump(mode="json", exclude_none=True),
        "wp_post": None,
        "exception": f"{type(exc).__name__}: {exc}",
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }
    try:
        with error_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    except Exception:
        log.exception("Failed to write dispatcher error artifact for update %s", update.update_id)


def clear_handlers() -> None:
    """Clear all registered handlers.

    Primarily useful for unit tests.
    """
    _handlers.clear()


def registered_handlers() -> Dict[UpdateKind, HandlerFunc]:
    """Return a copy of the handler registry."""
    return dict(_handlers)


def register_handler(kind: UpdateKind) -> Callable[[HandlerFunc], HandlerFunc]:
    """Decorator to register a coroutine function as the handler for an update kind.

    Args:
        kind: The :class:`UpdateKind` this handler should process.

    Returns:
        A decorator that registers the function in the dispatcher registry.
    """

    def decorator(fn: HandlerFunc) -> HandlerFunc:
        if kind in _handlers:
            log.warning("Overwriting existing handler for update kind %s", kind.value)
        _handlers[kind] = fn
        return fn

    return decorator


async def dispatch_update(update: TelegramUpdate) -> None:
    """Dispatch an incoming Telegram update to its registered handler.

    Determines the ``update.kind`` via ``get_payload()`` and forwards
    both the entire update and the extracted payload to the appropriate
    handler.  If no handler is registered for the update kind, the
    update is logged and ignored.

    Args:
        update: The incoming :class:`TelegramUpdate` instance.
    """

    payload = update.get_payload()
    kind = update.kind
    if kind is None:
        log.debug("Update %s has no kind; ignoring", update.update_id)
        return
    handler = _handlers.get(kind)
    if handler is None:
        log.info(
            "No handler registered for update kind %s; ignoring update %s",
            kind.value,
            update.update_id,
        )
        return
    try:
        await handler(update, payload)
    except Exception as exc:
        _record_dispatch_error(update, exc)
        log.exception(
            "Error while handling update %s of kind %s", update.update_id, kind.value
        )
