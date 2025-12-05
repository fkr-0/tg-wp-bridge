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


class TgMessage(BaseModel):
    message_id: int
    chat: TgChat
    text: Optional[str] = None
    caption: Optional[str] = None
    photo: Optional[List[TgPhotoSize]] = None

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
    ok: bool
    result: Dict[str, Any]

    model_config = ConfigDict(extra="allow")
