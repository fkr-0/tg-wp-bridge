import pytest
import json


@pytest.mark.asyncio
async def test_dispatcher_calls_registered_handler(make_update, temp_settings):
    from tg_wp_bridge.dispatcher import (
        clear_handlers,
        register_handler,
        dispatch_update,
        registered_handlers,
    )
    from tg_wp_bridge.update_model import UpdateKind

    snapshot = registered_handlers()
    clear_handlers()
    seen = []

    @register_handler(UpdateKind.message)
    async def _h(update, payload):
        seen.append((update.update_id, payload.message_id))

    upd = make_update(update_id=1, kind="message", message_id=42, text="hi")
    await dispatch_update(upd)
    assert seen == [(1, 42)]

    # restore
    clear_handlers()
    for k, fn in snapshot.items():
        register_handler(k)(fn)


@pytest.mark.asyncio
async def test_dispatcher_ignores_unknown_kind(make_update):
    from tg_wp_bridge.dispatcher import (
        clear_handlers,
        dispatch_update,
        registered_handlers,
        register_handler,
    )

    snapshot = registered_handlers()
    clear_handlers()
    upd = make_update(update_id=1, kind="message", message_id=1)
    # No handler registered -> should not raise
    await dispatch_update(upd)

    clear_handlers()
    for k, fn in snapshot.items():
        register_handler(k)(fn)


@pytest.mark.asyncio
async def test_dispatcher_writes_error_artifact_for_handler_exception(
    make_update, monkeypatch, tmp_path
):
    from tg_wp_bridge.dispatcher import (
        clear_handlers,
        dispatch_update,
        registered_handlers,
        register_handler,
    )
    from tg_wp_bridge.update_model import UpdateKind

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "logs"))
    snapshot = registered_handlers()
    clear_handlers()

    @register_handler(UpdateKind.message)
    async def _boom(update, payload):
        raise RuntimeError("handler exploded")

    upd = make_update(update_id=33, kind="message", message_id=42, text="hi")
    await dispatch_update(upd)

    error_files = sorted((tmp_path / "logs").glob("*.error"))
    assert error_files
    payload = json.loads(error_files[-1].read_text(encoding="utf-8"))
    assert payload["telegram_update"]["update_id"] == 33
    assert "RuntimeError: handler exploded" in payload["traceback"]

    clear_handlers()
    for k, fn in snapshot.items():
        register_handler(k)(fn)
