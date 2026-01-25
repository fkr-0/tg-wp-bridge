#!/usr/bin/env python3
"""
Pydantic models for external I/O:

- Telegram update / message subset
- WordPress responses (minimal typing where useful)
"""

from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, ConfigDict, HttpUrl

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


# class TgMessage(BaseModel):
#     message_id: int
#     chat: TgChat
#     text: Optional[str] = None
#     caption: Optional[str] = None
#     photo: Optional[List[TgPhotoSize]] = None
#     video: Optional[TgVideo] = None
#     animation: Optional[TgAnimation] = None
#     document: Optional[TgDocument] = None

#     model_config = ConfigDict(extra="allow")

# Update

please provide an enhanced TelegramUpdate model with more fields as per Telegram Bot API documentation.
Do also model the exclusive-optional parameters as an enum "subtyping" the update.
# This object represents an incoming update.
# At most one of the optional parameters can be present in any given update.
# Field 	Type 	Description
# update_id 	Integer 	The update's unique identifier. Update identifiers start from a certain positive number and increase sequentially. This identifier becomes especially handy if you're using webhooks, since it allows you to ignore repeated updates or to restore the correct update sequence, should they get out of order. If there are no new updates for at least a week, then identifier of the next update will be chosen randomly instead of sequentially.
# message 	Message 	Optional. New incoming message of any kind - text, photo, sticker, etc.
# edited_message 	Message 	Optional. New version of a message that is known to the bot and was edited. This update may at times be triggered by changes to message fields that are either unavailable or not actively used by your bot.
# channel_post 	Message 	Optional. New incoming channel post of any kind - text, photo, sticker, etc.
# edited_channel_post 	Message 	Optional. New version of a channel post that is known to the bot and was edited. This update may at times be triggered by changes to message fields that are either unavailable or not actively used by your bot.
# business_connection 	BusinessConnection 	Optional. The bot was connected to or disconnected from a business account, or a user edited an existing connection with the bot
# business_message 	Message 	Optional. New message from a connected business account
# edited_business_message 	Message 	Optional. New version of a message from a connected business account
# deleted_business_messages 	BusinessMessagesDeleted 	Optional. Messages were deleted from a connected business account
# message_reaction 	MessageReactionUpdated 	Optional. A reaction to a message was changed by a user. The bot must be an administrator in the chat and must explicitly specify "message_reaction" in the list of allowed_updates to receive these updates. The update isn't received for reactions set by bots.
# message_reaction_count 	MessageReactionCountUpdated 	Optional. Reactions to a message with anonymous reactions were changed. The bot must be an administrator in the chat and must explicitly specify "message_reaction_count" in the list of allowed_updates to receive these updates. The updates are grouped and can be sent with delay up to a few minutes.
# inline_query 	InlineQuery 	Optional. New incoming inline query
# chosen_inline_result 	ChosenInlineResult 	Optional. The result of an inline query that was chosen by a user and sent to their chat partner. Please see our documentation on the feedback collecting for details on how to enable these updates for your bot.
# callback_query 	CallbackQuery 	Optional. New incoming callback query
# shipping_query 	ShippingQuery 	Optional. New incoming shipping query. Only for invoices with flexible price
# pre_checkout_query 	PreCheckoutQuery 	Optional. New incoming pre-checkout query. Contains full information about checkout
# purchased_paid_media 	PaidMediaPurchased 	Optional. A user purchased paid media with a non-empty payload sent by the bot in a non-channel chat
# poll 	Poll 	Optional. New poll state. Bots receive only updates about manually stopped polls and polls, which are sent by the bot
# poll_answer 	PollAnswer 	Optional. A user changed their answer in a non-anonymous poll. Bots receive new votes only in polls that were sent by the bot itself.
# my_chat_member 	ChatMemberUpdated 	Optional. The bot's chat member status was updated in a chat. For private chats, this update is received only when the bot is blocked or unblocked by the user.
# chat_member 	ChatMemberUpdated 	Optional. A chat member's status was updated in a chat. The bot must be an administrator in the chat and must explicitly specify "chat_member" in the list of allowed_updates to receive these updates.
# chat_join_request 	ChatJoinRequest 	Optional. A request to join the chat has been sent. The bot must have the can_invite_users administrator right in the chat to receive these updates.
# chat_boost 	ChatBoostUpdated 	Optional. A chat boost was added or changed. The bot must be an administrator in the chat to receive these updates.
# removed_chat_boost 	ChatBoostRemoved 	Optional. A boost was removed from a chat. The bot must be an administrator in the chat to receive these updates.
class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TgMessage] = None
    channel_post: Optional[TgMessage] = None

    model_config = ConfigDict(extra="allow")
*** Enhanced ~TelegramUpdate~ Model with Exclusive-Optional Enum

#+BEGIN_QUOTE
This model covers all fields from the Telegram Bot API Update object (as of June 2024).
It uses an Enum to represent the exclusive-optional "kind" of update, and a union for the payload.
#+END_QUOTE

#+BEGIN_SRC python
from typing import Optional, Union
from enum import Enum
from pydantic import BaseModel, ConfigDict

# --- Forward references for type hints (define these elsewhere) ---
# from .schemas import TgMessage, Poll, PollAnswer, TgChat, etc.

class UpdateKind(str, Enum):
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
    update_id: int

    # Exclusive-optional payloads (at most one present)
    message: Optional["TgMessage"] = None
    edited_message: Optional["TgMessage"] = None
    channel_post: Optional["TgMessage"] = None
    edited_channel_post: Optional["TgMessage"] = None
    business_connection: Optional["BusinessConnection"] = None
    business_message: Optional["TgMessage"] = None
    edited_business_message: Optional["TgMessage"] = None
    deleted_business_messages: Optional["BusinessMessagesDeleted"] = None
    message_reaction: Optional["MessageReactionUpdated"] = None
    message_reaction_count: Optional["MessageReactionCountUpdated"] = None
    inline_query: Optional["InlineQuery"] = None
    chosen_inline_result: Optional["ChosenInlineResult"] = None
    callback_query: Optional["CallbackQuery"] = None
    shipping_query: Optional["ShippingQuery"] = None
    pre_checkout_query: Optional["PreCheckoutQuery"] = None
    purchased_paid_media: Optional["PaidMediaPurchased"] = None
    poll: Optional["Poll"] = None
    poll_answer: Optional["PollAnswer"] = None
    my_chat_member: Optional["ChatMemberUpdated"] = None
    chat_member: Optional["ChatMemberUpdated"] = None
    chat_join_request: Optional["ChatJoinRequest"] = None
    chat_boost: Optional["ChatBoostUpdated"] = None
    removed_chat_boost: Optional["ChatBoostRemoved"] = None

    # Enum to indicate which field is present (optional, for convenience)
    kind: Optional[UpdateKind] = None

    model_config = ConfigDict(extra="allow")

    def get_payload(self) -> Optional[object]:
        """
        Return the payload object and set kind accordingly.
        """
        for kind in UpdateKind:
            value = getattr(self, kind.value, None)
            if value is not None:
                self.kind = kind
                return value
        return None


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


class TgMessage(BaseModel):
    message_id: int
    message_thread_id: Optional[int] = None
    direct_messages_topic: Optional["DirectMessagesTopic"] = None
    from_: Optional["TgUser"] = None  # 'from' is a reserved keyword in Python
    sender_chat: Optional["TgChat"] = None
    sender_boost_count: Optional[int] = None
    sender_business_bot: Optional["TgUser"] = None
    date: int
    business_connection_id: Optional[str] = None
    chat: "TgChat"
    forward_origin: Optional["MessageOrigin"] = None
    is_topic_message: Optional[bool] = None
    is_automatic_forward: Optional[bool] = None
    reply_to_message: Optional["TgMessage"] = None
    external_reply: Optional["ExternalReplyInfo"] = None
    quote: Optional["TextQuote"] = None
    reply_to_story: Optional["Story"] = None
    reply_to_checklist_task_id: Optional[int] = None
    via_bot: Optional["TgUser"] = None
    edit_date: Optional[int] = None
    has_protected_content: Optional[bool] = None
    is_from_offline: Optional[bool] = None
    is_paid_post: Optional[bool] = None
    media_group_id: Optional[str] = None
    author_signature: Optional[str] = None
    paid_star_count: Optional[int] = None
    text: Optional[str] = None
    entities: Optional[List["MessageEntity"]] = None
    link_preview_options: Optional["LinkPreviewOptions"] = None
    suggested_post_info: Optional["SuggestedPostInfo"] = None
    effect_id: Optional[str] = None
    animation: Optional["TgAnimation"] = None
    audio: Optional["TgAudio"] = None
    document: Optional["TgDocument"] = None
    paid_media: Optional["PaidMediaInfo"] = None
    photo: Optional[List["TgPhotoSize"]] = None
    sticker: Optional["Sticker"] = None
    story: Optional["Story"] = None
    video: Optional["TgVideo"] = None
    video_note: Optional["VideoNote"] = None
    voice: Optional["Voice"] = None
    caption: Optional[str] = None
    caption_entities: Optional[List["MessageEntity"]] = None
    show_caption_above_media: Optional[bool] = None
    has_media_spoiler: Optional[bool] = None
    checklist: Optional["Checklist"] = None
    contact: Optional["Contact"] = None
    dice: Optional["Dice"] = None
    game: Optional["Game"] = None
    poll: Optional["Poll"] = None
    venue: Optional["Venue"] = None
    location: Optional["Location"] = None
    new_chat_members: Optional[List["TgUser"]] = None
    left_chat_member: Optional["TgUser"] = None
    new_chat_title: Optional[str] = None
    new_chat_photo: Optional[List["TgPhotoSize"]] = None
    delete_chat_photo: Optional[bool] = None
    group_chat_created: Optional[bool] = None
    supergroup_chat_created: Optional[bool] = None
    channel_chat_created: Optional[bool] = None
    message_auto_delete_timer_changed: Optional["MessageAutoDeleteTimerChanged"] = None
    migrate_to_chat_id: Optional[int] = None
    migrate_from_chat_id: Optional[int] = None
    pinned_message: Optional["MaybeInaccessibleMessage"] = None
    invoice: Optional["Invoice"] = None
    successful_payment: Optional["SuccessfulPayment"] = None
    refunded_payment: Optional["RefundedPayment"] = None
    users_shared: Optional["UsersShared"] = None
    chat_shared: Optional["ChatShared"] = None
    gift: Optional["GiftInfo"] = None
    unique_gift: Optional["UniqueGiftInfo"] = None
    gift_upgrade_sent: Optional["GiftInfo"] = None
    connected_website: Optional[str] = None
    write_access_allowed: Optional["WriteAccessAllowed"] = None
    passport_data: Optional["PassportData"] = None
    proximity_alert_triggered: Optional["ProximityAlertTriggered"] = None
    boost_added: Optional["ChatBoostAdded"] = None
    chat_background_set: Optional["ChatBackground"] = None
    checklist_tasks_done: Optional["ChecklistTasksDone"] = None
    checklist_tasks_added: Optional["ChecklistTasksAdded"] = None
    direct_message_price_changed: Optional["DirectMessagePriceChanged"] = None
    forum_topic_created: Optional["ForumTopicCreated"] = None
    forum_topic_edited: Optional["ForumTopicEdited"] = None
    forum_topic_closed: Optional["ForumTopicClosed"] = None
    forum_topic_reopened: Optional["ForumTopicReopened"] = None
    general_forum_topic_hidden: Optional["GeneralForumTopicHidden"] = None
    general_forum_topic_unhidden: Optional["GeneralForumTopicUnhidden"] = None
    giveaway_created: Optional["GiveawayCreated"] = None
    giveaway: Optional["Giveaway"] = None
    giveaway_winners: Optional["GiveawayWinners"] = None
    giveaway_completed: Optional["GiveawayCompleted"] = None
    paid_message_price_changed: Optional["PaidMessagePriceChanged"] = None
    suggested_post_approved: Optional["SuggestedPostApproved"] = None
    suggested_post_approval_failed: Optional["SuggestedPostApprovalFailed"] = None
    suggested_post_declined: Optional["SuggestedPostDeclined"] = None
    suggested_post_paid: Optional["SuggestedPostPaid"] = None
    suggested_post_refunded: Optional["SuggestedPostRefunded"] = None
    video_chat_scheduled: Optional["VideoChatScheduled"] = None
    video_chat_started: Optional["VideoChatStarted"] = None
    video_chat_ended: Optional["VideoChatEnded"] = None
    video_chat_participants_invited: Optional["VideoChatParticipantsInvited"] = None
    web_app_data: Optional["WebAppData"] = None
    reply_markup: Optional["InlineKeyboardMarkup"] = None

    model_config = ConfigDict(extra="allow")
