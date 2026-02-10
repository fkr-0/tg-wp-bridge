"""
Enhanced Telegram update model and update kind enumeration.

This module defines :class:`UpdateKind` and :class:`TelegramUpdate` to
provide an exhaustive representation of Telegram Bot API updates as of
mid‑2024.  It uses an enum to represent the mutually exclusive fields
on the update and exposes a helper method :meth:`TelegramUpdate.get_payload`
to retrieve the payload and set the update's kind.

These classes are defined in a separate module to avoid interfering
with the existing structures in ``schemas.py``.  Consumers should
import :class:`TelegramUpdate` and :class:`UpdateKind` from this module
instead of ``tg_wp_bridge.schemas`` when using the dispatcher.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Any, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .schemas import TgMessage

# Import TgMessage if available. Do not fail hard if the gigantic Telegram
# schema subset does not define every optional type we might want to refer to.
try:
    from .schemas import TgMessage  # type: ignore
except Exception:  # pragma: no cover
    TgMessage = Any  # type: ignore


class UpdateKind(str, Enum):
    """Enumeration of Telegram update kinds."""

    message = "message"
    edited_message = "edited_message"
    channel_post = "channel_post"
    edited_channel_post = "edited_channel_post"
    business_connection = "business_connection"
    business_message = "business_message"
    edited_business_message = "edited_business_message"
    deleted_business_messages = "deleted_business_messages"
    message_reaction = "message_reaction"
    message_reaction_count = "message_reaction_count"
    inline_query = "inline_query"
    chosen_inline_result = "chosen_inline_result"
    callback_query = "callback_query"
    shipping_query = "shipping_query"
    pre_checkout_query = "pre_checkout_query"
    purchased_paid_media = "purchased_paid_media"
    poll = "poll"
    poll_answer = "poll_answer"
    my_chat_member = "my_chat_member"
    chat_member = "chat_member"
    chat_join_request = "chat_join_request"
    chat_boost = "chat_boost"
    removed_chat_boost = "removed_chat_boost"


class TelegramUpdate(BaseModel):
    """Comprehensive Telegram update model.

    All fields defined in the Telegram Bot API Update object are
    represented as optional attributes.  Exactly one of these will be
    populated for any given update (exclusive optional).  The helper
    method :meth:`get_payload` returns the populated payload and sets
    the :attr:`kind` accordingly.
    """

    update_id: int

    # Exclusive-optional fields
    message: Optional[TgMessage] = None
    edited_message: Optional[TgMessage] = None
    channel_post: Optional[TgMessage] = None
    edited_channel_post: Optional[TgMessage] = None
    business_connection: Optional[dict] = None  # not modelled fully
    business_message: Optional[TgMessage] = None
    edited_business_message: Optional[TgMessage] = None
    deleted_business_messages: Optional[dict] = None
    message_reaction: Optional[dict] = None
    message_reaction_count: Optional[dict] = None
    inline_query: Optional[dict] = None
    chosen_inline_result: Optional[dict] = None
    callback_query: Optional[dict] = None
    shipping_query: Optional[dict] = None
    pre_checkout_query: Optional[dict] = None
    purchased_paid_media: Optional[dict] = None
    poll: Optional[dict] = None
    poll_answer: Optional[dict] = None
    my_chat_member: Optional[dict] = None
    chat_member: Optional[dict] = None
    chat_join_request: Optional[dict] = None
    chat_boost: Optional[dict] = None
    removed_chat_boost: Optional[dict] = None

    # Derived kind
    kind: Optional[UpdateKind] = None

    model_config = ConfigDict(extra="allow")

    def get_payload(self) -> Optional[object]:
        """Return the payload object and set :attr:`kind`.

        Iterates over :class:`UpdateKind` members and returns the
        corresponding attribute if non-null.  If found, sets
        :attr:`kind`.  Otherwise returns ``None`` and leaves
        :attr:`kind` unchanged.
        """
        for k in UpdateKind:
            value = getattr(self, k.value, None)
            if value is not None:
                self.kind = k
                return value
        return None
