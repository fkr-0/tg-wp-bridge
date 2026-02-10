from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_media_group_continuation_updates_first_wp_post(tmp_path, monkeypatch, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # noqa: F401  # ensure handlers are registered
    from tg_wp_bridge.schemas import TgChat, TgMessage, TgVideo, WPPostResponse, WPMediaResponse
    from tg_wp_bridge.update_model import TelegramUpdate

    storage = tmp_path / "logs"
    mapping_file = tmp_path / "message_map.json"
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(mapping_file))

    chat = TgChat(id=-1003610084567, type="supergroup")

    first = TelegramUpdate(
        update_id=1,
        message=TgMessage(
            message_id=112,
            date=1770727032,
            chat=chat,
            caption="Testertest",
            media_group_id="14165816262638850",
        ),
    )
    second = TelegramUpdate(
        update_id=2,
        message=TgMessage(
            message_id=113,
            date=1770727032,
            chat=chat,
            video=TgVideo(file_id="vid113", file_name="clip.mp4", mime_type="video/mp4"),
            media_group_id="14165816262638850",
        ),
    )

    with (
        temp_settings(
            wp_skip=False,
            tg_skip=False,
            chat_type_allowlist=("channel", "supergroup"),
        ),
        patch("tg_wp_bridge.handlers.create_wp_post", new_callable=AsyncMock) as mock_create,
        patch("tg_wp_bridge.handlers.get_file_direct_url", new_callable=AsyncMock) as mock_file_url,
        patch("tg_wp_bridge.handlers.download_file", new_callable=AsyncMock) as mock_download,
        patch("tg_wp_bridge.handlers.upload_media_to_wp", new_callable=AsyncMock) as mock_upload,
        patch("tg_wp_bridge.handlers.get_wp_post_content", new_callable=AsyncMock) as mock_get_content,
        patch("tg_wp_bridge.handlers.update_wp_post", new_callable=AsyncMock) as mock_update,
    ):
        mock_create.return_value = WPPostResponse(
            id=58,
            title={"rendered": "Testertest"},
            content={"rendered": "<p>Testertest</p>"},
        )
        mock_file_url.return_value = "https://telegram.example/file.mp4"
        mock_download.return_value = b"video-bytes"
        mock_upload.return_value = WPMediaResponse(
            id=57,
            source_url="https://example.com/uploads/clip.mp4",
        )
        mock_get_content.return_value = "<p>Testertest</p>"
        mock_update.return_value = WPPostResponse(
            id=58,
            title={"rendered": "Testertest"},
            content={"rendered": "<p>Testertest</p><figure>...</figure>"},
        )

        await dispatch_update(first)
        await dispatch_update(second)

        mock_create.assert_called_once()
        mock_update.assert_called_once()
        assert mock_update.call_args.kwargs["post_id"] == 58
        assert mock_update.call_args.kwargs["media_ids"] == [57]
