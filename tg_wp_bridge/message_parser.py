"""
Helpers to extract relevant data from Telegram updates/messages.

Pure functions only – no network or IO here.
"""

from typing import Optional, List

from .schemas import TelegramUpdate, TgMessage, TgPhotoSize


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

        # Truncate to max_length AFTER processing
        if len(candidate) > max_length:
            candidate = candidate[:max_length]

        return candidate

    return "(no title)"


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
