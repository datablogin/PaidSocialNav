"""Tests for CLI output formatting utilities."""

from __future__ import annotations

from paid_social_nav.cli import output
from paid_social_nav.cli.output import OutputColor


def test_success_with_prefix(capsys: any) -> None:
    """Test success message includes checkmark emoji by default."""
    output.success("Test message")
    captured = capsys.readouterr()
    assert "✅ Test message" in captured.out


def test_success_without_prefix(capsys: any) -> None:
    """Test success message without emoji prefix."""
    output.success("Test message", prefix=False)
    captured = capsys.readouterr()
    assert "✅" not in captured.out
    assert "Test message" in captured.out


def test_error_with_prefix(capsys: any) -> None:
    """Test error message includes cross emoji by default."""
    output.error("Error message", err=False)  # Don't write to stderr for test
    captured = capsys.readouterr()
    assert "❌ Error message" in captured.out


def test_error_without_prefix(capsys: any) -> None:
    """Test error message without emoji prefix."""
    output.error("Error message", prefix=False, err=False)
    captured = capsys.readouterr()
    assert "❌" not in captured.out
    assert "Error message" in captured.out


def test_error_writes_to_stderr(capsys: any) -> None:
    """Test error message writes to stderr by default."""
    output.error("Error message")
    captured = capsys.readouterr()
    assert "❌ Error message" in captured.err
    assert captured.out == ""


def test_info_with_prefix(capsys: any) -> None:
    """Test info message includes info emoji by default."""
    output.info("Info message")
    captured = capsys.readouterr()
    assert "ℹ️" in captured.out
    assert "Info message" in captured.out


def test_info_without_prefix(capsys: any) -> None:
    """Test info message without emoji prefix."""
    output.info("Info message", prefix=False)
    captured = capsys.readouterr()
    assert "ℹ️" not in captured.out
    assert "Info message" in captured.out


def test_warning_with_prefix(capsys: any) -> None:
    """Test warning message includes warning emoji by default."""
    output.warning("Warning message")
    captured = capsys.readouterr()
    assert "⚠️" in captured.out
    assert "Warning message" in captured.out


def test_warning_without_prefix(capsys: any) -> None:
    """Test warning message without emoji prefix."""
    output.warning("Warning message", prefix=False)
    captured = capsys.readouterr()
    assert "⚠️" not in captured.out
    assert "Warning message" in captured.out


def test_plain_no_color(capsys: any) -> None:
    """Test plain message without color."""
    output.plain("Plain message")
    captured = capsys.readouterr()
    assert "Plain message" in captured.out
    # Should not have any emoji
    assert "✅" not in captured.out
    assert "❌" not in captured.out
    assert "ℹ️" not in captured.out
    assert "⚠️" not in captured.out


def test_plain_with_color(capsys: any) -> None:
    """Test plain message with color uses enum."""
    output.plain("Colored message", color=OutputColor.CYAN)
    captured = capsys.readouterr()
    assert "Colored message" in captured.out


def test_data_with_prefix(capsys: any) -> None:
    """Test data message includes chart emoji by default."""
    output.data("Google Sheets")
    captured = capsys.readouterr()
    assert "📊 Google Sheets" in captured.out


def test_data_without_prefix(capsys: any) -> None:
    """Test data message without emoji prefix."""
    output.data("Google Sheets", prefix=False)
    captured = capsys.readouterr()
    assert "📊" not in captured.out
    assert "Google Sheets" in captured.out


def test_output_color_enum_values() -> None:
    """Test OutputColor enum has expected values."""
    assert OutputColor.WHITE.value == "WHITE"
    assert OutputColor.CYAN.value == "CYAN"
    assert OutputColor.GREEN.value == "GREEN"
    assert OutputColor.YELLOW.value == "YELLOW"
    assert OutputColor.RED.value == "RED"
    assert OutputColor.MAGENTA.value == "MAGENTA"
    assert OutputColor.BLUE.value == "BLUE"


def test_output_color_enum_type_safety() -> None:
    """Test that OutputColor enum provides type safety."""
    # This should work
    output.plain("Test", color=OutputColor.GREEN)

    # This would fail type checking if we tried it with a string:
    # output.plain("Test", color="GREEN")  # type: ignore
