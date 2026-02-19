import asyncio
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_retries_media_resolution_and_eventually_uploads(tmp_path, monkeypatch, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # noqa: F401  # ensure handlers are registered
    from tg_wp_bridge.schemas import TgChat, TgMessage, TgPhotoSize, WPPostResponse, WPMediaResponse
    from tg_wp_bridge.update_model import TelegramUpdate

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(tmp_path / "message_map.json"))

    update = TelegramUpdate(
        update_id=1,
        message=TgMessage(
            message_id=501,
            date=1770729760,
            chat=TgChat(id=-1003610084567, type="supergroup"),
            caption="Album entry",
            photo=[
                TgPhotoSize(file_id="photo-small", width=10, height=10),
                TgPhotoSize(file_id="photo-large", width=100, height=100),
            ],
        ),
    )

    with (
        temp_settings(
            wp_skip=False,
            tg_skip=False,
            chat_type_allowlist=("channel", "supergroup"),
            tg_media_retry_attempts=3,
            tg_media_retry_backoff_seconds=0,
        ),
        patch("tg_wp_bridge.handlers.get_file_direct_url", new_callable=AsyncMock) as mock_file_url,
        patch("tg_wp_bridge.handlers.download_file", new_callable=AsyncMock) as mock_download,
        patch("tg_wp_bridge.handlers.upload_media_to_wp", new_callable=AsyncMock) as mock_upload,
        patch("tg_wp_bridge.handlers.create_wp_post", new_callable=AsyncMock) as mock_create,
    ):
        mock_file_url.side_effect = [RuntimeError("telegram transient 400"), "https://telegram.example/file.jpg"]
        mock_download.return_value = b"photo-bytes"
        mock_upload.return_value = WPMediaResponse(
            id=301,
            source_url="https://example.com/uploads/photo.jpg",
        )
        mock_create.return_value = WPPostResponse(
            id=401,
            title={"rendered": "Album entry"},
            content={"rendered": "<p>Album entry</p>"},
            featured_media=301,
        )

        await dispatch_update(update)

        assert mock_file_url.await_count == 2
        assert mock_download.await_count == 1
        assert mock_upload.await_count == 1
        assert mock_create.call_args.kwargs["media_ids"] == [301]


@pytest.mark.asyncio
async def test_retry_exhaustion_does_not_abort_post_creation(tmp_path, monkeypatch, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # noqa: F401  # ensure handlers are registered
    from tg_wp_bridge.schemas import TgChat, TgMessage, TgPhotoSize, WPPostResponse
    from tg_wp_bridge.update_model import TelegramUpdate

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(tmp_path / "message_map.json"))

    update = TelegramUpdate(
        update_id=1,
        message=TgMessage(
            message_id=601,
            date=1770729760,
            chat=TgChat(id=-1003610084567, type="supergroup"),
            caption="Text must still be posted\nBody survives retries",
            photo=[
                TgPhotoSize(file_id="photo-small", width=10, height=10),
                TgPhotoSize(file_id="photo-large", width=100, height=100),
            ],
        ),
    )

    with (
        temp_settings(
            wp_skip=False,
            tg_skip=False,
            chat_type_allowlist=("channel", "supergroup"),
            tg_media_retry_attempts=3,
            tg_media_retry_backoff_seconds=0,
        ),
        patch("tg_wp_bridge.handlers.get_file_direct_url", new_callable=AsyncMock) as mock_file_url,
        patch("tg_wp_bridge.handlers.create_wp_post", new_callable=AsyncMock) as mock_create,
    ):
        mock_file_url.side_effect = RuntimeError("permanent telegram 400")
        mock_create.return_value = WPPostResponse(
            id=402,
            title={"rendered": "Text must still be posted"},
            content={"rendered": "<p>Body survives retries</p>"},
            featured_media=0,
        )

        await dispatch_update(update)

        assert mock_file_url.await_count == 3
        assert mock_create.await_count == 1
        assert mock_create.call_args.kwargs["media_ids"] is None
        assert "Body survives retries" in mock_create.call_args.kwargs["content_html"]


@pytest.mark.asyncio
async def test_post_body_does_not_repeat_extracted_title(tmp_path, monkeypatch, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # noqa: F401  # ensure handlers are registered
    from tg_wp_bridge.schemas import TgChat, TgMessage, WPPostResponse
    from tg_wp_bridge.update_model import TelegramUpdate

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(tmp_path / "message_map.json"))

    update = TelegramUpdate(
        update_id=1,
        message=TgMessage(
            message_id=650,
            date=1770729760,
            chat=TgChat(id=-1003610084567, type="supergroup"),
            caption="Primary Title Line\nThis should stay in body",
        ),
    )

    with (
        temp_settings(
            wp_skip=False,
            tg_skip=False,
            chat_type_allowlist=("channel", "supergroup"),
        ),
        patch("tg_wp_bridge.handlers.create_wp_post", new_callable=AsyncMock) as mock_create,
    ):
        mock_create.return_value = WPPostResponse(
            id=450,
            title={"rendered": "Primary Title Line"},
            content={"rendered": "<p>This should stay in body</p>"},
        )

        await dispatch_update(update)

        assert mock_create.await_count == 1
        assert mock_create.call_args.kwargs["title"] == "Primary Title Line"
        assert mock_create.call_args.kwargs["content_html"] == "<p>This should stay in body</p>"


@pytest.mark.asyncio
async def test_media_group_continuation_waits_for_primary_post_mapping(tmp_path, monkeypatch, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # noqa: F401  # ensure handlers are registered
    from tg_wp_bridge.schemas import TgChat, TgMessage, TgVideo, WPPostResponse, WPMediaResponse
    from tg_wp_bridge.update_model import TelegramUpdate

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TG_WP_MAPPING_FILE", str(tmp_path / "message_map.json"))

    chat = TgChat(id=-1003610084567, type="supergroup")
    group_id = "14179999990000001"

    continuation = TelegramUpdate(
        update_id=1,
        message=TgMessage(
            message_id=711,
            date=1770729760,
            chat=chat,
            video=TgVideo(file_id="vid711", file_name="clip.mp4", mime_type="video/mp4"),
            media_group_id=group_id,
        ),
    )
    primary = TelegramUpdate(
        update_id=2,
        message=TgMessage(
            message_id=710,
            date=1770729760,
            chat=chat,
            caption="Primary album caption",
            media_group_id=group_id,
        ),
    )

    with (
        temp_settings(
            wp_skip=False,
            tg_skip=False,
            chat_type_allowlist=("channel", "supergroup"),
            tg_media_group_wait_timeout_seconds=1.0,
            tg_media_group_wait_interval_seconds=0.01,
        ),
        patch("tg_wp_bridge.handlers.create_wp_post", new_callable=AsyncMock) as mock_create,
        patch("tg_wp_bridge.handlers._upload_single_media", new_callable=AsyncMock) as mock_upload,
        patch("tg_wp_bridge.handlers.get_wp_post_content", new_callable=AsyncMock) as mock_get_content,
        patch("tg_wp_bridge.handlers.update_wp_post", new_callable=AsyncMock) as mock_update,
    ):
        mock_create.return_value = WPPostResponse(
            id=777,
            title={"rendered": "Primary album caption"},
            content={"rendered": "<p>Primary album caption</p>"},
        )
        mock_upload.return_value = WPMediaResponse(
            id=778,
            source_url="https://example.com/uploads/clip.mp4",
        )
        mock_get_content.return_value = "<p>Primary album caption</p>"
        mock_update.return_value = WPPostResponse(
            id=777,
            title={"rendered": "Primary album caption"},
            content={"rendered": "<p>Primary album caption</p><figure>...</figure>"},
        )

        continuation_task = asyncio.create_task(dispatch_update(continuation))
        await asyncio.sleep(0.05)
        await dispatch_update(primary)
        await continuation_task

        assert mock_create.await_count == 1
        assert mock_update.await_count == 1
        assert mock_update.call_args.kwargs["post_id"] == 777
