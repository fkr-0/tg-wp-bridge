# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - 2026-03-03

### Added
- Timestamped `.error` artifacts (`<timestamp>.error`) for major processing failures with:
  - raw Telegram update payload
  - associated WordPress post payload (when available)
  - full Python traceback
- Dispatcher-level `.error` artifact capture for uncaught handler exceptions.

### Changed
- Processing logs now start with a message-scoped prefix:
  - `<message-id> > <log-msg>`
- Edited-message sync appends an `Edited at: <timestamp>` marker to mirrored WordPress content.

### Fixed
- WordPress media upload now handles non-ASCII filenames safely by using RFC5987-compatible
  `Content-Disposition` encoding, preventing ASCII codec failures for names like `Schüsse.mp4`.

## [0.5.0] - 2026-02-19

### Added
- Media download hardening controls:
  - `TG_MEDIA_RETRY_ATTEMPTS`
  - `TG_MEDIA_RETRY_BACKOFF_SECONDS`
  - `TG_MEDIA_GROUP_WAIT_TIMEOUT_SECONDS`
  - `TG_MEDIA_GROUP_WAIT_INTERVAL_SECONDS`
- Regression tests for:
  - transient Telegram media resolution failures with retry
  - non-fatal media upload failures (post still created without media)
  - out-of-order media-group continuation handling
  - title/body de-duplication in mirrored posts

### Changed
- Default log directory is now `data/logs` (can still be overridden via `STORAGE_DIR`).
- Title generation no longer truncates by default, preventing cut-off post titles.
- Mirrored post body now strips the first non-empty line (used as title) to avoid duplicated title text in content.

### Fixed
- Media-group race where a continuation message could be processed before the primary message mapping existed.
- Media processing path now retries transient Telegram media resolution/download failures before giving up.
- Media failures no longer abort post creation; posts are still created with available text/content.

## [0.3.0] - 2025-01-24

### Added
- **Emoji stripping** for URLs, slugs, and permalinks to ensure URL-safe content
- **Slug generation** (`build_slug_from_text()`) for creating clean, URL-friendly post slugs
- **Post type configuration** via `WP_POST_TYPE` environment variable (default: `post`)
  - Supports standard post types: `post`, `page`
  - Supports custom post types by name
- **Media deduplication** via `WP_USE_FEATURED_MEDIA` environment variable
  - When `False` (default): All media appears only in the content gallery
  - When `True`: First photo is used as featured image and excluded from gallery
  - Fixes bug where first media appeared twice (featured + in gallery)
- **Webhook path prefix** via `WEBHOOK_PREFIX` environment variable (default: `webhook`)
  - Allows customization of the Telegram webhook URL path
  - Full webhook path: `/{WEBHOOK_PREFIX}/{TELEGRAM_WEBHOOK_SECRET}`
- **Custom slug support** - WordPress posts now receive emoji-free, URL-safe slugs

### Changed
- `build_title_from_text()` now strips emojis from generated titles
- WordPress REST API endpoint handling respects `WP_POST_TYPE` setting
- Webhook endpoint path is now configurable instead of hardcoded `/webhook/`

### Fixed
- Media duplication bug where first image appeared twice (featured + gallery)
- Docker Compose environment variable loading now uses `env_file` directive

### Testing
- Added 44 tests for emoji stripping, slug generation, and post type features
- Added 14 tests for media deduplication behavior
- All tests include falsifying and regression detection patterns
- Total: 224 passing tests

## [0.2.0] - Previous

### Added
- Rich TTY-aware output with DisplayManager facade
- Comprehensive startup validation and diagnostics
- Docker configuration
- Message flow diagrams in documentation

### Changed
- README.org replaced with README.md
- Code formatting for improved readability

## [0.1.0] - Initial Release

### Added
- Basic Telegram to WordPress bridge functionality
- Channel post mirroring to WordPress blog posts
- Media upload (photos, videos, animations, documents)
- Hashtag filtering support
- Webhook configuration endpoints
- Health check and validation endpoints
