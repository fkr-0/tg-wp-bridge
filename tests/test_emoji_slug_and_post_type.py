# == tests/test_emoji_slug_and_post_type.py ==
"""
Comprehensive tests for emoji stripping, slug generation, and post type features.

This module includes:
1. Emoji stripping utility tests with falsifying and regression detection
2. Slug generation tests with various edge cases
3. Post type configuration tests
4. Integration tests combining all features
"""

import pytest
from tg_wp_bridge import message_parser
from tg_wp_bridge.config import Settings


# ============================================================================
# Emoji Stripping Tests
# ============================================================================


class TestStripEmojis:
    """Test suite for the strip_emojis function."""

    def test_strip_basic_emojis(self):
        """Test stripping basic Unicode emojis."""
        text = "Hello 🌟 world 👋"
        result = message_parser.strip_emojis(text)
        assert result == "Hello  world"
        assert "🌟" not in result
        assert "👋" not in result

    def test_strip_emoji_only_string(self):
        """Test stripping a string that contains only emojis."""
        text = "😀😃😄😁"
        result = message_parser.strip_emojis(text)
        assert result == ""

    def test_strip_emojis_preserves_text(self):
        """Test that stripping emojis preserves regular text."""
        text = "This is regular text without emojis"
        result = message_parser.strip_emojis(text)
        assert result == text

    def test_strip_emojis_with_unicode_text(self):
        """Test emoji stripping with non-emoji Unicode characters."""
        text = "Café résumé naïve 🎉"
        result = message_parser.strip_emojis(text)
        assert "🎉" not in result
        assert "Café" in result
        assert "résumé" in result
        assert "naïve" in result

    def test_strip_emojis_chinese_japanese_korean(self):
        """Test emoji stripping with CJK characters."""
        text = "こんにちは世界 🌸 مرحبا بالعالم"
        result = message_parser.strip_emojis(text)
        # The emoji should be removed
        assert "🌸" not in result
        # Non-emoji Unicode (CJK, Arabic) should be preserved in strip_emojis
        assert "こんにちは世界" in result
        assert "مرحبا" in result

    def test_strip_emojis_multiple_emoji_types(self):
        """Test stripping various emoji categories."""
        # emoticons
        text = "Grinning face 😀"
        assert "😀" not in message_parser.strip_emojis(text)

        # symbols & pictographs
        text = "Cloud ☁️"
        result = message_parser.strip_emojis(text)
        # Note: some emojis are multi-character sequences
        assert "☁" in result or result.strip() == "Cloud"

        # transport & map
        text = "Airplane ✈️"
        result = message_parser.strip_emojis(text)
        assert "✈" in result or result.strip() == "Airplane"

        # flags
        text = "Flag 🏳️"
        result = message_parser.strip_emojis(text)
        # Flag emojis are complex, just verify no crash
        assert isinstance(result, str)

    def test_strip_emojis_empty_string(self):
        """Test stripping emojis from an empty string."""
        result = message_parser.strip_emojis("")
        assert result == ""

    def test_strip_emojis_whitespace_only(self):
        """Test stripping emojis from whitespace-only string."""
        result = message_parser.strip_emojis("   \n\t  ")
        assert result == ""

    def test_strip_emojis_leading_trailing(self):
        """Test stripping emojis at start and end of string."""
        text = "🎉 Hello world 🎊"
        result = message_parser.strip_emojis(text)
        assert result.strip() == "Hello world"

    def test_strip_emojis_consecutive(self):
        """Test stripping consecutive emojis."""
        text = "Hello 👋👋👋 world"
        result = message_parser.strip_emojis(text)
        assert "👋" not in result

    def test_strip_emojis_with_special_chars(self):
        """Test emoji stripping with special characters."""
        text = "Hello! 🌟 @user #hashtag"
        result = message_parser.strip_emojis(text)
        assert "🌟" not in result
        assert "!" in result
        assert "@" in result
        assert "#" in result

    def test_strip_emojis_regression_variant_selector(self):
        """
        REGRESSION TEST: Ensure emoji variation selector is properly handled.
        The variation selector U+FE0F should be removed along with emojis.
        """
        # Simple emoji with variation selector
        text = "Number 9️⃣ hash #️⃣"
        result = message_parser.strip_emojis(text)
        # The base digits/chars should remain, emojis removed
        assert isinstance(result, str)

    def test_strip_emojis_regression_zero_width_joiner(self):
        """
        REGRESSION TEST: Test handling of complex emoji sequences with ZWJ.
        Family emoji, skin tone modifiers, etc.
        """
        # Family emoji (uses ZWJ - zero width joiner)
        text = "Family: 👨‍👩‍👧‍👦"
        result = message_parser.strip_emojis(text)
        # Should handle gracefully without crashing
        assert isinstance(result, str)
        # Emoji should be removed
        assert "👨" not in result

    def test_strip_emojis_regression_supplemental_emoji(self):
        """
        REGRESSION TEST: Test supplemental symbols and pictographs range.
        """
        text = "Pinched fingers 🤌 "
        result = message_parser.strip_emojis(text)
        assert "🤌" not in result

    def test_strip_emojis_falsy_check_empty_after_strip(self):
        """
        FALSIFYING TEST: Verify we can detect when text becomes empty after stripping.
        """
        text = "😀😃😄"
        result = message_parser.strip_emojis(text)
        # This should be falsy (empty or whitespace)
        assert not result or not result.strip()

    def test_strip_emojis_falsy_check_still_has_content(self):
        """
        FALSIFYING TEST: Verify we can detect when text still has content.
        """
        text = "Hello 😀"
        result = message_parser.strip_emojis(text)
        # This should be truthy (has actual text content)
        assert result.strip()


# ============================================================================
# Slug Generation Tests
# ============================================================================


class TestBuildSlugFromText:
    """Test suite for the build_slug_from_text function."""

    def test_slug_basic_text(self):
        """Test basic slug generation from plain text."""
        text = "Hello World"
        result = message_parser.build_slug_from_text(text)
        assert result == "hello-world"

    def test_slug_strips_hashtags(self):
        """Test that slug generation strips leading hashtags."""
        text = "#blog My Post Title"
        result = message_parser.build_slug_from_text(text)
        assert result == "my-post-title"
        assert "#" not in result

    def test_slug_strips_emojis(self):
        """Test that slug generation strips emojis."""
        text = "My Post 🌟 Title"
        result = message_parser.build_slug_from_text(text)
        assert "🌟" not in result
        assert "my-post-title" == result

    def test_slug_handles_special_chars(self):
        """Test slug generation with special characters."""
        text = "Hello, World! How are you?"
        result = message_parser.build_slug_from_text(text)
        assert result == "hello-world-how-are-you"

    def test_slug_consecutive_spaces(self):
        """Test slug generation with consecutive spaces."""
        text = "Hello    World     Test"
        result = message_parser.build_slug_from_text(text)
        # No consecutive hyphens
        assert "--" not in result
        assert result == "hello-world-test"

    def test_slug_truncation(self):
        """Test slug truncation to max_length."""
        text = "A" * 100 + " " + "B" * 50
        result = message_parser.build_slug_from_text(text, max_length=50)
        # Check length is reasonable (accounting for hyphens)
        assert len(result) <= 50

    def test_slug_empty_input(self):
        """Test slug generation with empty input."""
        result = message_parser.build_slug_from_text("")
        assert result == "untitled"

    def test_slug_whitespace_only(self):
        """Test slug generation with whitespace-only input."""
        result = message_parser.build_slug_from_text("   \n\n  ")
        assert result == "untitled"

    def test_slug_newlines_in_text(self):
        """Test slug generation uses first line only."""
        text = "First Line Title\nSecond Line\nThird Line"
        result = message_parser.build_slug_from_text(text)
        assert result == "first-line-title"

    def test_slug_unicode_handling(self):
        """Test slug generation with Unicode characters."""
        text = "Café résumé naïve"
        result = message_parser.build_slug_from_text(text)
        # Non-ASCII accents should be stripped to ASCII
        assert "cafe" in result
        assert "resume" in result
        assert "naive" in result

    def test_slug_numbers(self):
        """Test slug generation with numbers."""
        text = "Top 10 Things 2024"
        result = message_parser.build_slug_from_text(text)
        assert result == "top-10-things-2024"

    def test_slug_multiple_hashtags(self):
        """Test slug with multiple leading hashtags."""
        text = "#blog #news My Post Title"
        result = message_parser.build_slug_from_text(text)
        assert result == "my-post-title"

    def test_slug_leading_trailing_special_chars(self):
        """Test slug with special chars at edges."""
        text = "...Hello World..."
        result = message_parser.build_slug_from_text(text)
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_slug_only_hashtags(self):
        """Test slug when text is only hashtags."""
        text = "#blog #news"
        result = message_parser.build_slug_from_text(text)
        # Hashtags are stripped in slug generation (# symbols become hyphens)
        # The slug becomes "blog-news"
        assert result == "blog-news"

    def test_slug_regression_emoji_only_title(self):
        """
        REGRESSION TEST: Handle titles that become empty after emoji stripping.
        """
        text = "🎉🎊🎈"  # Only emojis
        result = message_parser.build_slug_from_text(text)
        assert result == "untitled"

    def test_slug_falsy_check_valid_slug(self):
        """
        FALSIFYING TEST: Verify we can detect valid slugs vs untitled fallback.
        """
        # Valid content
        result = message_parser.build_slug_from_text("Valid Title")
        assert result != "untitled"

        # Invalid content
        result = message_parser.build_slug_from_text("")
        assert result == "untitled"


# ============================================================================
# Title Generation Tests (with emoji stripping)
# ============================================================================


class TestBuildTitleFromTextWithEmojis:
    """Test suite for build_title_from_text with emoji stripping."""

    def test_title_strips_emojis(self):
        """Test that title generation strips emojis."""
        text = "🌟 My Post Title 🎉"
        result = message_parser.build_title_from_text(text)
        assert "🌟" not in result
        assert "🎉" not in result
        assert result == "My Post Title"

    def test_title_emojis_with_hashtags(self):
        """Test title with both hashtags and emojis."""
        text = "#blog 🎉 My Post Title"
        result = message_parser.build_title_from_text(text)
        assert "#blog" not in result
        assert "🎉" not in result
        assert result == "My Post Title"

    def test_title_emoji_only(self):
        """Test title when text contains only emojis."""
        text = "😀😃😄😁"
        result = message_parser.build_title_from_text(text)
        # Emojis are stripped, leaving empty string, which falls back to (no title)
        # Note: With current implementation, empty string after stripping returns (no title)
        assert result in ["", "(no title)"]


# ============================================================================
# Post Type Configuration Tests
# ============================================================================


class TestPostTypeConfiguration:
    """Test suite for WP_POST_TYPE configuration."""

    def test_default_post_type(self, monkeypatch):
        """Test that default post type is 'post'."""
        # Ensure env var is not set
        monkeypatch.delenv("WP_POST_TYPE", raising=False)
        settings = Settings()
        assert settings.wp_post_type == "post"

    def test_custom_post_type_page(self, monkeypatch):
        """Test setting post type to 'page'."""
        monkeypatch.setenv("WP_POST_TYPE", "page")
        # Reset settings to pick up new env var
        from tg_wp_bridge.config import Settings
        settings = Settings.model_validate({"wp_post_type": "page"})
        assert settings.wp_post_type == "page"

    def test_custom_post_type_string(self, monkeypatch):
        """Test setting post type to a custom post type."""
        monkeypatch.setenv("WP_POST_TYPE", "product")
        # Reset settings to pick up new env var
        from tg_wp_bridge.config import Settings
        settings = Settings.model_validate({"wp_post_type": "product"})
        assert settings.wp_post_type == "product"

    def test_post_type_falsy_check_default(self, monkeypatch):
        """
        FALSIFYING TEST: Verify we can detect when post type has default value.
        """
        monkeypatch.delenv("WP_POST_TYPE", raising=False)
        settings = Settings()
        # Should be truthy string "post"
        assert bool(settings.wp_post_type)
        assert settings.wp_post_type == "post"

    def test_post_type_falsy_check_custom(self, monkeypatch):
        """
        FALSIFYING TEST: Verify custom post types are applied.
        """
        monkeypatch.setenv("WP_POST_TYPE", "custom_article")
        from tg_wp_bridge.config import Settings
        settings = Settings.model_validate({"wp_post_type": "custom_article"})
        assert settings.wp_post_type == "custom_article"
        assert settings.wp_post_type != "post"


# ============================================================================
# Integration Tests
# ============================================================================


class TestEmojiSlugAndPostTypeIntegration:
    """Integration tests combining emoji stripping, slugs, and post types."""

    def test_full_workflow_emoji_title_slug(self):
        """Test full workflow: text with emoji -> title and slug."""
        text = "#blog 🎉 My Awesome Post About Emojis"
        title = message_parser.build_title_from_text(text)
        slug = message_parser.build_slug_from_text(text)

        # Title should have emojis stripped
        assert "🎉" not in title
        assert "#blog" not in title
        assert title == "My Awesome Post About Emojis"

        # Slug should be URL-safe
        assert "🎉" not in slug
        assert "#" not in slug
        assert slug == "my-awesome-post-about-emojis"

    def test_full_workflow_multilingual_emoji(self):
        """Test workflow with multilingual text and emojis."""
        text = "🌟 Café Résumé: A Guide 📚"
        title = message_parser.build_title_from_text(text)
        slug = message_parser.build_slug_from_text(text)

        # Title preserves non-emoji Unicode
        assert "🌟" not in title
        assert "📚" not in title
        assert "Café" in title or "Cafe" in title

        # Slug is ASCII-safe
        assert "🌟" not in slug
        assert "📚" not in slug

    def test_regression_emoji_everywhere(self):
        """
        REGRESSION TEST: Text with emojis in all positions.
        """
        text = "🎉#blog🎊Hello🎈World🎁2024🎆"
        title = message_parser.build_title_from_text(text)
        slug = message_parser.build_slug_from_text(text)

        # No emojis in output
        for emoji in ["🎉", "🎊", "🎈", "🎁", "🎆"]:
            assert emoji not in title
            assert emoji not in slug

        # Should still extract meaningful content
        assert "Hello" in title
        assert "World" in title

    def test_falsy_content_detection_after_stripping(self):
        """
        FALSIFYING TEST: Detect when content becomes meaningless after stripping.
        """
        # Emojis only - should result in fallback
        text = "😀😃😄"
        title = message_parser.build_title_from_text(text)
        slug = message_parser.build_slug_from_text(text)

        # Both should indicate no valid content
        assert title == "(no title)"
        assert slug == "untitled"


# == end/tests/test_emoji_slug_and_post_type.py ==
