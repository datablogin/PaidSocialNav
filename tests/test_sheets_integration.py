"""Tests for Google Sheets integration."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from paid_social_nav.sheets.exporter import GoogleSheetsExporter
from paid_social_nav.sheets.formatter import SheetFormatter


class TestSheetFormatter:
    """Test cases for SheetFormatter."""

    def test_get_header_format(self) -> None:
        """Test header format generation."""
        format_dict = SheetFormatter.get_header_format()
        assert "backgroundColor" in format_dict
        assert "textFormat" in format_dict
        assert format_dict["textFormat"]["bold"] is True
        assert format_dict["horizontalAlignment"] == "CENTER"

    def test_get_score_color_excellent(self) -> None:
        """Test color for excellent score (>= 90)."""
        color = SheetFormatter.get_score_color(95.0)
        assert color == SheetFormatter.COLORS["score_excellent"]

    def test_get_score_color_good(self) -> None:
        """Test color for good score (75-89)."""
        color = SheetFormatter.get_score_color(80.0)
        assert color == SheetFormatter.COLORS["score_good"]

    def test_get_score_color_fair(self) -> None:
        """Test color for fair score (60-74)."""
        color = SheetFormatter.get_score_color(65.0)
        assert color == SheetFormatter.COLORS["score_fair"]

    def test_get_score_color_poor(self) -> None:
        """Test color for poor score (< 60)."""
        color = SheetFormatter.get_score_color(45.0)
        assert color == SheetFormatter.COLORS["score_poor"]

    def test_create_alternating_row_format(self) -> None:
        """Test alternating row format creation."""
        result = SheetFormatter.create_alternating_row_format(
            sheet_id=123, start_row=1, end_row=10, num_columns=5
        )
        assert "repeatCell" in result
        assert result["repeatCell"]["range"]["sheetId"] == 123
        assert result["repeatCell"]["range"]["startRowIndex"] == 1
        assert result["repeatCell"]["range"]["endRowIndex"] == 10

    def test_create_conditional_format_rule(self) -> None:
        """Test conditional formatting rule creation."""
        result = SheetFormatter.create_conditional_format_rule(
            sheet_id=123,
            start_row=1,
            end_row=10,
            column_index=3,
            threshold_type="NUMBER_GREATER_THAN_EQ",
            threshold_value=90.0,
        )
        assert "addConditionalFormatRule" in result
        assert result["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["type"] == "NUMBER_GREATER_THAN_EQ"

    def test_create_freeze_rows_request(self) -> None:
        """Test freeze rows request creation."""
        result = SheetFormatter.create_freeze_rows_request(sheet_id=123, num_rows=1)
        assert "updateSheetProperties" in result
        assert result["updateSheetProperties"]["properties"]["gridProperties"]["frozenRowCount"] == 1

    def test_create_auto_resize_request(self) -> None:
        """Test auto-resize columns request creation."""
        result = SheetFormatter.create_auto_resize_request(
            sheet_id=123, start_column=0, end_column=5
        )
        assert "autoResizeDimensions" in result
        assert result["autoResizeDimensions"]["dimensions"]["dimension"] == "COLUMNS"


class TestGoogleSheetsExporter:
    """Test cases for GoogleSheetsExporter."""

    def test_init_without_credentials(self) -> None:
        """Test initialization without credentials raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Google Sheets credentials not configured"):
                GoogleSheetsExporter()

    def test_init_with_missing_file(self) -> None:
        """Test initialization with non-existent credentials file."""
        with pytest.raises(ValueError, match="Credentials file not found"):
            GoogleSheetsExporter("/path/to/nonexistent/file.json")

    @patch("paid_social_nav.sheets.exporter.service_account.Credentials.from_service_account_file")
    @patch("paid_social_nav.sheets.exporter.build")
    def test_init_with_valid_credentials(
        self, mock_build: Mock, mock_creds: Mock, tmp_path: Path
    ) -> None:
        """Test successful initialization with valid credentials."""
        # Create a temporary credentials file
        creds_file = tmp_path / "service-account.json"
        creds_file.write_text('{"type": "service_account"}')

        # Mock the credentials and service
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        exporter = GoogleSheetsExporter(str(creds_file))
        assert exporter.service is not None
        assert exporter.formatter is not None

    @patch("paid_social_nav.sheets.exporter.service_account.Credentials.from_service_account_file")
    @patch("paid_social_nav.sheets.exporter.build")
    def test_format_findings(self, mock_build: Mock, mock_creds: Mock, tmp_path: Path) -> None:
        """Test findings formatting."""
        # Setup
        creds_file = tmp_path / "service-account.json"
        creds_file.write_text('{"type": "service_account"}')
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        exporter = GoogleSheetsExporter(str(creds_file))

        # Test with various finding types
        findings = {
            "actual": 1234.56,
            "target": 2000.00,
            "items": [1, 2, 3],
            "status": "active",
        }

        result = exporter._format_findings(findings)
        assert "actual: 1234.56" in result
        assert "target: 2000.00" in result
        assert "items: 3 items" in result
        assert "status: active" in result

    @patch("paid_social_nav.sheets.exporter.service_account.Credentials.from_service_account_file")
    @patch("paid_social_nav.sheets.exporter.build")
    def test_format_findings_empty(
        self, mock_build: Mock, mock_creds: Mock, tmp_path: Path
    ) -> None:
        """Test formatting empty findings."""
        creds_file = tmp_path / "service-account.json"
        creds_file.write_text('{"type": "service_account"}')
        mock_creds.return_value = MagicMock()
        mock_build.return_value = MagicMock()

        exporter = GoogleSheetsExporter(str(creds_file))
        result = exporter._format_findings({})
        assert result == "No findings"

    @patch("paid_social_nav.sheets.exporter.service_account.Credentials.from_service_account_file")
    @patch("paid_social_nav.sheets.exporter.build")
    def test_export_audit_data_success(
        self, mock_build: Mock, mock_creds: Mock, tmp_path: Path
    ) -> None:
        """Test successful audit data export."""
        # Setup
        creds_file = tmp_path / "service-account.json"
        creds_file.write_text('{"type": "service_account"}')
        mock_creds.return_value = MagicMock()

        # Mock the Sheets API service
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet creation
        mock_spreadsheet = {
            "spreadsheetId": "test_sheet_123",
            "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/test_sheet_123/edit",
            "sheets": [
                {
                    "properties": {
                        "sheetId": 0,
                        "title": "Sheet1",
                    }
                }
            ],
        }
        mock_service.spreadsheets().create().execute.return_value = mock_spreadsheet
        mock_service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {"properties": {"sheetId": 0, "title": "Executive Summary"}},
                {"properties": {"sheetId": 1, "title": "Rule Details"}},
                {"properties": {"sheetId": 2, "title": "Raw Data"}},
            ]
        }
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}
        mock_service.spreadsheets().values().update().execute.return_value = {}

        exporter = GoogleSheetsExporter(str(creds_file))

        # Test data
        rules = [
            {
                "rule": "pacing_vs_target",
                "window": "2024-01",
                "level": "account",
                "score": 85.5,
                "findings": {"actual": 1000, "target": 1200},
            }
        ]

        # Execute
        result = exporter.export_audit_data(
            tenant_name="test_tenant",
            audit_date="2025-01-22",
            overall_score=85.5,
            rules=rules,
            period="2024-01",
            insights=None,
        )

        # Verify
        assert result == "https://docs.google.com/spreadsheets/d/test_sheet_123/edit"
        assert mock_service.spreadsheets().create.called
        assert mock_service.spreadsheets().batchUpdate.called

    @patch("paid_social_nav.sheets.exporter.service_account.Credentials.from_service_account_file")
    @patch("paid_social_nav.sheets.exporter.build")
    def test_export_audit_data_with_insights(
        self, mock_build: Mock, mock_creds: Mock, tmp_path: Path
    ) -> None:
        """Test export with AI insights."""
        # Setup
        creds_file = tmp_path / "service-account.json"
        creds_file.write_text('{"type": "service_account"}')
        mock_creds.return_value = MagicMock()

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_spreadsheet = {
            "spreadsheetId": "test_sheet_123",
            "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/test_sheet_123/edit",
            "sheets": [{"properties": {"sheetId": 0, "title": "Sheet1"}}],
        }
        mock_service.spreadsheets().create().execute.return_value = mock_spreadsheet
        mock_service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {"properties": {"sheetId": 0, "title": "Executive Summary"}},
                {"properties": {"sheetId": 1, "title": "Rule Details"}},
                {"properties": {"sheetId": 2, "title": "Raw Data"}},
            ]
        }
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}
        mock_service.spreadsheets().values().update().execute.return_value = {}

        exporter = GoogleSheetsExporter(str(creds_file))

        rules = [
            {
                "rule": "pacing_vs_target",
                "window": "2024-01",
                "level": "account",
                "score": 85.5,
                "findings": {},
            }
        ]

        insights = {
            "recommendations": [
                {
                    "title": "Optimize Budget",
                    "description": "Adjust budget allocation",
                    "expected_impact": "10% improvement",
                }
            ],
            "strengths": [
                {"title": "Good CTR", "description": "CTR above benchmark"}
            ],
            "issues": [
                {"title": "Low Frequency", "severity": "medium", "description": "Increase frequency"}
            ],
        }

        result = exporter.export_audit_data(
            tenant_name="test_tenant",
            audit_date="2025-01-22",
            overall_score=85.5,
            rules=rules,
            period="2024-01",
            insights=insights,
        )

        assert result == "https://docs.google.com/spreadsheets/d/test_sheet_123/edit"

    @patch("paid_social_nav.sheets.exporter.service_account.Credentials.from_service_account_file")
    @patch("paid_social_nav.sheets.exporter.build")
    def test_export_audit_data_api_error(
        self, mock_build: Mock, mock_creds: Mock, tmp_path: Path
    ) -> None:
        """Test export failure due to API error."""
        from googleapiclient.errors import HttpError  # type: ignore[import-not-found]

        # Setup
        creds_file = tmp_path / "service-account.json"
        creds_file.write_text('{"type": "service_account"}')
        mock_creds.return_value = MagicMock()

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Simulate API error
        mock_service.spreadsheets().create().execute.side_effect = HttpError(
            resp=MagicMock(status=500), content=b"Internal Server Error"
        )

        exporter = GoogleSheetsExporter(str(creds_file))

        with pytest.raises(RuntimeError, match="Failed to export to Google Sheets"):
            exporter.export_audit_data(
                tenant_name="test_tenant",
                audit_date="2025-01-22",
                overall_score=85.5,
                rules=[],
                period="2024-01",
                insights=None,
            )
