"""
Startup validation and initialization for tg-wp-bridge.

This module provides comprehensive startup validation including:
- Environment variable validation
- WordPress URL and credential validation
- Telegram bot token validation
- Webhook configuration validation
- Automatic webhook setup when appropriate
"""

import asyncio
import httpx
import logging
from typing import Dict, Tuple
from urllib.parse import urlparse

from . import telegram_api, wordpress_api
from .config import settings

log = logging.getLogger("tg-wp-bridge.startup")


class StartupValidationError(Exception):
    """Raised when startup validation fails."""

    pass


async def check_environment_variables() -> Dict[str, Tuple[bool, str]]:
    """
    Check which environment variables are set and valid.

    Returns:
        Dict mapping variable names to (is_set, message) tuples
    """
    log.info("Checking environment variables...")
    results = {}

    # Check Telegram Bot Token
    if settings.telegram_bot_token:
        # Basic format validation: should look like "123456:ABCDEF..."
        if (
            ":" in settings.telegram_bot_token
            and len(settings.telegram_bot_token.split(":")[0]) >= 8
        ):
            results["TELEGRAM_BOT_TOKEN"] = (True, "Set with valid format")
        else:
            results["TELEGRAM_BOT_TOKEN"] = (False, "Set but invalid format")
    else:
        results["TELEGRAM_BOT_TOKEN"] = (False, "Not set")

    # Check Webhook Secret
    if settings.telegram_webhook_secret:
        if len(settings.telegram_webhook_secret) >= 8:
            results["TELEGRAM_WEBHOOK_SECRET"] = (True, "Set with sufficient length")
        else:
            results["TELEGRAM_WEBHOOK_SECRET"] = (
                False,
                "Set but too short (min 8 chars)",
            )
    else:
        results["TELEGRAM_WEBHOOK_SECRET"] = (False, "Not set")

    # Check Public Base URL
    if settings.public_base_url:
        parsed = urlparse(str(settings.public_base_url))
        if parsed.scheme in ("http", "https") and parsed.netloc:
            results["PUBLIC_BASE_URL"] = (
                True,
                f"Set ({parsed.scheme}://{parsed.netloc})",
            )
        else:
            results["PUBLIC_BASE_URL"] = (False, "Set but invalid URL")
    else:
        results["PUBLIC_BASE_URL"] = (False, "Not set")

    # Check WordPress Base URL
    if settings.wp_base_url:
        parsed = urlparse(str(settings.wp_base_url))
        if parsed.scheme in ("http", "https") and parsed.netloc:
            results["WP_BASE_URL"] = (True, f"Set ({parsed.scheme}://{parsed.netloc})")
        else:
            results["WP_BASE_URL"] = (False, "Set but invalid URL")
    else:
        results["WP_BASE_URL"] = (False, "Not set")

    # Check WordPress Username
    if settings.wp_username:
        if len(settings.wp_username.strip()) >= 1:
            results["WP_USERNAME"] = (True, f"Set ({settings.wp_username})")
        else:
            results["WP_USERNAME"] = (False, "Set but empty")
    else:
        results["WP_USERNAME"] = (False, "Not set")

    # Check WordPress App Password
    if settings.wp_app_password:
        # WordPress app passwords are typically 32+ chars of letters, numbers, and symbols
        if len(settings.wp_app_password) >= 20:
            results["WP_APP_PASSWORD"] = (True, "Set with sufficient length")
        else:
            results["WP_APP_PASSWORD"] = (False, "Set but too short (min 20 chars)")
    else:
        results["WP_APP_PASSWORD"] = (False, "Not set")

    # Log results
    for var_name, (is_valid, message) in results.items():
        if is_valid:
            log.info(f"✓ {var_name}: {message}")
        else:
            log.warning(f"✗ {var_name}: {message}")

    return results


async def check_wordpress_validation() -> Dict[str, Tuple[bool, str]]:
    """
    Validate WordPress connectivity and credentials.

    Returns:
        Dict with validation results
    """
    log.info("Validating WordPress configuration...")
    results = {}

    # Check WP URL reachability
    try:
        log.debug("Attempting to ping WordPress API...")
        ping_info = await wordpress_api.ping_wp_api()
        site_name = ping_info.get("name", "Unknown")
        results["wp_reachable"] = (True, f"Reachable (site: {site_name})")
        log.info(f"✓ WordPress reachable: {site_name}")
    except Exception as e:
        results["wp_reachable"] = (False, f"Unreachable: {str(e)}")
        log.error(f"✗ WordPress unreachable: {e}")
        return results  # Skip credential check if unreachable

    # Check WordPress credentials
    try:
        log.debug("Validating WordPress credentials...")
        creds_info = await wordpress_api.check_wp_credentials()
        user_name = creds_info.get("name", "unknown")
        user_id = creds_info.get("id", "unknown")
        results["wp_credentials"] = (True, f"Valid (user: {user_name}, id: {user_id})")
        log.info(f"✓ WordPress credentials valid: {user_name} (ID: {user_id})")
    except Exception as e:
        results["wp_credentials"] = (False, f"Invalid: {str(e)}")
        log.error(f"✗ WordPress credentials invalid: {e}")

    return results


async def check_telegram_validation() -> Dict[str, Tuple[bool, str]]:
    """
    Validate Telegram bot token and API connectivity.

    Returns:
        Dict with validation results
    """
    log.info("Validating Telegram configuration...")
    results = {}

    # Check bot token format and basic validation
    if not settings.telegram_bot_token:
        results["token_format"] = (False, "Token not set")
        log.error("✗ Telegram bot token not configured")
        return results

    # Basic format check
    if ":" not in settings.telegram_bot_token:
        results["token_format"] = (False, "Invalid format (missing colon)")
        log.error("✗ Telegram bot token has invalid format")
        return results

    # Try to get bot info as validation
    try:
        log.debug("Validating Telegram bot token...")
        async with httpx.AsyncClient() as client:
            token = settings.telegram_bot_token
            base_url = getattr(
                settings, "telegram_api_base", "https://api.telegram.org"
            ).rstrip("/")
            url = f"{base_url}/bot{token}/getMe"

            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()

            if data.get("ok"):
                bot_info = data.get("result", {})
                bot_username = bot_info.get("username", "unknown")
                bot_name = bot_info.get("first_name", "unknown")
                results["token_format"] = (
                    True,
                    f"Valid (bot: @{bot_username}, name: {bot_name})",
                )
                log.info(f"✓ Telegram bot token valid: @{bot_username} ({bot_name})")
            else:
                error_msg = data.get("description", "Unknown error")
                results["token_format"] = (False, f"API rejected: {error_msg}")
                log.error(f"✗ Telegram bot token invalid: {error_msg}")
    except Exception as e:
        results["token_format"] = (False, f"Validation failed: {str(e)}")
        log.error(f"✗ Telegram bot token validation error: {e}")

    return results


async def check_webhook_validation() -> Dict[str, Tuple[bool, str]]:
    """
    Validate webhook configuration and check if it's reachable.

    Returns:
        Dict with validation results
    """
    log.info("Validating webhook configuration...")
    results = {}

    # Check if we have all required components for webhook
    if not settings.public_base_url:
        results["webhook_config"] = (False, "Public base URL not configured")
        log.warning("✗ Webhook validation skipped: Public base URL not set")
        return results

    if not settings.telegram_webhook_secret:
        results["webhook_config"] = (False, "Webhook secret not configured")
        log.warning("✗ Webhook validation skipped: Webhook secret not set")
        return results

    # Build webhook URL
    webhook_url = (
        f"{settings.public_base_url}/webhook/{settings.telegram_webhook_secret}"
    )
    log.debug(f"Constructed webhook URL: {webhook_url}")

    # Check current webhook status
    try:
        log.debug("Checking current Telegram webhook status...")
        webhook_info = await telegram_api.get_webhook_info()
        current_url = webhook_info.url

        if current_url == webhook_url:
            results["webhook_config"] = (True, f"Correctly configured ({webhook_url})")
            log.info(f"✓ Webhook already configured correctly: {webhook_url}")
        elif current_url:
            results["webhook_config"] = (
                False,
                f"Mismatched (current: {current_url}, expected: {webhook_url})",
            )
            log.warning(
                f"⚠ Webhook configured but to wrong URL: {current_url} (expected: {webhook_url})"
            )
        else:
            results["webhook_config"] = (False, "Not configured")
            log.warning("⚠ Webhook not configured")

        # Check for webhook errors
        if webhook_info.last_error_message:
            results["webhook_error"] = (
                False,
                f"Last error: {webhook_info.last_error_message}",
            )
            log.warning(f"⚠ Webhook has errors: {webhook_info.last_error_message}")
        else:
            results["webhook_error"] = (True, "No recent errors")

    except Exception as e:
        results["webhook_config"] = (False, f"Failed to check: {str(e)}")
        log.error(f"✗ Failed to check webhook status: {e}")

    return results


async def setup_webhook_if_needed() -> bool:
    """
    Set up webhook if it's not already configured correctly.

    Returns:
        True if webhook is configured successfully or was already correct
        False if webhook setup failed
    """
    log.info("Checking if webhook setup is needed...")

    # Skip if we don't have all required components
    if not (
        settings.public_base_url
        and settings.telegram_webhook_secret
        and settings.telegram_bot_token
    ):
        log.warning("Skipping webhook setup: missing required configuration")
        return False

    # Check current status
    webhook_url = (
        f"{settings.public_base_url}/webhook/{settings.telegram_webhook_secret}"
    )

    try:
        webhook_info = await telegram_api.get_webhook_info()

        if webhook_info.url == webhook_url and not webhook_info.last_error_message:
            log.info("Webhook already configured correctly")
            return True
    except Exception as e:
        log.warning(f"Could not check webhook status: {e}")

    # Try to set webhook
    try:
        log.info(f"Setting webhook to: {webhook_url}")
        result = await telegram_api.set_webhook()

        if result.get("ok"):
            log.info("✓ Webhook configured successfully")
            return True
        else:
            error_desc = result.get("description", "Unknown error")
            log.error(f"✗ Failed to set webhook: {error_desc}")
            return False
    except Exception as e:
        log.error(f"✗ Exception while setting webhook: {e}")
        return False


async def run_startup_validation(auto_setup_webhook: bool = True) -> Dict[str, any]:
    """
    Run comprehensive startup validation.

    Args:
        auto_setup_webhook: If True, automatically configure webhook if needed

    Returns:
        Dict with validation results and status
    """
    log.info("=" * 60)
    log.info("Starting comprehensive validation...")
    log.info("=" * 60)

    validation_results = {
        "environment": {},
        "wordpress": {},
        "telegram": {},
        "webhook": {},
        "overall": {"status": "unknown", "errors": []},
    }

    # 1. Check environment variables
    validation_results["environment"] = await check_environment_variables()

    # 2. Validate WordPress if URL is configured
    if validation_results["environment"].get("WP_BASE_URL", (False, ""))[0]:
        validation_results["wordpress"] = await check_wordpress_validation()
    else:
        log.warning("Skipping WordPress validation: URL not configured")
        validation_results["wordpress"] = {
            "wp_reachable": (False, "Skipped: URL not configured"),
            "wp_credentials": (False, "Skipped: URL not configured"),
        }

    # 3. Validate Telegram if token is configured
    if validation_results["environment"].get("TELEGRAM_BOT_TOKEN", (False, ""))[0]:
        validation_results["telegram"] = await check_telegram_validation()
    else:
        log.warning("Skipping Telegram validation: Token not configured")
        validation_results["telegram"] = {
            "token_format": (False, "Skipped: Token not configured")
        }

    # 4. Validate webhook if components are available
    if (
        validation_results["environment"].get("PUBLIC_BASE_URL", (False, ""))[0]
        and validation_results["environment"].get(
            "TELEGRAM_WEBHOOK_SECRET", (False, "")
        )[0]
    ):
        validation_results["webhook"] = await check_webhook_validation()
    else:
        log.warning("Skipping webhook validation: Missing required components")
        validation_results["webhook"] = {
            "webhook_config": (False, "Skipped: Missing components"),
            "webhook_error": (True, "Not applicable"),
        }

    # 5. Auto-setup webhook if requested
    webhook_setup_success = False
    if auto_setup_webhook:
        if (
            validation_results["telegram"].get("token_format", (False, ""))[0]
            and validation_results["environment"].get("PUBLIC_BASE_URL", (False, ""))[0]
        ):
            webhook_setup_success = await setup_webhook_if_needed()
        else:
            log.info("Skipping automatic webhook setup: Prerequisites not met")
    else:
        log.info("Automatic webhook setup disabled")

    # 6. Determine overall status
    errors = []

    # Check critical components
    if not validation_results["telegram"].get("token_format", (False, ""))[0]:
        errors.append("Telegram bot token invalid or missing")

    if not validation_results["wordpress"].get("wp_reachable", (False, ""))[0]:
        errors.append("WordPress unreachable or URL invalid")

    if not validation_results["wordpress"].get("wp_credentials", (False, ""))[0]:
        errors.append("WordPress credentials invalid")

    if not webhook_setup_success and auto_setup_webhook:
        errors.append("Webhook configuration failed")

    # Log summary
    log.info("=" * 60)
    log.info("VALIDATION SUMMARY")
    log.info("=" * 60)

    for component, results in validation_results.items():
        if component == "overall":
            continue

        component_name = component.capitalize()
        log.info(f"\n{component_name}:")

        for check_name, (is_valid, message) in results.items():
            status = "✓" if is_valid else "✗"
            log.info(f"  {status} {check_name}: {message}")

    if errors:
        log.error("\nCritical errors found:")
        for error in errors:
            log.error(f"  ✗ {error}")
        validation_results["overall"]["status"] = "failed"
        validation_results["overall"]["errors"] = errors
    else:
        log.info("\n✓ All critical validations passed!")
        validation_results["overall"]["status"] = "passed"

    log.info("=" * 60)

    return validation_results


async def validate_and_log_startup(auto_setup_webhook: bool = True) -> None:
    """
    Run startup validation and raise exception if critical failures are found.

    Args:
        auto_setup_webhook: If True, automatically configure webhook if needed

    Raises:
        StartupValidationError: If critical validation failures are found
    """
    results = await run_startup_validation(auto_setup_webhook)

    if results["overall"]["status"] == "failed":
        errors = results["overall"]["errors"]
        raise StartupValidationError(f"Startup validation failed: {'; '.join(errors)}")

    log.info("Startup validation completed successfully")


# Utility function to run from sync context
def run_startup_validation_sync(auto_setup_webhook: bool = True) -> Dict[str, any]:
    """
    Synchronous wrapper for run_startup_validation.
    """
    return asyncio.run(run_startup_validation(auto_setup_webhook))


def validate_and_log_startup_sync(auto_setup_webhook: bool = True) -> None:
    """
    Synchronous wrapper for validate_and_log_startup.
    """
    asyncio.run(validate_and_log_startup(auto_setup_webhook))
