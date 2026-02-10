"""Pydantic models for external I/O.

This project only needs a **small** subset of the Telegram Bot API schema
to do its job: extract message text, detect a few media types, and track
the message and chat identifiers.

Keeping the schema minimal has two practical benefits:

1. Faster validation and easier tests.
2. Avoiding huge forward-reference graphs that require explicit
   ``model_rebuild()`` calls.

If you need additional Telegram fields later, extend these models in a
targeted way rather than pasting the full API schema.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, HttpUrl

# ---------------------------------------------------------------------------
# WordPress models
# ---------------------------------------------------------------------------


class WPMediaResponse(BaseModel):
    id: int
    source_url: Optional[HttpUrl] = None

    model_config = ConfigDict(extra="allow")


class WPPostResponse(BaseModel):
    id: int
    link: Optional[HttpUrl] = None
    title: Dict[str, Any]
    content: Dict[str, Any]

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Telegram models (minimal subset)
# ---------------------------------------------------------------------------


class TgChat(BaseModel):
    id: int
    type: str

    model_config = ConfigDict(extra="allow")


class TgPhotoSize(BaseModel):
    file_id: str
    width: int
    height: int

    model_config = ConfigDict(extra="allow")


class TgFileBase(BaseModel):
    file_id: str
    file_unique_id: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class TgThumbnail(BaseModel):
    file_id: str
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    file_unique_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class TgVideo(TgFileBase):
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    thumbnail: Optional[TgThumbnail] = None
    thumb: Optional[TgThumbnail] = None


class TgAnimation(TgFileBase):
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    thumbnail: Optional[TgThumbnail] = None
    thumb: Optional[TgThumbnail] = None


class TgDocument(TgFileBase):
    thumbnail: Optional[TgThumbnail] = None
    thumb: Optional[TgThumbnail] = None


class TgMessage(BaseModel):
    """Minimal Telegram message.

    Required for our bridge:
    - message_id, date, chat
    - text/caption
    - photo/video/animation/document (for media mirroring)
    """

    message_id: int
    date: int
    chat: TgChat

    text: Optional[str] = None
    caption: Optional[str] = None

    photo: Optional[List[TgPhotoSize]] = None
    video: Optional[TgVideo] = None
    animation: Optional[TgAnimation] = None
    document: Optional[TgDocument] = None

    model_config = ConfigDict(extra="allow")


class TelegramWebhookInfo(BaseModel):
    """Telegram webhook status model (mirrors getWebhookInfo result)."""

    url: Optional[str] = None
    has_custom_certificate: bool = False
    pending_update_count: int = 0
    ip_address: Optional[str] = None
    last_error_date: Optional[int] = None
    last_error_message: Optional[str] = None
    last_synchronization_error_date: Optional[int] = None
    max_connections: Optional[int] = None
    allowed_updates: Optional[List[str]] = None

    model_config = ConfigDict(extra="allow")
