from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_video_with_thumbnail_uses_thumbnail_as_featured(tmp_path, monkeypatch, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # noqa: F401
    from tg_wp_bridge.schemas import TgChat, TgMessage, TgVideo, TgThumbnail, WPMediaResponse, WPPostResponse
    from tg_wp_bridge.update_model import TelegramUpdate

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(tmp_path / "message_map.json"))

    update = TelegramUpdate(
        update_id=1,
        message=TgMessage(
            message_id=123,
            date=1770729760,
            chat=TgChat(id=-1003610084567, type="supergroup"),
            video=TgVideo(
                file_id="video123",
                file_name="clip.mp4",
                mime_type="video/mp4",
                thumbnail=TgThumbnail(file_id="thumb123", width=180, height=320),
            ),
        ),
    )

    with (
        temp_settings(wp_skip=False, tg_skip=False, chat_type_allowlist=("channel", "supergroup")),
        patch("tg_wp_bridge.handlers._upload_single_media", new_callable=AsyncMock) as mock_upload,
        patch("tg_wp_bridge.handlers.create_wp_post", new_callable=AsyncMock) as mock_create,
        patch("tg_wp_bridge.handlers.get_wp_post_featured_media", new_callable=AsyncMock) as mock_get_featured,
        patch("tg_wp_bridge.handlers.update_wp_post", new_callable=AsyncMock) as mock_update,
    ):
        mock_upload.side_effect = [
            WPMediaResponse(id=200, source_url="https://example.com/clip.mp4"),
            WPMediaResponse(id=100, source_url="https://example.com/thumb.jpg"),
        ]
        mock_get_featured.return_value = 100
        mock_create.return_value = WPPostResponse(
            id=58,
            title={"rendered": "(no title)"},
            content={"rendered": "<figure>...</figure>"},
        )

        await dispatch_update(update)

        assert mock_create.call_args.kwargs["media_ids"] == [100]
        assert "clip.mp4" in mock_create.call_args.kwargs["content_html"]
        mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_video_without_thumbnail_appends_when_featured_not_set(tmp_path, monkeypatch, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # noqa: F401
    from tg_wp_bridge.schemas import TgChat, TgMessage, TgVideo, WPMediaResponse, WPPostResponse
    from tg_wp_bridge.update_model import TelegramUpdate

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(tmp_path / "message_map.json"))

    update = TelegramUpdate(
        update_id=1,
        message=TgMessage(
            message_id=123,
            date=1770729760,
            chat=TgChat(id=-1003610084567, type="supergroup"),
            video=TgVideo(file_id="video123", file_name="clip.mp4", mime_type="video/mp4"),
        ),
    )

    with (
        temp_settings(wp_skip=False, tg_skip=False, chat_type_allowlist=("channel", "supergroup")),
        patch("tg_wp_bridge.handlers._upload_single_media", new_callable=AsyncMock) as mock_upload,
        patch("tg_wp_bridge.handlers.create_wp_post", new_callable=AsyncMock) as mock_create,
        patch("tg_wp_bridge.handlers.update_wp_post", new_callable=AsyncMock) as mock_update,
    ):
        mock_upload.return_value = WPMediaResponse(
            id=200,
            source_url="https://example.com/clip.mp4",
        )
        # Simulate WP not applying featured_media
        mock_create.return_value = WPPostResponse(
            id=58,
            title={"rendered": "(no title)"},
            content={"rendered": ""},
            featured_media=0,
        )
        mock_update.return_value = WPPostResponse(
            id=58,
            title={"rendered": "(no title)"},
            content={"rendered": "<video>...</video>"},
            featured_media=0,
        )

        await dispatch_update(update)

        mock_update.assert_called_once()
        assert "clip.mp4" in mock_update.call_args.kwargs["content_html"]
