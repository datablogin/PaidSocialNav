"""PDF export utilities for audit reports.

This module provides utilities for converting HTML audit reports to PDF format using WeasyPrint.
It handles the conversion process, error handling, and provides a clean interface for PDF generation.

PDF Generation Process:
1. Accept HTML content (from existing HTML template)
2. Apply print-specific CSS styling
3. Convert HTML to PDF using WeasyPrint
4. Return PDF bytes for file writing or upload

Usage:
    from paid_social_nav.render.pdf import PDFExporter

    exporter = PDFExporter()
    pdf_bytes = exporter.html_to_pdf(html_content)

    # Write to file
    with open('report.pdf', 'wb') as f:
        f.write(pdf_bytes)

Architecture Notes:
    - Uses WeasyPrint for HTML to PDF conversion
    - Pure Python implementation (no external binaries required)
    - Handles CSS for print media
    - Gracefully handles missing system dependencies

System Dependencies:
    WeasyPrint requires system libraries:
    - macOS: brew install cairo pango gdk-pixbuf libffi
    - Ubuntu: apt-get install libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0
    - Other systems: See WeasyPrint documentation
"""

from __future__ import annotations

from ..core.logging_config import get_logger

logger = get_logger(__name__)


class PDFExporter:
    """Export HTML reports to PDF format using WeasyPrint."""

    def __init__(self) -> None:
        """Initialize PDF exporter.

        Checks for WeasyPrint availability and logs warnings if dependencies are missing.
        """
        self._weasyprint_available = self._check_weasyprint()

    def _check_weasyprint(self) -> bool:
        """Check if WeasyPrint is available and properly configured.

        Returns:
            True if WeasyPrint can be imported and used, False otherwise
        """
        try:
            import weasyprint  # type: ignore  # noqa: F401

            return True
        except ImportError as e:
            logger.error(
                "WeasyPrint not installed. Install with: pip install weasyprint",
                extra={"error": str(e)},
            )
            return False
        except OSError as e:
            logger.error(
                "WeasyPrint system dependencies missing. "
                "On macOS: brew install cairo pango gdk-pixbuf libffi. "
                "On Ubuntu: apt-get install libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0",
                extra={"error": str(e)},
            )
            return False

    def html_to_pdf(self, html_content: str, base_url: str | None = None) -> bytes:
        """Convert HTML content to PDF.

        Args:
            html_content: HTML string to convert to PDF
            base_url: Optional base URL for resolving relative paths in HTML

        Returns:
            PDF content as bytes

        Raises:
            RuntimeError: If WeasyPrint is not available or conversion fails
        """
        if not self._weasyprint_available:
            raise RuntimeError(
                "WeasyPrint is not available. Please install system dependencies and "
                "reinstall weasyprint. See docs/pdf-export.md for instructions."
            )

        try:
            from weasyprint import HTML  # type: ignore

            logger.debug("Converting HTML to PDF", extra={"html_length": len(html_content)})

            # Convert HTML to PDF
            html = HTML(string=html_content, base_url=base_url)
            pdf_bytes: bytes = html.write_pdf()

            logger.info(
                "PDF generated successfully",
                extra={"pdf_size": len(pdf_bytes), "html_size": len(html_content)},
            )

            return pdf_bytes

        except Exception as e:
            logger.error(
                "Failed to convert HTML to PDF",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise RuntimeError(f"PDF conversion failed: {e}") from e

    def is_available(self) -> bool:
        """Check if PDF export is available.

        Returns:
            True if WeasyPrint is properly configured, False otherwise
        """
        return self._weasyprint_available


def write_pdf(path: str, pdf_bytes: bytes) -> None:
    """Write PDF bytes to file.

    Args:
        path: File path to write PDF to
        pdf_bytes: PDF content as bytes

    Raises:
        OSError: If file writing fails
    """
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    try:
        p.write_bytes(pdf_bytes)
        logger.info(f"PDF written to {path}", extra={"size": len(pdf_bytes)})
    except OSError as e:
        logger.error(f"Failed to write PDF to {path}", extra={"error": str(e)}, exc_info=True)
        raise
