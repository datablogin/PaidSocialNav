"""Google Sheets exporter for audit data."""

from __future__ import annotations

import os
from typing import Any

from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore[import-not-found]
from googleapiclient.errors import HttpError  # type: ignore[import-not-found]

from ..core.logging_config import get_logger
from .formatter import SheetFormatter

logger = get_logger(__name__)


class GoogleSheetsExporter:
    """Export audit data to Google Sheets with formatted tabs."""

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, credentials_path: str | None = None) -> None:
        """Initialize the Google Sheets exporter.

        Args:
            credentials_path: Path to service account JSON credentials.
                             If None, reads from GOOGLE_APPLICATION_CREDENTIALS env var.

        Raises:
            ValueError: If credentials are not found or invalid
        """
        if credentials_path is None:
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not credentials_path:
            raise ValueError(
                "Google Sheets credentials not configured. "
                "Set GOOGLE_APPLICATION_CREDENTIALS environment variable "
                "or pass credentials_path to GoogleSheetsExporter."
            )

        if not os.path.exists(credentials_path):
            raise ValueError(f"Credentials file not found: {credentials_path}")

        try:
            self.credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                credentials_path, scopes=self.SCOPES
            )
            self.service = build("sheets", "v4", credentials=self.credentials)
            logger.info(
                "Google Sheets API initialized",
                extra={"credentials_path": credentials_path},
            )
        except (DefaultCredentialsError, Exception) as e:
            logger.error(
                "Failed to initialize Google Sheets API",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise ValueError(f"Failed to load credentials: {e}") from e

        self.formatter = SheetFormatter()

    def export_audit_data(
        self,
        tenant_name: str,
        audit_date: str,
        overall_score: float,
        rules: list[dict[str, Any]],
        period: str,
        insights: dict[str, Any] | None = None,
    ) -> str:
        """Export audit data to a new Google Sheet.

        Args:
            tenant_name: Name of the tenant being audited
            audit_date: Date of the audit (YYYY-MM-DD)
            overall_score: Overall audit score (0-100)
            rules: List of rule results with scores and findings
            period: Time period covered by the audit
            insights: Optional AI-generated insights

        Returns:
            URL of the created Google Sheet

        Raises:
            RuntimeError: If sheet creation or update fails
        """
        try:
            # Create the spreadsheet
            sheet_title = f"{tenant_name} Audit {audit_date}"
            spreadsheet = self._create_spreadsheet(sheet_title)
            spreadsheet_id = spreadsheet["spreadsheetId"]
            spreadsheet_url = spreadsheet["spreadsheetUrl"]

            logger.info(
                "Created Google Sheet",
                extra={
                    "spreadsheet_id": spreadsheet_id,
                    "title": sheet_title,
                },
            )

            # Get sheet IDs for the default sheet (will be renamed to Executive Summary)
            sheets = spreadsheet.get("sheets", [])
            if not sheets:
                raise RuntimeError("No sheets found in created spreadsheet")

            exec_summary_sheet_id = sheets[0]["properties"]["sheetId"]

            # Build all tabs
            batch_requests: list[dict[str, Any]] = []

            # 1. Rename first sheet to "Executive Summary" and populate it
            batch_requests.append(
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": exec_summary_sheet_id,
                            "title": "Executive Summary",
                        },
                        "fields": "title",
                    }
                }
            )

            # 2. Add "Rule Details" sheet
            batch_requests.append(
                {
                    "addSheet": {
                        "properties": {
                            "title": "Rule Details",
                            "gridProperties": {"rowCount": 1000, "columnCount": 10},
                        }
                    }
                }
            )

            # 3. Add "Raw Data" sheet
            batch_requests.append(
                {
                    "addSheet": {
                        "properties": {
                            "title": "Raw Data",
                            "gridProperties": {"rowCount": 1000, "columnCount": 15},
                        }
                    }
                }
            )

            # Execute batch update to create sheets
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body={"requests": batch_requests}
            ).execute()

            # Get updated sheet information
            spreadsheet = (
                self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            )
            sheets = spreadsheet.get("sheets", [])

            # Map sheet titles to IDs
            sheet_id_map = {
                sheet["properties"]["title"]: sheet["properties"]["sheetId"]
                for sheet in sheets
            }

            # Populate Executive Summary
            self._populate_executive_summary(
                spreadsheet_id,
                sheet_id_map["Executive Summary"],
                tenant_name,
                audit_date,
                overall_score,
                period,
                rules,
                insights,
            )

            # Populate Rule Details
            self._populate_rule_details(
                spreadsheet_id, sheet_id_map["Rule Details"], rules
            )

            # Populate Raw Data
            self._populate_raw_data(
                spreadsheet_id, sheet_id_map["Raw Data"], rules, insights
            )

            logger.info(
                "Successfully exported audit data to Google Sheets",
                extra={
                    "spreadsheet_id": spreadsheet_id,
                    "url": spreadsheet_url,
                    "tenant": tenant_name,
                },
            )

            return str(spreadsheet_url)

        except HttpError as e:
            logger.error(
                "Google Sheets API error during export",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise RuntimeError(f"Failed to export to Google Sheets: {e}") from e
        except Exception as e:
            logger.error(
                "Unexpected error during Google Sheets export",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise RuntimeError(f"Failed to export to Google Sheets: {e}") from e

    def _create_spreadsheet(self, title: str) -> dict[str, Any]:
        """Create a new spreadsheet.

        Args:
            title: Title for the spreadsheet

        Returns:
            Spreadsheet metadata dict
        """
        spreadsheet_body = {
            "properties": {"title": title},
            "sheets": [
                {
                    "properties": {
                        "title": "Sheet1",
                        "gridProperties": {"rowCount": 100, "columnCount": 10},
                    }
                }
            ],
        }

        result: dict[str, Any] = (
            self.service.spreadsheets().create(body=spreadsheet_body).execute()
        )
        return result

    def _populate_executive_summary(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        tenant_name: str,
        audit_date: str,
        overall_score: float,
        period: str,
        rules: list[dict[str, Any]],
        insights: dict[str, Any] | None,
    ) -> None:
        """Populate the Executive Summary tab.

        Args:
            spreadsheet_id: ID of the spreadsheet
            sheet_id: ID of the Executive Summary sheet
            tenant_name: Tenant name
            audit_date: Audit date
            overall_score: Overall score
            period: Time period
            rules: List of rule results
            insights: Optional insights data
        """
        # Build data rows
        data = [
            ["Paid Social Audit - Executive Summary"],
            [],
            ["Tenant", tenant_name],
            ["Audit Date", audit_date],
            ["Period", period],
            ["Overall Score", overall_score],
            [],
            ["Key Metrics"],
            ["Total Rules Evaluated", len(rules)],
            [
                "Rules Passed (>= 75)",
                sum(1 for r in rules if r.get("score", 0) >= 75),
            ],
            [
                "Rules Failed (< 60)",
                sum(1 for r in rules if r.get("score", 0) < 60),
            ],
            ["Average Score", sum(r.get("score", 0) for r in rules) / len(rules) if rules else 0],
        ]

        # Add insights summary if available
        if insights:
            data.append([])
            data.append(["AI-Generated Insights"])
            if insights.get("strengths"):
                data.append(["Strengths", len(insights["strengths"])])
            if insights.get("issues"):
                data.append(["Issues Identified", len(insights["issues"])])
            if insights.get("recommendations"):
                data.append(["Recommendations", len(insights["recommendations"])])

        # Write data
        range_name = "Executive Summary!A1"
        body = {"values": data}
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

        # Apply formatting
        requests = [
            # Format title row
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 2,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": self.formatter.COLORS["header_bg"],
                            "textFormat": {
                                "foregroundColor": self.formatter.COLORS["header_text"],
                                "bold": True,
                                "fontSize": 14,
                            },
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
            # Format overall score cell with conditional color
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 5,
                        "endRowIndex": 6,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": self.formatter.get_score_color(
                                overall_score
                            ),
                            "textFormat": {"bold": True, "fontSize": 12},
                            "numberFormat": {"type": "NUMBER", "pattern": "0.00"},
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
            # Bold section headers
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 7,
                        "endRowIndex": 8,
                        "startColumnIndex": 0,
                        "endColumnIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 11}
                        }
                    },
                    "fields": "userEnteredFormat.textFormat",
                }
            },
            # Freeze top row
            self.formatter.create_freeze_rows_request(sheet_id, 1),
            # Auto-resize columns
            self.formatter.create_auto_resize_request(sheet_id, 0, 2),
        ]

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    def _populate_rule_details(
        self, spreadsheet_id: str, sheet_id: int, rules: list[dict[str, Any]]
    ) -> None:
        """Populate the Rule Details tab.

        Args:
            spreadsheet_id: ID of the spreadsheet
            sheet_id: ID of the Rule Details sheet
            rules: List of rule results
        """
        # Build header and data rows
        headers = ["Rule", "Window", "Level", "Score", "Findings Summary"]
        data = [headers]

        for rule in rules:
            rule_name = rule.get("rule", "Unknown")
            window = rule.get("window", "N/A")
            level = rule.get("level", "N/A")
            score = rule.get("score", 0)
            findings = rule.get("findings", {})

            # Create findings summary
            findings_summary = self._format_findings(findings)

            data.append([rule_name, window, level, score, findings_summary])

        # Write data
        range_name = "Rule Details!A1"
        body = {"values": data}
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

        # Apply formatting
        requests = [
            # Format header row
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(headers),
                    },
                    "cell": {
                        "userEnteredFormat": self.formatter.get_header_format()
                    },
                    "fields": "userEnteredFormat",
                }
            },
            # Freeze header row
            self.formatter.create_freeze_rows_request(sheet_id, 1),
            # Auto-resize all columns
            self.formatter.create_auto_resize_request(sheet_id, 0, len(headers)),
        ]

        # Add conditional formatting for scores
        if len(rules) > 0:
            # Excellent scores (>= 90)
            requests.append(
                self.formatter.create_conditional_format_rule(
                    sheet_id=sheet_id,
                    start_row=1,
                    end_row=len(rules) + 1,
                    column_index=3,  # Score column
                    threshold_type="NUMBER_GREATER_THAN_EQ",
                    threshold_value=90.0,
                    color=self.formatter.COLORS["score_excellent"],
                )
            )
            # Good scores (>= 75)
            requests.append(
                self.formatter.create_conditional_format_rule(
                    sheet_id=sheet_id,
                    start_row=1,
                    end_row=len(rules) + 1,
                    column_index=3,
                    threshold_type="NUMBER_GREATER_THAN_EQ",
                    threshold_value=75.0,
                    color=self.formatter.COLORS["score_good"],
                )
            )
            # Fair scores (>= 60)
            requests.append(
                self.formatter.create_conditional_format_rule(
                    sheet_id=sheet_id,
                    start_row=1,
                    end_row=len(rules) + 1,
                    column_index=3,
                    threshold_type="NUMBER_GREATER_THAN_EQ",
                    threshold_value=60.0,
                    color=self.formatter.COLORS["score_fair"],
                )
            )

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    def _populate_raw_data(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        rules: list[dict[str, Any]],
        insights: dict[str, Any] | None,
    ) -> None:
        """Populate the Raw Data tab with complete audit information.

        Args:
            spreadsheet_id: ID of the spreadsheet
            sheet_id: ID of the Raw Data sheet
            rules: List of rule results
            insights: Optional insights data
        """
        # Build comprehensive data dump
        headers = [
            "Rule",
            "Window",
            "Level",
            "Score",
            "Weight",
            "Findings (JSON)",
            "Description",
        ]
        data = [headers]

        for rule in rules:
            data.append(
                [
                    rule.get("rule", ""),
                    rule.get("window", ""),
                    rule.get("level", ""),
                    rule.get("score", 0),
                    rule.get("weight", 0),
                    str(rule.get("findings", {})),
                    rule.get("description", ""),
                ]
            )

        # Add insights section if available
        if insights:
            data.append([])
            data.append(["AI-Generated Insights"])
            data.append([])

            if insights.get("recommendations"):
                data.append(["Recommendations"])
                for rec in insights["recommendations"]:
                    data.append(
                        [
                            rec.get("title", ""),
                            "",
                            "",
                            "",
                            "",
                            rec.get("description", ""),
                            rec.get("expected_impact", ""),
                        ]
                    )
                data.append([])

            if insights.get("strengths"):
                data.append(["Strengths"])
                for strength in insights["strengths"]:
                    data.append(
                        [
                            strength.get("title", ""),
                            "",
                            "",
                            "",
                            "",
                            strength.get("description", ""),
                        ]
                    )
                data.append([])

            if insights.get("issues"):
                data.append(["Issues"])
                for issue in insights["issues"]:
                    data.append(
                        [
                            issue.get("title", ""),
                            "",
                            "",
                            issue.get("severity", ""),
                            "",
                            issue.get("description", ""),
                        ]
                    )

        # Write data
        range_name = "Raw Data!A1"
        body = {"values": data}
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

        # Apply formatting
        requests = [
            # Format header row
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(headers),
                    },
                    "cell": {
                        "userEnteredFormat": self.formatter.get_header_format()
                    },
                    "fields": "userEnteredFormat",
                }
            },
            # Freeze header row
            self.formatter.create_freeze_rows_request(sheet_id, 1),
            # Auto-resize columns
            self.formatter.create_auto_resize_request(sheet_id, 0, len(headers)),
        ]

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    def _format_findings(self, findings: dict[str, Any]) -> str:
        """Format findings dict into a readable string.

        Args:
            findings: Findings dictionary

        Returns:
            Formatted string summary
        """
        if not findings:
            return "No findings"

        parts = []
        for key, value in findings.items():
            if isinstance(value, int | float):
                parts.append(f"{key}: {value:.2f}")
            elif isinstance(value, list):
                parts.append(f"{key}: {len(value)} items")
            else:
                parts.append(f"{key}: {value}")

        return "; ".join(parts)
