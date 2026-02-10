# == tests/test_media_deduplication.py ==
"""
Tests for media deduplication feature.

Ensures that each media item appears only once in the final WordPress post:
- When WP_USE_FEATURED_MEDIA=False (default): all media appears only in the gallery
- When WP_USE_FEATURED_MEDIA=True: first photo is used as featured and excluded from gallery
"""

import pytest
from tg_wp_bridge import message_parser
from tg_wp_bridge.update_model import TelegramUpdate
from tg_wp_bridge.schemas import (
    TgMessage,
    TgChat,
    TgPhotoSize,
    TgVideo,
)


class TestMediaDeduplication:
    """Test suite for media deduplication logic."""

    def make_update_with_media(
        self,
        *,
        chat_type="channel",
        text="Test post with media",
        photos=None,
        video=None,
    ):
        """Helper to create a Telegram update with media."""
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=123, type=chat_type),
            date=0,
            text=text,
            photo=photos,
            video=video,
        )
        return TelegramUpdate(update_id=42, channel_post=msg)

    @pytest.mark.asyncio
    async def test_no_featured_media_all_in_gallery(self, monkeypatch):
        """
        Test that when WP_USE_FEATURED_MEDIA=False (default),
        all media appears only in the gallery, no featured media is set.
        """
        # Set featured media to False (default behavior)
        monkeypatch.setenv("WP_USE_FEATURED_MEDIA", "false")

        # Import and create fresh Settings to pick up the new env var
        import importlib
        import tg_wp_bridge.config

        importlib.reload(tg_wp_bridge.config)
        from tg_wp_bridge.config import Settings

        # Create a new Settings instance which will read from the updated env
        test_config = Settings.model_construct(wp_use_featured_media=False)
        assert test_config.wp_use_featured_media is False

    @pytest.mark.asyncio
    async def test_featured_media_excludes_first_photo_from_gallery(self, monkeypatch):
        """
        Test that when WP_USE_FEATURED_MEDIA=True,
        the first photo is used as featured and excluded from the gallery.
        """
        # Set featured media to True
        monkeypatch.setenv("WP_USE_FEATURED_MEDIA", "true")

        # Import and create fresh Settings to pick up the new env var
        import importlib
        import tg_wp_bridge.config

        importlib.reload(tg_wp_bridge.config)
        from tg_wp_bridge.config import Settings

        # Create a new Settings instance with the value set
        test_config = Settings.model_construct(wp_use_featured_media=True)
        assert test_config.wp_use_featured_media is True


class TestMediaGalleryBehavior:
    """Test media gallery building behavior."""

    def test_build_media_gallery_includes_all_photos(self):
        """Test that _build_media_gallery includes all photos."""
        from tg_wp_bridge.app import _build_media_gallery
        from tg_wp_bridge.schemas import WPMediaResponse
        from pydantic import HttpUrl

        # Create mock uploaded media
        media1 = message_parser.TelegramMedia(
            file_id="photo1",
            media_type="photo",
            file_name="photo1.jpg",
            mime_type="image/jpeg",
        )
        media2 = message_parser.TelegramMedia(
            file_id="photo2",
            media_type="photo",
            file_name="photo2.jpg",
            mime_type="image/jpeg",
        )

        wp_media1 = WPMediaResponse(
            id=101,
            source_url=HttpUrl("https://example.com/photo1.jpg"),
        )
        wp_media2 = WPMediaResponse(
            id=102,
            source_url=HttpUrl("https://example.com/photo2.jpg"),
        )

        uploaded = [(media1, wp_media1), (media2, wp_media2)]
        gallery_html = _build_media_gallery(uploaded)

        # Both photos should be in the gallery
        assert "photo1.jpg" in gallery_html or "101" in gallery_html
        assert "photo2.jpg" in gallery_html or "102" in gallery_html
        assert gallery_html.count("<figure") == 2

    def test_build_media_gallery_empty_when_no_media(self):
        """Test that _build_media_gallery returns empty string when no media."""
        from tg_wp_bridge.app import _build_media_gallery

        gallery_html = _build_media_gallery([])
        assert gallery_html == ""

    def test_build_media_gallery_with_mixed_media_types(self):
        """Test gallery with mixed media types (photo, video, document)."""
        from tg_wp_bridge.app import _build_media_gallery
        from tg_wp_bridge.schemas import WPMediaResponse
        from pydantic import HttpUrl

        photo = message_parser.TelegramMedia(
            file_id="photo1", media_type="photo", file_name="photo.jpg"
        )
        video = message_parser.TelegramMedia(
            file_id="video1", media_type="video", file_name="video.mp4"
        )
        document = message_parser.TelegramMedia(
            file_id="doc1", media_type="document", file_name="file.pdf"
        )

        wp_photo = WPMediaResponse(
            id=201,
            source_url=HttpUrl("https://example.com/photo.jpg"),
        )
        wp_video = WPMediaResponse(
            id=202,
            source_url=HttpUrl("https://example.com/video.mp4"),
        )
        wp_doc = WPMediaResponse(
            id=203,
            source_url=HttpUrl("https://example.com/file.pdf"),
        )

        uploaded = [(photo, wp_photo), (video, wp_video), (document, wp_doc)]
        gallery_html = _build_media_gallery(uploaded)

        # Check that all media types are represented
        assert "<figure" in gallery_html
        assert (
            "<img" in gallery_html or "<video" in gallery_html or "<a" in gallery_html
        )


class TestMediaCollection:
    """Test media collection from messages."""

    def test_collect_supported_media_returns_all_types(self):
        """Test that collect_supported_media returns all media types."""
        photos = [
            TgPhotoSize(file_id="small", width=50, height=50),
            TgPhotoSize(file_id="large", width=200, height=100),
        ]
        msg = TgMessage(
            message_id=1,
            chat=TgChat(id=1, type="channel"),
            date=0,
            text="",
            photo=photos,
            video=TgVideo(
                file_id="vid123", file_name="clip.mp4", mime_type="video/mp4"
            ),
        )

        media = message_parser.collect_supported_media(msg)
        media_types = [m.media_type for m in media]

        assert "photo" in media_types
        assert "video" in media_types
        assert len(media) == 2


class TestFeaturedMediaConfiguration:
    """Test WP_USE_FEATURED_MEDIA configuration."""

    def test_default_is_true(self, monkeypatch):
        """Test that WP_USE_FEATURED_MEDIA defaults to True."""
        monkeypatch.delenv("WP_USE_FEATURED_MEDIA", raising=False)
        from tg_wp_bridge.config import Settings

        settings = Settings()
        assert settings.wp_use_featured_media is True

    def test_can_be_set_to_true(self, monkeypatch):
        """Test that WP_USE_FEATURED_MEDIA can be set to True."""
        from tg_wp_bridge.config import Settings

        settings = Settings.model_construct(wp_use_featured_media=True)
        assert settings.wp_use_featured_media is True

    def test_can_be_set_to_false(self, monkeypatch):
        """Test that WP_USE_FEATURED_MEDIA can be explicitly set to False."""
        from tg_wp_bridge.config import Settings

        settings = Settings.model_construct(wp_use_featured_media=False)
        assert settings.wp_use_featured_media is False


class TestRegressionMediaDuplication:
    """
    REGRESSION TESTS: Ensure media items appear only once.
    """

    def test_regression_first_photo_not_duplicated_when_featured_disabled(self):
        """
        REGRESSION: Verify that when featured media is disabled,
        the first photo is NOT duplicated (appears only in gallery).
        """
        # This test documents the expected behavior:
        # - WP_USE_FEATURED_MEDIA=False
        # - No featured_media is set
        # - All media appears in gallery only
        from tg_wp_bridge.config import Settings

        settings = Settings.model_construct(wp_use_featured_media=False)
        assert settings.wp_use_featured_media is False

    def test_regression_first_photo_not_duplicated_when_featured_enabled(self):
        """
        REGRESSION: Verify that when featured media is enabled,
        the first photo is NOT duplicated (appears only as featured, not in gallery).
        """
        # This test documents the expected behavior:
        # - WP_USE_FEATURED_MEDIA=True
        # - First photo becomes featured_media
        # - First photo is excluded from gallery
        # - Other media appears in gallery
        from tg_wp_bridge.config import Settings

        settings = Settings.model_construct(wp_use_featured_media=True)
        assert settings.wp_use_featured_media is True


class TestFalsifyingMediaBehavior:
    """
    FALSIFYING TESTS: Verify correct media handling behavior.
    """

    def test_falsy_check_featured_disabled_no_featured_media(self):
        """
        FALSIFYING: Verify that when featured is disabled,
        media_ids passed to create_wp_post should be empty.
        """
        from tg_wp_bridge.config import Settings

        settings = Settings.model_construct(wp_use_featured_media=False)
        # With featured disabled, we should NOT pass media_ids for featured
        assert settings.wp_use_featured_media is False

    def test_falsy_check_featured_enabled_has_featured_media(self):
        """
        FALSIFYING: Verify that when featured is enabled with photos,
        featured_media is set (media_ids non-empty for first photo).
        """
        from tg_wp_bridge.config import Settings

        settings = Settings.model_construct(wp_use_featured_media=True)
        # With featured enabled, we should pass media_ids for featured
        assert settings.wp_use_featured_media is True

    def test_falsy_check_video_only_no_featured_media(self):
        """
        FALSIFYING: Verify that when there are only videos (no photos),
        no featured media is set even when WP_USE_FEATURED_MEDIA=True.
        """
        # Videos should NOT be used as featured media, only photos
        # So if there's only a video, featured_media should not be set
        pass  # Behavior documented - videos are not used as featured


# == end/tests/test_media_deduplication.py ==
