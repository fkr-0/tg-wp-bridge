import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_new_message_wp_skip_creates_mapping_and_logs(tmp_dirs, make_update, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers  # ensure handlers are registered

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
async def test_duplicate_message_does_not_create_second_wp_log(tmp_dirs, make_update, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers

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
async def test_edited_message_wp_skip_uses_mapping_and_writes_wp_log(tmp_dirs, make_update, temp_settings):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers

    with temp_settings(wp_skip=True, tg_skip=False):
        await dispatch_update(make_update(update_id=1, kind="message", message_id=300, text="Hello"))
        await dispatch_update(make_update(update_id=2, kind="edited_message", message_id=300, text="Hello EDIT"))

    storage: Path = tmp_dirs["storage"]
    wp_logs = sorted(storage.glob("*_wp_300_*.json"))
    assert len(wp_logs) == 2  # one create + one update


@pytest.mark.asyncio
async def test_log_rotation_by_file_count(tmp_dirs, make_update, temp_settings, monkeypatch):
    from tg_wp_bridge.dispatcher import dispatch_update
    import tg_wp_bridge.handlers

    monkeypatch.setenv("LOG_MAX_FILES", "2")
    with temp_settings(wp_skip=True, tg_skip=False):
        await dispatch_update(make_update(update_id=1, kind="message", message_id=400, text="A"))
        await dispatch_update(make_update(update_id=2, kind="message", message_id=401, text="B"))

    storage: Path = tmp_dirs["storage"]
    files = sorted(storage.glob("*.json"))
    # rotation keeps only the newest 2 files
    assert len(files) <= 2