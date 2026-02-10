import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_media_group_messages_map_to_single_wp_post(tmp_path, monkeypatch, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # noqa: F401  # ensure handlers are registered
    from tg_wp_bridge.schemas import TgMessage, TgChat, TgVideo
    from tg_wp_bridge.update_model import TelegramUpdate

    storage = tmp_path / "logs"
    mapping_file = tmp_path / "message_map.json"
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(mapping_file))

    chat = TgChat(id=-1003610084567, type="supergroup")

    first = TelegramUpdate(
        update_id=1,
        message=TgMessage(
            message_id=108,
            date=1770727032,
            chat=chat,
            caption="album caption",
            media_group_id="14165816262638850",
        ),
    )
    second = TelegramUpdate(
        update_id=2,
        message=TgMessage(
            message_id=109,
            date=1770727032,
            chat=chat,
            video=TgVideo(file_id="video109", file_name="clip.mp4", mime_type="video/mp4"),
            media_group_id="14165816262638850",
        ),
    )

    with temp_settings(
        wp_skip=True,
        tg_skip=False,
        chat_type_allowlist=("channel", "supergroup"),
    ):
        await dispatch_update(first)
        await dispatch_update(second)

    mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
    assert mapping["108"] == 108
    assert mapping["109"] == 108
    assert mapping["mg:-1003610084567:14165816262638850"] == 108

    wp_logs = sorted(storage.glob("*_wp_*.json"))
    assert len(wp_logs) == 2
    wp_payloads = [json.loads(Path(p).read_text(encoding="utf-8")) for p in wp_logs]
    assert all(payload["id"] == 108 for payload in wp_payloads)
