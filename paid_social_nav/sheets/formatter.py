"""Formatting utilities for Google Sheets."""

from __future__ import annotations

from typing import Any


class SheetFormatter:
    """Utilities for formatting Google Sheets with colors and conditional formatting."""

    # Color definitions (RGB 0-1 scale)
    COLORS = {
        "header_bg": {"red": 0.4, "green": 0.49, "blue": 0.91},  # Purple
        "header_text": {"red": 1.0, "green": 1.0, "blue": 1.0},  # White
        "score_excellent": {"red": 0.22, "green": 0.73, "blue": 0.29},  # Green
        "score_good": {"red": 0.6, "green": 0.8, "blue": 0.2},  # Yellow-green
        "score_fair": {"red": 1.0, "green": 0.76, "blue": 0.03},  # Yellow
        "score_poor": {"red": 0.91, "green": 0.26, "blue": 0.21},  # Red
        "alt_row": {"red": 0.97, "green": 0.97, "blue": 0.97},  # Light gray
    }

    @staticmethod
    def get_header_format() -> dict[str, Any]:
        """Get formatting for header rows."""
        return {
            "backgroundColor": SheetFormatter.COLORS["header_bg"],
            "textFormat": {
                "foregroundColor": SheetFormatter.COLORS["header_text"],
                "bold": True,
                "fontSize": 10,
            },
            "horizontalAlignment": "CENTER",
        }

    @staticmethod
    def get_score_color(score: float) -> dict[str, float]:
        """Get color based on score value.

        Args:
            score: Score value (0-100)

        Returns:
            RGB color dict
        """
        if score >= 90:
            return SheetFormatter.COLORS["score_excellent"]
        elif score >= 75:
            return SheetFormatter.COLORS["score_good"]
        elif score >= 60:
            return SheetFormatter.COLORS["score_fair"]
        else:
            return SheetFormatter.COLORS["score_poor"]

    @staticmethod
    def create_alternating_row_format(
        sheet_id: int, start_row: int, end_row: int, num_columns: int
    ) -> dict[str, Any]:
        """Create alternating row background formatting.

        Args:
            sheet_id: ID of the sheet to format
            start_row: Starting row index (0-based)
            end_row: Ending row index (0-based, exclusive)
            num_columns: Number of columns to format

        Returns:
            Request dict for repeatCell formatting
        """
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_columns,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": SheetFormatter.COLORS["alt_row"]
                    }
                },
                "fields": "userEnteredFormat.backgroundColor",
            }
        }

    @staticmethod
    def create_conditional_format_rule(
        sheet_id: int,
        start_row: int,
        end_row: int,
        column_index: int,
        threshold_type: str = "NUMBER_GREATER_THAN_EQ",
        threshold_value: float = 90.0,
        color: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Create a conditional formatting rule.

        Args:
            sheet_id: ID of the sheet
            start_row: Starting row index (0-based)
            end_row: Ending row index (0-based, exclusive)
            column_index: Column to apply formatting to (0-based)
            threshold_type: Type of condition (NUMBER_GREATER_THAN_EQ, etc.)
            threshold_value: Threshold value for condition
            color: RGB color dict (defaults to excellent green)

        Returns:
            Request dict for conditional formatting rule
        """
        if color is None:
            color = SheetFormatter.COLORS["score_excellent"]

        return {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [
                        {
                            "sheetId": sheet_id,
                            "startRowIndex": start_row,
                            "endRowIndex": end_row,
                            "startColumnIndex": column_index,
                            "endColumnIndex": column_index + 1,
                        }
                    ],
                    "booleanRule": {
                        "condition": {
                            "type": threshold_type,
                            "values": [{"userEnteredValue": str(threshold_value)}],
                        },
                        "format": {"backgroundColor": color},
                    },
                },
                "index": 0,
            }
        }

    @staticmethod
    def create_freeze_rows_request(sheet_id: int, num_rows: int = 1) -> dict[str, Any]:
        """Create request to freeze top rows.

        Args:
            sheet_id: ID of the sheet
            num_rows: Number of rows to freeze (default: 1 for header)

        Returns:
            Request dict to freeze rows
        """
        return {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": num_rows},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }

    @staticmethod
    def create_auto_resize_request(
        sheet_id: int, start_column: int, end_column: int
    ) -> dict[str, Any]:
        """Create request to auto-resize columns.

        Args:
            sheet_id: ID of the sheet
            start_column: Starting column index (0-based)
            end_column: Ending column index (0-based, exclusive)

        Returns:
            Request dict to auto-resize columns
        """
        return {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start_column,
                    "endIndex": end_column,
                }
            }
        }
