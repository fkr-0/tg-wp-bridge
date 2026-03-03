import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import tg_wp_bridge.handlers  # noqa: F401


@pytest.mark.asyncio
async def test_new_message_wp_skip_creates_mapping_and_logs(
    tmp_dirs, make_update, temp_settings
):
    from tg_wp_bridge.dispatcher import dispatch_update

    with temp_settings(wp_skip=True, tg_skip=False):
        upd = make_update(update_id=1, kind="message", message_id=100, text="Hello")
        await dispatch_update(upd)

    # mapping stored
    mapping_file: Path = tmp_dirs["mapping_file"]
    data = json.loads(mapping_file.read_text(encoding="utf-8"))
    assert data["100"] == 100

    # logs stored
    storage: Path = tmp_dirs["storage"]
    assert storage.exists()
    tg_logs = sorted(storage.glob("*_tg_100.json"))
    wp_logs = sorted(storage.glob("*_wp_100_*.json"))
    assert len(tg_logs) == 1
    assert len(wp_logs) == 1


@pytest.mark.asyncio
async def test_duplicate_message_does_not_create_second_wp_log(
    tmp_dirs, make_update, temp_settings
):
    from tg_wp_bridge.dispatcher import dispatch_update

    with temp_settings(wp_skip=True, tg_skip=False):
        upd1 = make_update(update_id=1, kind="message", message_id=200, text="Hello")
        upd2 = make_update(update_id=2, kind="message", message_id=200, text="Hello")
        await dispatch_update(upd1)
        await dispatch_update(upd2)

    storage: Path = tmp_dirs["storage"]
    wp_logs = sorted(storage.glob("*_wp_200_*.json"))
    assert len(wp_logs) == 1
    tg_logs = sorted(storage.glob("*_tg_200.json"))
    assert len(tg_logs) == 2


@pytest.mark.asyncio
async def test_edited_message_wp_skip_uses_mapping_and_writes_wp_log(
    tmp_dirs, make_update, temp_settings
):
    from tg_wp_bridge.dispatcher import dispatch_update

    with temp_settings(wp_skip=True, tg_skip=False):
        await dispatch_update(
            make_update(update_id=1, kind="message", message_id=300, text="Hello")
        )
        await dispatch_update(
            make_update(
                update_id=2, kind="edited_message", message_id=300, text="Hello EDIT"
            )
        )

    storage: Path = tmp_dirs["storage"]
    wp_logs = sorted(storage.glob("*_wp_300_*.json"))
    assert len(wp_logs) == 2  # one create + one update


@pytest.mark.asyncio
async def test_log_rotation_by_file_count(
    tmp_dirs, make_update, temp_settings, monkeypatch
):
    from tg_wp_bridge.dispatcher import dispatch_update

    monkeypatch.setenv("LOG_MAX_FILES", "2")
    with temp_settings(wp_skip=True, tg_skip=False):
        await dispatch_update(
            make_update(update_id=1, kind="message", message_id=400, text="A")
        )
        await dispatch_update(
            make_update(update_id=2, kind="message", message_id=401, text="B")
        )

    storage: Path = tmp_dirs["storage"]
    files = sorted(storage.glob("*.json"))
    # rotation keeps only the newest 2 files
    assert len(files) <= 2


def test_mapping_file_falls_back_when_default_path_not_writable(monkeypatch, tmp_path):
    from tg_wp_bridge import handlers

    monkeypatch.delenv("TG_WP_MAPPING_FILE", raising=False)
    monkeypatch.setenv("TG_WP_MAPPING_FALLBACK_DIR", str(tmp_path))

    original_mkdir = Path.mkdir

    def controlled_mkdir(self, *args, **kwargs):
        if str(self) == "data":
            raise PermissionError("permission denied")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", controlled_mkdir)

    mapping_path = handlers._mapping_file()

    assert mapping_path == tmp_path / "message_map.json"


@pytest.mark.asyncio
async def test_message_processing_logs_use_message_id_prefix(
    tmp_dirs, make_update, temp_settings, caplog
):
    import tg_wp_bridge.handlers  # noqa: F401
    from tg_wp_bridge.dispatcher import dispatch_update

    caplog.set_level(logging.INFO, logger="tg-wp-bridge.handlers")

    with temp_settings(wp_skip=True, tg_skip=False):
        await dispatch_update(
            make_update(update_id=10, kind="message", message_id=555, text="Hello")
        )

    assert "555 >" in caplog.text


@pytest.mark.asyncio
async def test_new_message_failure_writes_error_artifact(
    tmp_dirs, make_update, temp_settings
):
    from tg_wp_bridge.dispatcher import dispatch_update

    with temp_settings(wp_skip=False, tg_skip=False):
        with patch(
            "tg_wp_bridge.handlers.create_wp_post",
            new=AsyncMock(side_effect=RuntimeError("create failed")),
        ):
            await dispatch_update(
                make_update(update_id=11, kind="message", message_id=556, text="Hello")
            )

    storage: Path = tmp_dirs["storage"]
    error_files = sorted(storage.glob("*.error"))
    assert error_files
    payload = json.loads(error_files[-1].read_text(encoding="utf-8"))
    assert payload["telegram_update"]["update_id"] == 11
    assert "RuntimeError: create failed" in payload["traceback"]
    assert payload["wp_post"] is None


@pytest.mark.asyncio
async def test_edited_message_appends_edited_timestamp_and_uses_mapping(
    tmp_dirs, temp_settings
):
    from tg_wp_bridge.dispatcher import dispatch_update
    from tg_wp_bridge.update_model import TelegramUpdate
    from tg_wp_bridge.schemas import WPPostResponse

    mapping_file: Path = tmp_dirs["mapping_file"]
    mapping_file.write_text('{"777": 888}', encoding="utf-8")

    edited = TelegramUpdate.model_validate(
        {
            "update_id": 12,
            "edited_message": {
                "message_id": 777,
                "date": 0,
                "edit_date": 1700000000,
                "chat": {"id": 1, "type": "channel"},
                "text": "Updated title\nUpdated body",
            },
        }
    )

    with temp_settings(wp_skip=False, tg_skip=False):
        with patch("tg_wp_bridge.handlers.update_wp_post", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = WPPostResponse(
                id=888,
                title={"rendered": "Updated title"},
                content={"rendered": "<p>Updated body</p>"},
            )
            await dispatch_update(edited)

    kwargs = mock_update.call_args.kwargs
    assert kwargs["post_id"] == 888
    assert "Edited at:" in kwargs["content_html"]
    assert "2023-11-14T22:13:20+00:00" in kwargs["content_html"]
