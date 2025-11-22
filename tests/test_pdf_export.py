"""Tests for PDF export functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paid_social_nav.render.pdf import PDFExporter, write_pdf
from paid_social_nav.render.renderer import ReportRenderer
from paid_social_nav.storage.gcs import parse_gcs_uri, upload_file_to_gcs


class TestPDFExporter:
    """Test PDF export functionality."""

    def test_pdf_exporter_init(self) -> None:
        """Test PDFExporter initialization."""
        exporter = PDFExporter()
        assert exporter is not None

    @patch("paid_social_nav.render.pdf.weasyprint")
    def test_html_to_pdf_success(self, mock_weasyprint: MagicMock) -> None:
        """Test successful HTML to PDF conversion."""
        # Mock HTML class and write_pdf method
        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = b"PDF content"
        mock_weasyprint.HTML.return_value = mock_html_instance

        exporter = PDFExporter()
        html_content = "<html><body>Test</body></html>"
        pdf_bytes = exporter.html_to_pdf(html_content)

        assert pdf_bytes == b"PDF content"
        mock_weasyprint.HTML.assert_called_once_with(string=html_content, base_url=None)
        mock_html_instance.write_pdf.assert_called_once()

    def test_html_to_pdf_weasyprint_unavailable(self) -> None:
        """Test PDF conversion when WeasyPrint is not available."""
        with patch("paid_social_nav.render.pdf.PDFExporter._check_weasyprint", return_value=False):
            exporter = PDFExporter()
            assert not exporter.is_available()

            with pytest.raises(RuntimeError, match="WeasyPrint is not available"):
                exporter.html_to_pdf("<html><body>Test</body></html>")

    @patch("paid_social_nav.render.pdf.weasyprint")
    def test_html_to_pdf_with_base_url(self, mock_weasyprint: MagicMock) -> None:
        """Test HTML to PDF conversion with base URL."""
        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = b"PDF content"
        mock_weasyprint.HTML.return_value = mock_html_instance

        exporter = PDFExporter()
        html_content = "<html><body>Test</body></html>"
        base_url = "http://example.com"
        pdf_bytes = exporter.html_to_pdf(html_content, base_url=base_url)

        assert pdf_bytes == b"PDF content"
        mock_weasyprint.HTML.assert_called_once_with(string=html_content, base_url=base_url)

    def test_is_available(self) -> None:
        """Test is_available method."""
        with patch("paid_social_nav.render.pdf.PDFExporter._check_weasyprint", return_value=True):
            exporter = PDFExporter()
            assert exporter.is_available()

        with patch("paid_social_nav.render.pdf.PDFExporter._check_weasyprint", return_value=False):
            exporter = PDFExporter()
            assert not exporter.is_available()


class TestWritePDF:
    """Test write_pdf utility function."""

    def test_write_pdf_success(self, tmp_path: Path) -> None:
        """Test writing PDF to file."""
        pdf_content = b"PDF content"
        pdf_path = tmp_path / "test.pdf"

        write_pdf(str(pdf_path), pdf_content)

        assert pdf_path.exists()
        assert pdf_path.read_bytes() == pdf_content

    def test_write_pdf_creates_directories(self, tmp_path: Path) -> None:
        """Test that write_pdf creates parent directories."""
        pdf_content = b"PDF content"
        pdf_path = tmp_path / "subdir" / "test.pdf"

        write_pdf(str(pdf_path), pdf_content)

        assert pdf_path.exists()
        assert pdf_path.read_bytes() == pdf_content


class TestReportRendererPDF:
    """Test PDF rendering through ReportRenderer."""

    @pytest.fixture
    def sample_data(self) -> dict:
        """Sample audit data for testing."""
        return {
            "tenant_name": "TestClient",
            "period": "2025-01",
            "audit_date": "2025-01-22",
            "overall_score": 85,
            "rules": [
                {
                    "rule": "pacing_vs_target",
                    "window": "2025-W03",
                    "score": 90,
                    "findings": {"actual": 1000.0, "target": 1100.0},
                },
                {
                    "rule": "creative_diversity",
                    "window": "2025-W03",
                    "score": 80,
                    "findings": {"video_share": 0.6, "image_share": 0.4},
                },
            ],
            "recommendations": [],
            "strengths": [],
            "issues": [],
            "quick_wins": [],
            "roadmap": {},
        }

    @patch("paid_social_nav.render.renderer.PDFExporter")
    def test_render_pdf_success(self, mock_pdf_exporter_class: MagicMock, sample_data: dict) -> None:
        """Test successful PDF rendering."""
        # Mock PDFExporter instance
        mock_exporter = MagicMock()
        mock_exporter.is_available.return_value = True
        mock_exporter.html_to_pdf.return_value = b"PDF content"
        mock_pdf_exporter_class.return_value = mock_exporter

        renderer = ReportRenderer()
        pdf_bytes = renderer.render_pdf(sample_data, generate_charts=False)

        assert pdf_bytes == b"PDF content"
        mock_exporter.is_available.assert_called_once()
        mock_exporter.html_to_pdf.assert_called_once()

    @patch("paid_social_nav.render.renderer.PDFExporter")
    def test_render_pdf_weasyprint_unavailable(
        self, mock_pdf_exporter_class: MagicMock, sample_data: dict
    ) -> None:
        """Test PDF rendering when WeasyPrint is unavailable."""
        mock_exporter = MagicMock()
        mock_exporter.is_available.return_value = False
        mock_pdf_exporter_class.return_value = mock_exporter

        renderer = ReportRenderer()

        with pytest.raises(RuntimeError, match="PDF export is not available"):
            renderer.render_pdf(sample_data)


class TestGCSUpload:
    """Test GCS upload functionality."""

    def test_parse_gcs_uri_success(self) -> None:
        """Test parsing valid GCS URI."""
        bucket, blob = parse_gcs_uri("gs://my-bucket/path/to/file.pdf")
        assert bucket == "my-bucket"
        assert blob == "path/to/file.pdf"

    def test_parse_gcs_uri_no_gs_prefix(self) -> None:
        """Test parsing URI without gs:// prefix."""
        with pytest.raises(ValueError, match="Invalid GCS URI format"):
            parse_gcs_uri("http://my-bucket/file.pdf")

    def test_parse_gcs_uri_no_bucket(self) -> None:
        """Test parsing URI without bucket name."""
        with pytest.raises(ValueError, match="missing bucket name"):
            parse_gcs_uri("gs:///file.pdf")

    def test_parse_gcs_uri_no_blob(self) -> None:
        """Test parsing URI without blob path."""
        with pytest.raises(ValueError, match="missing blob path"):
            parse_gcs_uri("gs://my-bucket")

    @patch("paid_social_nav.storage.gcs.storage")
    def test_upload_file_to_gcs_with_bytes(self, mock_storage: MagicMock) -> None:
        """Test uploading bytes to GCS."""
        # Mock storage client and bucket
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.public_url = "https://storage.googleapis.com/bucket/file.pdf"

        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob

        # Call upload function
        content = b"PDF content"
        url = upload_file_to_gcs(
            gcs_uri="gs://my-bucket/file.pdf",
            content_bytes=content,
            make_public=True,
        )

        assert url == "https://storage.googleapis.com/bucket/file.pdf"
        mock_blob.upload_from_string.assert_called_once_with(
            content, content_type="application/pdf"
        )
        mock_blob.make_public.assert_called_once()

    @patch("paid_social_nav.storage.gcs.storage")
    def test_upload_file_to_gcs_with_local_path(
        self, mock_storage: MagicMock, tmp_path: Path
    ) -> None:
        """Test uploading local file to GCS."""
        # Create test file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content")

        # Mock storage client and bucket
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.public_url = "https://storage.googleapis.com/bucket/file.pdf"

        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob

        # Call upload function
        url = upload_file_to_gcs(
            gcs_uri="gs://my-bucket/file.pdf",
            local_path=str(test_file),
            make_public=True,
        )

        assert url == "https://storage.googleapis.com/bucket/file.pdf"
        mock_blob.upload_from_filename.assert_called_once_with(
            str(test_file), content_type="application/pdf"
        )
        mock_blob.make_public.assert_called_once()

    def test_upload_file_to_gcs_no_input(self) -> None:
        """Test upload with neither local_path nor content_bytes."""
        with pytest.raises(ValueError, match="Either local_path or content_bytes must be provided"):
            upload_file_to_gcs(gcs_uri="gs://my-bucket/file.pdf")

    @patch("paid_social_nav.storage.gcs.storage")
    def test_upload_file_to_gcs_bucket_not_exists(self, mock_storage: MagicMock) -> None:
        """Test upload when bucket doesn't exist."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = False

        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket

        with pytest.raises(RuntimeError, match="Bucket.*does not exist"):
            upload_file_to_gcs(
                gcs_uri="gs://my-bucket/file.pdf",
                content_bytes=b"content",
            )

    @patch("paid_social_nav.storage.gcs.storage")
    def test_upload_file_to_gcs_signed_url(self, mock_storage: MagicMock) -> None:
        """Test uploading with signed URL (make_public=False)."""
        # Mock storage client and bucket
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"

        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob

        # Call upload function
        url = upload_file_to_gcs(
            gcs_uri="gs://my-bucket/file.pdf",
            content_bytes=b"content",
            make_public=False,
        )

        assert url == "https://signed-url.example.com"
        mock_blob.make_public.assert_not_called()
        mock_blob.generate_signed_url.assert_called_once()
