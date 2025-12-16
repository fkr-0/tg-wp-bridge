#!/usr/bin/env python3
"""
Pydantic models for external I/O:

- Telegram update / message subset
- WordPress responses (minimal typing where useful)
"""

from typing import List, Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, HttpUrl


# ---------------------------------------------------------------------------
# Telegram models (subset, enough for our use case)
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


class TgVideo(TgFileBase):
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None


class TgAnimation(TgFileBase):
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None


class TgDocument(TgFileBase):
    pass


class TgMessage(BaseModel):
    message_id: int
    chat: TgChat
    text: Optional[str] = None
    caption: Optional[str] = None
    photo: Optional[List[TgPhotoSize]] = None
    video: Optional[TgVideo] = None
    animation: Optional[TgAnimation] = None
    document: Optional[TgDocument] = None

    model_config = ConfigDict(extra="allow")


class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TgMessage] = None
    channel_post: Optional[TgMessage] = None

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# WordPress models (minimal, primarily for clarity)
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
