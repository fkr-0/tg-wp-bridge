import pytest


def test_expected_webhook_url_respects_prefix(temp_settings):
    from tg_wp_bridge import telegram_api

    with temp_settings(
        public_base_url="https://example.com",
        telegram_webhook_secret="s3cr3t",
        webhook_prefix="tg-webhook",
        telegram_bot_token="12345678:TEST",
        tg_skip=False,
    ):
        assert (
            telegram_api.expected_webhook_url()
            == "https://example.com/tg-webhook/s3cr3t"
        )


@pytest.mark.asyncio
async def test_webhook_validation_skips_when_tg_skip(temp_settings):
    from tg_wp_bridge import startup

    with temp_settings(tg_skip=True):
        res = await startup.check_webhook_validation()
        assert res["webhook_config"][0] is True
