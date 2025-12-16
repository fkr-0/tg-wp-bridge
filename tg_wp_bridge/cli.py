"""
CLI interface for tg-wp-bridge management commands.

Provides command-line access to:
- webhook_info: Inspect current Telegram webhook status
- set_webhook: Configure Telegram webhook
- status: Display bridge configuration and status
"""

import asyncio
import json
import logging
import sys
from typing import Optional

import click

from .config import settings, Settings
from . import wordpress_api
from .telegram_api import get_webhook_info, set_webhook

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("tg-wp-bridge.cli")


@click.group()
@click.option(
    "--config-file",
    type=click.Path(exists=True),
    help="Path to environment file with configuration",
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, config_file: Optional[str], debug: bool) -> None:
    """Telegram-WordPress Bridge CLI management tool."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        log.debug("Debug mode enabled")
    
    # Load configuration from specified file if provided
    if config_file:
        log.info(f"Loading configuration from: {config_file}")
        from pydantic_settings import SettingsConfigDict
        
        class LocalSettings(Settings):
            model_config = SettingsConfigDict(
                env_file=config_file,
                env_file_encoding="utf-8",
                extra="ignore",
            )
        
        # Replace global settings for this CLI session
        import tg_wp_bridge.config as config_module
        config_module.settings = LocalSettings()
        log.debug("Configuration loaded from custom file")
    
    # Log key configuration values (in debug mode only for security)
    log.debug("Configuration loaded:")
    log.debug(f"  telegram_bot_token: {'*' * 10 if settings.telegram_bot_token else 'None'}")
    log.debug(f"  public_base_url: {settings.public_base_url}")
    log.debug(f"  telegram_webhook_secret: {'*' * 8 if settings.telegram_webhook_secret else 'None'}")
    
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config_file
    ctx.obj["debug"] = debug


@cli.command(name="wp-info")
@click.pass_context
def wp_info_cmd(ctx: click.Context) -> None:
    """Display WordPress API configuration details."""
    log.info("Displaying WordPress API configuration")

    base_url = getattr(settings, "wp_base_url", None)
    username = getattr(settings, "wp_username", None)
    category_id = getattr(settings, "wp_category_id", 0)
    publish_status = getattr(settings, "wp_publish_status", "publish")

    click.echo("WordPress API configuration:")
    click.echo(f"  Base URL: {base_url or 'Not configured'}")
    click.echo(f"  Username: {username or 'Not configured'}")
    click.echo(f"  Category ID: {category_id}")
    click.echo(f"  Publish status: {publish_status}")

    if base_url:
        base = str(base_url).rstrip("/")
        click.echo(f"  Media endpoint: {base}/wp-json/wp/v2/media")
        click.echo(f"  Posts endpoint: {base}/wp-json/wp/v2/posts")
    else:
        click.echo("  Media endpoint: N/A")
        click.echo("  Posts endpoint: N/A")


@cli.command(name="wp-check")
@click.pass_context
def wp_check_cmd(ctx: click.Context) -> None:
    """Verify WordPress reachability and credentials."""

    log.info("Checking WordPress reachability and credentials")

    async def _check():
        ping_ok = False
        cred_ok = False
        ping_error = None
        cred_error = None

        try:
            ping_info = await wordpress_api.ping_wp_api()
            ping_ok = True
            click.echo("✓ WordPress reachable")
            click.echo(f"  Name: {ping_info.get('name', 'Unknown')}")
        except Exception as exc:  # pragma: no cover - logging path
            ping_error = str(exc)
            log.error("WordPress ping failed: %s", exc, exc_info=ctx.obj.get("debug", False))
            click.echo(f"✗ WordPress ping failed: {exc}", err=True)

        try:
            creds_info = await wordpress_api.check_wp_credentials()
            cred_ok = True
            click.echo("✓ WordPress credentials valid")
            click.echo(
                f"  Auth user: {creds_info.get('name', 'unknown')} (id={creds_info.get('id')})"
            )
        except Exception as exc:  # pragma: no cover - logging path
            cred_error = str(exc)
            log.error("WordPress credential check failed: %s", exc, exc_info=ctx.obj.get("debug", False))
            click.echo(f"✗ WordPress credential check failed: {exc}", err=True)

        if not (ping_ok and cred_ok):
            raise click.ClickException(
                "WordPress check failed: "
                + "; ".join(filter(None, [ping_error, cred_error]))
            )

    asyncio.run(_check())


@cli.command(name="webhook-info")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table", help="Output format")
@click.pass_context
def webhook_info(ctx: click.Context, output_format: str) -> None:
    """Display current Telegram webhook information."""
    log.info("Getting webhook information")
    
    async def _get_webhook_info():
        try:
            log.debug("Calling get_webhook_info()")
            info = await get_webhook_info()
            log.debug(f"Webhook info received: {info.model_dump()}")
            
            if output_format == "json":
                click.echo(json.dumps(info.model_dump(), indent=2))
            else:
                # Table format
                click.echo("Telegram Webhook Information:")
                click.echo(f"  URL: {info.url or 'Not set'}")
                click.echo(f"  Custom certificate: {info.has_custom_certificate}")
                click.echo(f"  Pending updates: {info.pending_update_count}")
                click.echo(f"  Last error date: {info.last_error_date or 'None'}")
                click.echo(f"  Last error message: {info.last_error_message or 'None'}")
                click.echo(f"  IP address: {info.ip_address or 'Not set'}")
            
            log.info("Webhook information retrieved successfully")
                
        except Exception as e:
            log.error(f"Error getting webhook info: {e}", exc_info=ctx.obj.get("debug", False))
            click.echo(f"Error getting webhook info: {e}", err=True)
            raise click.ClickException(f"Failed to get webhook info: {e}")
    
    asyncio.run(_get_webhook_info())


@cli.command(name="set-webhook")
@click.option("--dry-run", is_flag=True, help="Show what would be set without actually setting it")
@click.pass_context
def set_webhook_cmd(ctx: click.Context, dry_run: bool) -> None:
    """Configure Telegram webhook for this bridge."""
    log.info(f"Setting webhook (dry_run={dry_run})")
    
    async def _set_webhook():
        try:
            webhook_url = (
                f"{settings.public_base_url}/webhook/{settings.telegram_webhook_secret}"
            )
            
            log.info(f"Calculated webhook URL: {webhook_url}")
            
            if dry_run:
                click.echo(f"Would set webhook to: {webhook_url}")
                log.info("Dry run completed - no actual webhook set")
                return
            
            log.info("Proceeding with webhook configuration")
            click.echo(f"Setting webhook to: {webhook_url}")
            
            result = await set_webhook()
            log.debug(f"set_webhook() result: {result}")
            
            if result.get("ok"):
                click.echo("✓ Webhook configured successfully")
                click.echo(f"  URL: {webhook_url}")
                description = result.get("description")
                if description:
                    click.echo(f"  Telegram response: {description}")
                log.info("Webhook configured successfully")
            else:
                click.echo("✗ Failed to configure webhook", err=True)
                error_msg = result.get('description', 'Unknown error')
                click.echo(f"  Error: {error_msg}", err=True)
                log.error(f"Webhook configuration failed: {error_msg}")
                raise click.ClickException("Webhook configuration failed")
                
        except Exception as e:
            log.error(f"Error setting webhook: {e}", exc_info=ctx.obj.get("debug", False))
            click.echo(f"Error setting webhook: {e}", err=True)
            raise click.ClickException(f"Failed to set webhook: {e}")
    
    asyncio.run(_set_webhook())


@cli.command(name="startup-check")
@click.option(
    "--auto-fix-webhook/--no-auto-fix-webhook",
    default=True,
    help="Automatically configure webhook if not set",
)
@click.pass_context
def startup_check_cmd(ctx: click.Context, auto_fix_webhook: bool) -> None:
    """Run startup diagnostics and optionally fix missing webhook."""

    async def _run():
        click.echo("Running startup checks…")

        bot_token_ok = bool(settings.telegram_bot_token)
        click.echo(f"Bot token configured: {'✓' if bot_token_ok else '✗'}")

        webhook_configured = False
        webhook_error: Optional[str] = None
        webhook_url: Optional[str] = None

        if bot_token_ok:
            try:
                info = await get_webhook_info()
                webhook_url = info.url
                webhook_configured = bool(info.url)
                if webhook_configured:
                    click.echo(f"Webhook configured: ✓ ({info.url})")
                else:
                    click.echo("Webhook configured: ✗")
                    if auto_fix_webhook:
                        click.echo("Attempting to configure webhook…")
                        result = await set_webhook()
                        if result.get("ok"):
                            refreshed = await get_webhook_info()
                            webhook_url = refreshed.url
                            webhook_configured = bool(refreshed.url)
                            click.echo(
                                f"Webhook configured successfully at {webhook_url or 'unknown URL'}"
                            )
                        else:
                            webhook_error = result.get("description", "Unknown error")
                            click.echo(
                                f"Webhook configuration failed: {webhook_error}", err=True
                            )
            except Exception as exc:  # pragma: no cover - logging path
                webhook_error = str(exc)
                click.echo(f"Webhook check failed: {exc}", err=True)
        else:
            webhook_error = "Bot token missing"

        # WordPress ping and credential checks
        wp_reachable = False
        wp_creds_ok = False
        wp_ping_error: Optional[str] = None
        wp_creds_error: Optional[str] = None

        try:
            ping_info = await wordpress_api.ping_wp_api()
            wp_reachable = True
            click.echo(f"WordPress reachable: ✓ ({ping_info.get('name', 'Unknown')})")
        except Exception as exc:  # pragma: no cover - logging path
            wp_ping_error = str(exc)
            click.echo(f"WordPress reachable: ✗ ({exc})", err=True)

        if wp_reachable:
            try:
                creds_info = await wordpress_api.check_wp_credentials()
                wp_creds_ok = True
                click.echo(
                    "WordPress credentials: ✓ (user="
                    f"{creds_info.get('name', 'unknown')} id={creds_info.get('id')})"
                )
            except Exception as exc:  # pragma: no cover - logging path
                wp_creds_error = str(exc)
                click.echo(f"WordPress credentials: ✗ ({exc})", err=True)

        click.echo("\nStartup summary:")
        click.echo(f"  Bot token configured: {'✓' if bot_token_ok else '✗'}")
        click.echo(f"  Webhook configured: {'✓' if webhook_configured else '✗'}")
        if webhook_error and not webhook_configured:
            click.echo(f"  Webhook error: {webhook_error}")
        click.echo(f"  WordPress reachable: {'✓' if wp_reachable else '✗'}")
        if wp_ping_error and not wp_reachable:
            click.echo(f"  WordPress ping error: {wp_ping_error}")
        click.echo(f"  WordPress credentials: {'✓' if wp_creds_ok else '✗'}")
        if wp_creds_error and not wp_creds_ok:
            click.echo(f"  WordPress credential error: {wp_creds_error}")

        if not (bot_token_ok and webhook_configured and wp_reachable and wp_creds_ok):
            raise click.ClickException("Startup check reported failures")

    asyncio.run(_run())


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Display bridge configuration and current status."""
    log.info("Displaying bridge status")
    
    click.echo("Telegram-WordPress Bridge Status:")
    click.echo()
    
    # Configuration section
    click.echo("Configuration:")
    bot_token_status = "✓" if settings.telegram_bot_token else "✗"
    click.echo(f"  Bot token configured: {bot_token_status}")
    
    click.echo(f"  Public base URL: {settings.public_base_url or 'Not configured'}")
    
    webhook_secret_status = "✓" if settings.telegram_webhook_secret else "✗"
    click.echo(f"  Webhook secret configured: {webhook_secret_status}")
    
    click.echo(f"  Required hashtag: {settings.required_hashtag or 'None'}")
    
    # WordPress section
    wp_base = getattr(settings, 'wp_base_url', None)
    if wp_base:
        click.echo(f"  WordPress base URL: {wp_base}")
    else:
        click.echo("  WordPress base URL: Not configured")
    
    wp_username = getattr(settings, 'wp_username', None)
    if wp_username:
        click.echo(f"  WordPress username: {wp_username}")
    else:
        click.echo("  WordPress username: Not configured")
        
    wp_password = getattr(settings, 'wp_app_password', None)
    wp_password_status = "✓" if wp_password else "✗"
    click.echo(f"  WordPress password configured: {wp_password_status}")
    click.echo(f"  WordPress category ID: {getattr(settings, 'wp_category_id', 0)}")
    click.echo(f"  WordPress publish status: {getattr(settings, 'wp_publish_status', 'publish')}")
    
    # Log configuration status
    log.info("Configuration check completed")
    log.debug(f"Bot token: {'configured' if settings.telegram_bot_token else 'not configured'}")
    log.debug(f"Public base URL: {settings.public_base_url}")
    log.debug(f"Webhook secret: {'configured' if settings.telegram_webhook_secret else 'not configured'}")
    log.debug(f"WordPress base URL: {wp_base}")
    log.debug(f"WordPress username: {wp_username}")
    
    # Check webhook status
    async def _check_webhook():
        try:
            log.debug("Checking webhook status")
            info = await get_webhook_info()
            click.echo()
            click.echo("Webhook Status:")
            click.echo(f"  Configured URL: {info.url or 'Not set'}")
            
            if info.url:
                status_indicator = "✓ Active" if not info.last_error_message else "⚠ Active with errors"
                click.echo(f"  Status: {status_indicator}")
            else:
                click.echo(f"  Status: ✗ Not configured")
            
            if info.last_error_message:
                click.echo(f"  Last error: {info.last_error_message}")
                log.warning(f"Webhook last error: {info.last_error_message}")
            
            log.info("Webhook status check completed")
                
        except Exception as e:
            click.echo()
            click.echo("Webhook Status:")
            click.echo(f"  Error checking status: {e}")
            log.error(f"Error checking webhook status: {e}", exc_info=ctx.obj.get("debug", False))
    
    asyncio.run(_check_webhook())


if __name__ == "__main__":
    cli()
