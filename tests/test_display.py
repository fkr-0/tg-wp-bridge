"""Tests for display module rendering."""

from io import StringIO
from unittest.mock import patch

import pytest

from tg_wp_bridge.display import (
    DisplayManager,
    OutputRenderer,
    PlainRenderer,
    RichRenderer,
    RICH_AVAILABLE,
    get_display,
    reset_display,
)


class TestOutputRenderer:
    """Tests for the OutputRenderer abstract base class."""

    def test_cannot_instantiate_abstract_renderer(self):
        """Abstract base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            OutputRenderer()


@pytest.mark.skipif(not RICH_AVAILABLE, reason="rich not installed")
class TestRichRenderer:
    """Tests for RichRenderer with rich library."""

    def test_init_creates_console(self):
        """Renderer initialization creates a rich Console."""
        renderer = RichRenderer()
        assert renderer.console is not None
        assert renderer.is_interactive()

    def test_print_success_outputs_green_checkmark(self):
        """Success message prints with green checkmark."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)
        renderer.print_success("Test message")

        output = console.file.getvalue()
        assert "Test message" in output

    def test_print_error_outputs_red_x(self):
        """Error message prints with red X."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)
        renderer.print_error("Error message")

        output = console.file.getvalue()
        assert "Error message" in output

    def test_print_validation_table(self):
        """Validation results are printed as a table."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)

        results = {
            "check1": (True, "All good"),
            "check2": (False, "Failed"),
        }
        renderer.print_validation_table("Test Table", results)

        output = console.file.getvalue()
        assert "Test Table" in output
        assert "check1" in output
        assert "check2" in output

    def test_print_summary_passed(self):
        """Passed validation prints success panel."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)

        results = {"overall": {"status": "passed", "errors": []}}
        renderer.print_summary(results)

        output = console.file.getvalue()
        assert "passed" in output.lower()

    def test_print_summary_failed(self):
        """Failed validation prints error panel."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)

        results = {"overall": {"status": "failed", "errors": ["Error 1", "Error 2"]}}
        renderer.print_summary(results)

        output = console.file.getvalue()
        assert "failed" in output.lower()
        assert "Error 1" in output

    def test_progress_context(self):
        """Progress context manager works correctly."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)

        with renderer.progress_context(total=2) as (progress, task_id):
            assert progress is not None
            assert task_id is not None
            renderer.update_progress((progress, task_id), 1, "Step 1")

    def test_print_summary_handles_none_overall(self):
        """print_summary handles None overall gracefully."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)

        # Test with None overall
        results = {"overall": None}
        # Should not crash
        renderer.print_summary(results)

        # Test with missing overall key
        results = {}
        renderer.print_summary(results)


class TestPlainRenderer:
    """Tests for PlainRenderer fallback."""

    def test_init(self):
        """PlainRenderer can be instantiated."""
        renderer = PlainRenderer()
        assert not renderer.is_interactive()

    def test_print_success_outputs_checkmark(self):
        """Success message prints with checkmark."""
        renderer = PlainRenderer()
        with patch("builtins.print") as mock_print:
            renderer.print_success("Test message")
            mock_print.assert_called_once_with("[✓] Test message")

    def test_print_error_outputs_x(self):
        """Error message prints with X symbol."""
        renderer = PlainRenderer()
        with patch("builtins.print") as mock_print:
            renderer.print_error("Error message")
            mock_print.assert_called_once_with("[✗] Error message")

    def test_print_validation_table(self):
        """Validation results are printed as text."""
        renderer = PlainRenderer()
        results = {
            "check1": (True, "All good"),
            "check2": (False, "Failed"),
        }
        with patch("builtins.print") as mock_print:
            renderer.print_validation_table("Test Table", results)
            # Should have been called multiple times
            assert mock_print.call_count > 0

    def test_print_summary_passed(self):
        """Passed validation prints success message."""
        renderer = PlainRenderer()
        results = {"overall": {"status": "passed", "errors": []}}
        with patch("builtins.print") as mock_print:
            renderer.print_summary(results)
            # Should print success message
            assert any("✓" in str(call) for call in mock_print.call_args_list)

    def test_print_summary_failed(self):
        """Failed validation prints errors."""
        renderer = PlainRenderer()
        results = {"overall": {"status": "failed", "errors": ["Error 1", "Error 2"]}}
        with patch("builtins.print") as mock_print:
            renderer.print_summary(results)
            # Should print error messages
            assert mock_print.call_count > 0

    def test_progress_context_no_op(self):
        """Progress context yields None for plain renderer."""
        renderer = PlainRenderer()
        with renderer.progress_context(total=2) as (progress, task_id):
            assert progress is None
            assert task_id is None
            # Should not crash
            renderer.update_progress((progress, task_id), 1, "Step 1")

    def test_print_summary_handles_none_errors(self):
        """print_summary handles None errors gracefully."""
        renderer = PlainRenderer()
        results = {"overall": {"status": "failed", "errors": None}}
        with patch("builtins.print") as mock_print:
            renderer.print_summary(results)
            # Should not crash
            assert mock_print.call_count > 0


class TestDisplayManager:
    """Tests for DisplayManager facade."""

    def test_init_auto_detect_tty(self):
        """DisplayManager auto-detects TTY when no flags given."""
        manager = DisplayManager()
        # Should create either RichRenderer or PlainRenderer based on TTY
        assert manager.renderer is not None

    def test_force_rich(self):
        """force_rich=True creates RichRenderer if rich is available."""
        if RICH_AVAILABLE:
            manager = DisplayManager(force_rich=True)
            assert manager.is_rich()
        else:
            # If rich is not available, should fall back to plain
            manager = DisplayManager(force_rich=True)
            assert not manager.is_rich()

    def test_force_plain(self):
        """force_plain=True creates PlainRenderer."""
        manager = DisplayManager(force_plain=True)
        assert not manager.is_rich()

    def test_force_plain_takes_precedence(self):
        """When both force_rich and force_plain are True, plain wins."""
        manager = DisplayManager(force_rich=True, force_plain=True)
        assert not manager.is_rich()

    def test_is_rich(self):
        """is_rich() returns correct state."""
        # Plain mode
        manager = DisplayManager(force_plain=True)
        assert not manager.is_rich()

        # Rich mode (if available)
        if RICH_AVAILABLE:
            manager = DisplayManager(force_rich=True)
            assert manager.is_rich()

    def test_delegates_to_renderer(self):
        """DisplayManager delegates all methods to current renderer."""
        manager = DisplayManager(force_plain=True)

        # Should not raise any errors
        manager.print_header("Test Header")
        manager.print_info("Test Info")
        manager.print_success("Test Success")
        manager.print_warning("Test Warning")
        manager.print_error("Test Error")

        with manager.progress_context(1):
            pass

        manager.print_validation_table("Test", {"check": (True, "OK")})
        manager.print_summary({"overall": {"status": "passed", "errors": []}})


class TestDisplayManagerTTYDetection:
    """Tests for TTY detection logic."""

    def test_tty_detected_when_true(self):
        """When stdout is a TTY, rich renderer is selected."""
        with patch("sys.stdout.isatty", return_value=True):
            if RICH_AVAILABLE:
                manager = DisplayManager()
                assert manager.is_rich()

    def test_non_tty_uses_plain(self):
        """When stdout is not a TTY, plain renderer is selected."""
        with patch("sys.stdout.isatty", return_value=False):
            manager = DisplayManager()
            assert not manager.is_rich()


class TestDisplaySingleton:
    """Tests for module-level display singleton functions."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_display()

    def test_get_display_returns_singleton(self):
        """get_display returns same instance on subsequent calls."""
        display1 = get_display()
        display2 = get_display()
        assert display1 is display2

    def test_get_display_with_force_recreates(self):
        """get_display with force flags recreates the singleton."""
        display1 = get_display()
        display2 = get_display(force_plain=True)
        # Should be a new instance when force flags are used
        assert display1 is not display2

    def test_reset_display_clears_singleton(self):
        """reset_display clears the global singleton."""
        display1 = get_display()
        reset_display()
        display2 = get_display()
        assert display1 is not display2

    def test_singleton_respects_tty_detection(self):
        """Singleton auto-detects TTY on first creation."""
        with patch("sys.stdout.isatty", return_value=False):
            manager = get_display()
            assert not manager.is_rich()

        reset_display()

        with patch("sys.stdout.isatty", return_value=True):
            if RICH_AVAILABLE:
                manager = get_display()
                assert manager.is_rich()


@pytest.mark.skipif(not RICH_AVAILABLE, reason="rich not installed")
class TestRichRendererEdgeCases:
    """Edge case tests for RichRenderer."""

    def test_print_summary_with_malformed_results(self):
        """RichRenderer handles malformed results gracefully."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)

        # Empty results
        renderer.print_summary({})

        # Missing keys
        renderer.print_summary({"other_key": "value"})

        # None overall with errors
        renderer.print_summary({"overall": None, "errors": ["error"]})

    def test_print_validation_table_with_empty_results(self):
        """RichRenderer handles empty validation results."""
        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        renderer = RichRenderer(console)

        renderer.print_validation_table("Empty Table", {})

        output = console.file.getvalue()
        assert "Empty Table" in output


class TestDisplayManagerEdgeCases:
    """Edge case tests for DisplayManager."""

    def test_handles_rich_not_available(self):
        """DisplayManager works when rich is not available."""
        with patch("tg_wp_bridge.display.RICH_AVAILABLE", False):
            manager = DisplayManager(force_rich=True)
            # Should fall back to plain renderer
            assert not manager.is_rich()
            assert isinstance(manager.renderer, PlainRenderer)

    def test_update_progress_with_none_progress(self):
        """update_progress handles None progress object gracefully."""
        manager = DisplayManager(force_plain=True)
        # Should not crash
        manager.update_progress(None, 1, "Test")

    def test_print_validation_table_with_malformed_data(self):
        """DisplayManager raises error for malformed validation data."""
        manager = DisplayManager(force_plain=True)

        # Empty results - should work
        manager.print_validation_table("Empty", {})

        # Results with non-tuple values - should raise ValueError
        with pytest.raises(ValueError, match="too many values to unpack"):
            manager.print_validation_table("Malformed", {"check1": "not a tuple"})

        # Results with None values - should raise TypeError
        with pytest.raises(TypeError):
            manager.print_validation_table("With None", {"check1": None})
