import pytest


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
    from tg_wp_bridge.dispatcher import clear_handlers, dispatch_update, registered_handlers, register_handler

    snapshot = registered_handlers()
    clear_handlers()
    upd = make_update(update_id=1, kind="message", message_id=1)
    # No handler registered -> should not raise
    await dispatch_update(upd)

    clear_handlers()
    for k, fn in snapshot.items():
        register_handler(k)(fn)
