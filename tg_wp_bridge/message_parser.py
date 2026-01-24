"""
Helpers to extract relevant data from Telegram updates/messages.

Pure functions only – no network or IO here.
"""

import re
from dataclasses import dataclass
from typing import Optional, List

# Emoji pattern - matches common Unicode emoji characters
# These ranges are carefully selected to avoid overlapping with CJK characters
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002600-\U000027BF"  # misc symbols and dingbats
    "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
    "\U0000FE0F"             # variation selector
    "\u200D"                 # zero width joiner (for compound emojis)
    "]+",
    flags=re.UNICODE,
)


def strip_emojis(text: str) -> str:
    """
    Remove all emoji characters from a string.

    This is useful for creating URL-safe slugs and permalinks where
    emojis might cause encoding issues.

    Args:
        text: The input string possibly containing emojis.

    Returns:
        The string with all emoji characters removed.
    """
    return _EMOJI_PATTERN.sub("", text).strip()

from .schemas import (
    TelegramUpdate,
    TgMessage,
    TgPhotoSize,
    TgVideo,
    TgAnimation,
    TgDocument,
)


@dataclass
class TelegramMedia:
    """Lightweight descriptor for supported Telegram media attachments."""

    file_id: str
    media_type: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None


def extract_message_entity(update: TelegramUpdate) -> Optional[TgMessage]:
    """
    Return the effective message (either `channel_post` or `message`)
    from a Telegram update.
    """
    return update.channel_post or update.message


def extract_message_text(update: TelegramUpdate) -> Optional[str]:
    """
    Extract text from an update, preferring message/channel_post.text
    and falling back to .caption.
    """
    msg = extract_message_entity(update)
    if not msg:
        return None

    return msg.text or msg.caption


def find_photo_with_max_size(msg: TgMessage) -> Optional[TgPhotoSize]:
    """
    From a TgMessage, pick the largest photo variant if present.

    Telegram sends multiple sizes of the same photo in msg.photo.
    """
    if not msg.photo:
        return None

    return max(msg.photo, key=lambda p: p.width * p.height)


def _add_media(
    media: List[TelegramMedia],
    seen_ids: set,
    *,
    file_id: Optional[str],
    media_type: str,
    file_name: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> None:
    if not file_id or file_id in seen_ids:
        return
    seen_ids.add(file_id)
    media.append(
        TelegramMedia(
            file_id=file_id,
            media_type=media_type,
            file_name=file_name,
            mime_type=mime_type,
        )
    )


def collect_supported_media(msg: TgMessage) -> List[TelegramMedia]:
    """Return a list of supported media descriptors for the message."""

    media: List[TelegramMedia] = []
    seen_ids: set = set()

    photo = find_photo_with_max_size(msg)
    if photo:
        _add_media(
            media,
            seen_ids,
            file_id=photo.file_id,
            media_type="photo",
            file_name=f"{photo.file_id}.jpg",
            mime_type="image/jpeg",
        )

    if isinstance(msg.video, TgVideo):
        _add_media(
            media,
            seen_ids,
            file_id=msg.video.file_id,
            media_type="video",
            file_name=msg.video.file_name,
            mime_type=msg.video.mime_type,
        )

    if isinstance(msg.animation, TgAnimation):
        _add_media(
            media,
            seen_ids,
            file_id=msg.animation.file_id,
            media_type="animation",
            file_name=msg.animation.file_name,
            mime_type=msg.animation.mime_type,
        )

    if isinstance(msg.document, TgDocument):
        _add_media(
            media,
            seen_ids,
            file_id=msg.document.file_id,
            media_type="document",
            file_name=msg.document.file_name,
            mime_type=msg.document.mime_type,
        )

    return media


def extract_hashtags(text: str) -> List[str]:
    """
    Extract hashtags from free text.

    Rules (simple but robust enough for blog mirroring):
    - A hashtag is any token starting with '#' and containing at least one
      non-'#' character.
    - Trailing punctuation like ',', '.', '!' is stripped.
    - Opening and closing punctuation is also stripped (e.g., '(', ')', '[', ']').
    - Returned in order of first appearance, without duplicates.
    """
    hashtags: List[str] = []
    seen = set()

    for raw_token in text.split():
        token = raw_token
        if not token.startswith("#"):
            continue
        # strip trailing and opening punctuation commonly attached to hashtags
        token = token.rstrip(".,!?:;)]}").lstrip("([{")
        # Also handle hashtags that might have opening punctuation before #
        if not token.startswith("#"):
            continue
        # Strip any remaining punctuation after the # processing
        token = token.rstrip(".,!?:;)]}([{")
        if token == "#" or len(token) < 2:
            continue
        if token not in seen:
            seen.add(token)
            hashtags.append(token)

    return hashtags


def build_title_from_text(text: str, max_length: int = 60) -> str:
    """
    Build a reasonable post title from the message text.

    Strategy:
    - Take the first non-empty line.
    - Drop leading hashtags from that line (e.g. '#blog #news Title here').
    - Strip emojis for cleaner titles.
    - Truncate to max_length characters.
    - Fallback: '(no title)'.
    """
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        words = line.split()
        filtered_words = []
        dropping_hashtags = True

        for w in words:
            if dropping_hashtags and w.startswith("#"):
                # skip early hashtags in the line
                continue
            dropping_hashtags = False
            filtered_words.append(w)

        candidate = " ".join(filtered_words) if filtered_words else line
        candidate = candidate.strip()
        if not candidate:
            continue

        # Strip emojis for cleaner titles
        candidate = strip_emojis(candidate)

        # Check if empty after stripping emojis (e.g., emoji-only text)
        if not candidate:
            continue

        # Truncate to max_length AFTER processing
        if len(candidate) > max_length:
            candidate = candidate[:max_length]

        return candidate

    return "(no title)"


def build_slug_from_text(text: str, max_length: int = 60) -> str:
    """
    Build a URL-safe slug from the message text.

    Strategy:
    - Extract title using build_title_from_text (which strips hashtags and emojis).
    - Convert to lowercase.
    - Replace non-ASCII characters with ASCII equivalents.
    - Replace spaces and non-alphanumeric characters with hyphens.
    - Remove consecutive hyphens.

    Returns a slug suitable for permalinks.
    """
    import unicodedata

    title = build_title_from_text(text, max_length=max_length)
    if not title or title == "(no title)":
        return "untitled"

    # Normalize Unicode to NFD and combine characters
    # Then remove combining marks (accents, etc.)
    normalized = unicodedata.normalize('NFKD', title)
    ascii_title = ''.join(
        c for c in normalized
        if not unicodedata.combining(c) and c.isalnum() or c.isspace()
    )

    # Convert to lowercase
    slug = ascii_title.lower().strip()

    # Replace spaces and special chars with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Ensure we don't return empty string
    return slug if slug else "untitled"


def text_to_html(text: str) -> str:
    """
    Convert plain text to simple HTML:

    - Double newlines create new paragraphs.
    - Single newlines within a paragraph are converted to <br>.
    - Output is one or more <p>...</p> blocks with minimal markup.
    """
    stripped = text.strip()
    if not stripped:
        return "<p></p>"

    paragraphs = stripped.split("\n\n")
    html_paragraphs = []

    for para in paragraphs:
        lines = para.split("\n")
        joined = "<br>".join(line for line in lines)
        html_paragraphs.append(f"<p>{joined}</p>")

    return "".join(html_paragraphs)
