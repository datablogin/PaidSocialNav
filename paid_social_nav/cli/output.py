"""Console output formatting utilities for consistent CLI user experience.

This module provides helper functions for standardized console output across
all CLI commands with consistent emoji, color schemes, and formatting patterns.

Logging Strategy:
- Use console output functions (success, error, info, warning) for user-facing messages
- Use structured logging (logger.info, logger.error, etc.) for debugging and observability
- Console output is for immediate feedback; logging is for analysis and troubleshooting
"""

from __future__ import annotations

from enum import Enum

import typer


class OutputColor(str, Enum):
    """Valid color options for plain text output."""

    WHITE = "WHITE"
    CYAN = "CYAN"
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    MAGENTA = "MAGENTA"
    BLUE = "BLUE"


def success(message: str, *, prefix: bool = True) -> None:
    """Display a success message in green with checkmark emoji.

    Args:
        message: The success message to display
        prefix: Whether to include the checkmark emoji prefix (default: True)

    Example:
        success("Report written to output.pdf")
        # Output: ✅ Report written to output.pdf
    """
    formatted = f"✅ {message}" if prefix else message
    typer.secho(formatted, fg=typer.colors.GREEN)


def error(message: str, *, prefix: bool = True, err: bool = True) -> None:
    """Display an error message in red with cross emoji.

    Args:
        message: The error message to display
        prefix: Whether to include the cross emoji prefix (default: True)
        err: Whether to write to stderr instead of stdout (default: True)

    Example:
        error("Config file not found: config.yaml")
        # Output: ❌ Config file not found: config.yaml
    """
    formatted = f"❌ {message}" if prefix else message
    typer.secho(formatted, fg=typer.colors.RED, err=err)


def info(message: str, *, prefix: bool = True) -> None:
    """Display an informational message in cyan with info emoji.

    Args:
        message: The informational message to display
        prefix: Whether to include the info emoji prefix (default: True)

    Example:
        info("Processing 5 records...")
        # Output: ℹ️  Processing 5 records...
    """
    formatted = f"ℹ️  {message}" if prefix else message
    typer.secho(formatted, fg=typer.colors.CYAN)


def warning(message: str, *, prefix: bool = True) -> None:
    """Display a warning message in yellow with warning emoji.

    Args:
        message: The warning message to display
        prefix: Whether to include the warning emoji prefix (default: True)

    Example:
        warning("Using default configuration")
        # Output: ⚠️  Using default configuration
    """
    formatted = f"⚠️  {message}" if prefix else message
    typer.secho(formatted, fg=typer.colors.YELLOW)


def plain(message: str, *, color: OutputColor | None = None) -> None:
    """Display a plain message without emoji prefix.

    Args:
        message: The message to display
        color: Optional color from OutputColor enum

    Example:
        from paid_social_nav.cli.output import OutputColor
        plain("Additional details here", color=OutputColor.WHITE)
        # Output: Additional details here (in white)
    """
    if color:
        typer.secho(message, fg=getattr(typer.colors, color.value))
    else:
        typer.echo(message)


def data(message: str, *, prefix: bool = True) -> None:
    """Display a data/sheets message in cyan with chart emoji.

    Args:
        message: The data message to display
        prefix: Whether to include the chart emoji prefix (default: True)

    Example:
        data("Google Sheets:")
        # Output: 📊 Google Sheets:
    """
    formatted = f"📊 {message}" if prefix else message
    typer.secho(formatted, fg=typer.colors.CYAN)
