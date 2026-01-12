"""
Display and output rendering for tg-wp-bridge.

Provides TTY-aware output with rich formatting when available,
gracefully degrading to plain text for logs and non-interactive use.

This module implements an Adapter pattern for output rendering:
- OutputRenderer: Abstract base class defining the display interface
- RichRenderer: Rich console output with colors, tables, and progress indicators
- PlainRenderer: Simple text fallback for non-TTY environments
- DisplayManager: Facade that auto-detects appropriate renderer
"""

import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple

# Conditional rich imports
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class OutputRenderer(ABC):
    """
    Abstract base class for output rendering strategies.

    All renderers must implement these methods to provide
    consistent output across different display backends.
    """

    @abstractmethod
    def print_header(self, title: str) -> None:
        """Print a section header."""
        pass

    @abstractmethod
    def print_info(self, message: str) -> None:
        """Print an informational message."""
        pass

    @abstractmethod
    def print_success(self, message: str) -> None:
        """Print a success message."""
        pass

    @abstractmethod
    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        pass

    @abstractmethod
    def print_error(self, message: str) -> None:
        """Print an error message."""
        pass

    @abstractmethod
    @contextmanager
    def progress_context(self, total: int):
        """Context manager for progress tracking during operations."""
        pass

    @abstractmethod
    def update_progress(
        self, progress_obj: Any, advance: int, description: str
    ) -> None:
        """Update progress display."""
        pass

    @abstractmethod
    def print_validation_table(
        self, title: str, results: Dict[str, Tuple[bool, str]]
    ) -> None:
        """Print validation results as a table."""
        pass

    @abstractmethod
    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print final validation summary."""
        pass

    @abstractmethod
    def is_interactive(self) -> bool:
        """Return True if this renderer supports interactive output."""
        pass


class RichRenderer(OutputRenderer):
    """
    Rich console output with colors, tables, and progress indicators.

    This renderer uses the rich library to provide visually appealing
    output with colors, tables, panels, and progress bars.
    """

    def __init__(self, console: Optional[Console] = None) -> None:
        """
        Initialize the rich renderer.

        Args:
            console: Optional rich Console instance. If None, creates a new one.
        """
        if not RICH_AVAILABLE:
            raise ImportError("rich library is not available")
        self.console = console or Console()

    def print_header(self, title: str) -> None:
        """Print a formatted header panel."""
        self.console.print(Panel(title, border_style="bold blue", padding=(0, 1)))

    def print_info(self, message: str) -> None:
        """Print an informational message in cyan."""
        self.console.print(f"[cyan]{message}[/cyan]")

    def print_success(self, message: str) -> None:
        """Print a success message with green checkmark."""
        self.console.print(f"[green]✓[/green] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message with yellow triangle."""
        self.console.print(f"[yellow]⚠[/yellow] {message}")

    def print_error(self, message: str) -> None:
        """Print an error message with red X."""
        self.console.print(f"[red]✗[/red] {message}")

    @contextmanager
    def progress_context(self, total: int):
        """
        Create a progress tracking context.

        Yields a tuple of (progress, task_id) that can be used
        with update_progress().
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        )
        with progress:
            task = progress.add_task("Processing...", total=total)
            yield (progress, task)

    def update_progress(
        self, progress_obj: Any, advance: int, description: str
    ) -> None:
        """Update progress display with new advance and description."""
        progress, task_id = progress_obj
        progress.update(task_id, advance=advance, description=description)

    def print_validation_table(
        self, title: str, results: Dict[str, Tuple[bool, str]]
    ) -> None:
        """Print validation results as a formatted table."""
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("Check", style="cyan", width=30)
        table.add_column("Status", style="bold", width=10)
        table.add_column("Details", style="white")

        for check_name, (is_valid, message) in results.items():
            status = "[green]✓ PASS[/green]" if is_valid else "[red]✗ FAIL[/red]"
            table.add_row(check_name, status, message)

        self.console.print(table)

    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print final validation summary as a panel."""
        overall = results.get("overall") or {}
        if not isinstance(overall, dict):
            overall = {}
        status = overall.get("status", "unknown")
        errors = overall.get("errors") or []

        if status == "passed":
            self.console.print(
                Panel(
                    "[bold green]✓ All validations passed![/bold green]\n\n"
                    "The application is ready to handle requests.",
                    title="[bold green]Startup Complete[/bold green]",
                    border_style="green",
                )
            )
        else:
            error_text = "\n".join(f"  • {err}" for err in errors)
            self.console.print(
                Panel(
                    f"[bold red]✗ Validation failed[/bold red]\n\n{error_text}",
                    title="[bold red]Startup Errors[/bold red]",
                    border_style="red",
                )
            )

    def is_interactive(self) -> bool:
        """Rich renderer supports interactive output."""
        return True


class PlainRenderer(OutputRenderer):
    """
    Plain text fallback for non-TTY environments.

    This renderer provides simple text output without colors or
    special formatting, suitable for log files and CI/CD environments.
    """

    def print_header(self, title: str) -> None:
        """Print a plain text header with separator lines."""
        print(f"\n{'=' * 60}")
        print(f" {title}")
        print(f"{'=' * 60}\n")

    def print_info(self, message: str) -> None:
        """Print an informational message."""
        print(message)

    def print_success(self, message: str) -> None:
        """Print a success message with checkmark."""
        print(f"[✓] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message with warning symbol."""
        print(f"[!] {message}")

    def print_error(self, message: str) -> None:
        """Print an error message with X symbol."""
        print(f"[✗] {message}")

    @contextmanager
    def progress_context(self, total: int):
        """
        No-op progress context for plain text.

        Yields None for both progress and task_id since
        plain text doesn't support progress bars.
        """
        yield (None, None)

    def update_progress(
        self, progress_obj: Any, advance: int, description: str
    ) -> None:
        """No-op for plain text renderer."""
        pass

    def print_validation_table(
        self, title: str, results: Dict[str, Tuple[bool, str]]
    ) -> None:
        """Print validation results as plain text."""
        print(f"\n{title}:")
        print("-" * 60)
        for check_name, (is_valid, message) in results.items():
            status = "[PASS]" if is_valid else "[FAIL]"
            print(f"  {status} {check_name}: {message}")

    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print final validation summary as plain text."""
        overall = results.get("overall") or {}
        if not isinstance(overall, dict):
            overall = {}
        status = overall.get("status", "unknown")
        errors = overall.get("errors") or []

        print(f"\n{'=' * 60}")
        print(" SUMMARY")
        print(f"{'=' * 60}")

        if status == "passed":
            print("[✓] All validations passed!")
            print("    The application is ready to handle requests.")
        else:
            print("[✗] Validation failed:")
            for error in errors:
                print(f"    • {error}")
        print(f"{'=' * 60}\n")

    def is_interactive(self) -> bool:
        """Plain renderer does not support interactive output."""
        return False


class DisplayManager:
    """
    Main display facade that auto-detects and delegates to appropriate renderer.

    This class provides a unified interface for output that automatically
    chooses the best renderer based on the runtime environment:

    - In a TTY (interactive terminal): Uses RichRenderer for colored output
    - In a pipe or log file: Uses PlainRenderer for simple text
    - With force_rich=True: Always uses RichRenderer
    - With force_plain=True: Always uses PlainRenderer

    Usage:
        display = DisplayManager()  # Auto-detects TTY
        display.print_header("Starting validation")
        display.print_success("Everything works!")

        # Force specific mode
        display = DisplayManager(force_rich=True)
        display = DisplayManager(force_plain=True)
    """

    def __init__(self, force_rich: bool = False, force_plain: bool = False) -> None:
        """
        Initialize display manager with appropriate renderer.

        Args:
            force_rich: Force rich output even in non-TTY
            force_plain: Force plain text even in TTY

        Note:
            If both force_rich and force_plain are True, force_plain takes precedence.
            If rich is not available, falls back to PlainRenderer.
        """
        if force_plain:
            self.renderer = PlainRenderer()
        elif force_rich and RICH_AVAILABLE:
            self.renderer = RichRenderer()
        elif RICH_AVAILABLE and sys.stdout.isatty():
            self.renderer = RichRenderer()
        else:
            self.renderer = PlainRenderer()

    def is_rich(self) -> bool:
        """Check if currently using rich renderer."""
        return isinstance(self.renderer, RichRenderer)

    def is_interactive(self) -> bool:
        """Check if current renderer supports interactive output."""
        return self.renderer.is_interactive()

    # Delegate all methods to current renderer
    def print_header(self, title: str) -> None:
        """Print a section header."""
        self.renderer.print_header(title)

    def print_info(self, message: str) -> None:
        """Print an informational message."""
        self.renderer.print_info(message)

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.renderer.print_success(message)

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        self.renderer.print_warning(message)

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.renderer.print_error(message)

    def progress_context(self, total: int = 1):
        """Context manager for progress tracking - delegates to renderer."""
        return self.renderer.progress_context(total)

    def update_progress(
        self, progress_obj: Any, advance: int, description: str
    ) -> None:
        """Update progress display."""
        self.renderer.update_progress(progress_obj, advance, description)

    def print_validation_table(
        self, title: str, results: Dict[str, Tuple[bool, str]]
    ) -> None:
        """Print validation results as a table."""
        self.renderer.print_validation_table(title, results)

    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print final validation summary."""
        self.renderer.print_summary(results)


# Export a default singleton instance for convenience
_default_display: Optional[DisplayManager] = None


def get_display(force_rich: bool = False, force_plain: bool = False) -> DisplayManager:
    """
    Get or create the default display manager.

    Args:
        force_rich: Force rich output
        force_plain: Force plain output

    Returns:
        DisplayManager instance
    """
    global _default_display
    if _default_display is None or force_rich or force_plain:
        _default_display = DisplayManager(
            force_rich=force_rich, force_plain=force_plain
        )
    return _default_display


def reset_display() -> None:
    """Reset the default display manager (useful for testing)."""
    global _default_display
    _default_display = None
