"""Google Cloud Storage utilities for uploading files.

This module provides utilities for uploading files (particularly PDF reports) to Google Cloud Storage.
It handles authentication, upload operations, and URL generation for uploaded files.

Upload Process:
1. Parse GCS URI (gs://bucket/prefix/filename)
2. Authenticate using application default credentials
3. Upload file to specified bucket and path
4. Return public or signed URL for access

Usage:
    from paid_social_nav.storage.gcs import upload_file_to_gcs

    # Upload a file
    public_url = upload_file_to_gcs(
        local_path="./reports/audit.pdf",
        gcs_uri="gs://my-bucket/audits/2025/audit.pdf"
    )

    # Or upload from bytes
    public_url = upload_file_to_gcs(
        local_path=None,
        gcs_uri="gs://my-bucket/audits/2025/audit.pdf",
        content_bytes=pdf_bytes
    )

Architecture Notes:
    - Uses Application Default Credentials (ADC) for authentication
    - Supports both file path and bytes upload
    - Generates signed URLs for private buckets
    - Handles bucket creation if needed (optional)

Security Notes:
    - Requires appropriate GCS permissions (storage.objects.create)
    - Uses ADC (service account or user credentials)
    - Signed URLs expire after configurable duration (default: 7 days)
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from ..core.logging_config import get_logger

logger = get_logger(__name__)


def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    """Parse GCS URI into bucket and blob path.

    Args:
        gcs_uri: GCS URI in format gs://bucket/path/to/file

    Returns:
        Tuple of (bucket_name, blob_path)

    Raises:
        ValueError: If URI format is invalid
    """
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI format: {gcs_uri}. Must start with 'gs://'")

    parsed = urlparse(gcs_uri)
    bucket_name = parsed.netloc
    blob_path = parsed.path.lstrip("/")

    if not bucket_name:
        raise ValueError(f"Invalid GCS URI: missing bucket name in {gcs_uri}")

    if not blob_path:
        raise ValueError(f"Invalid GCS URI: missing blob path in {gcs_uri}")

    return bucket_name, blob_path


def upload_file_to_gcs(
    gcs_uri: str,
    local_path: str | None = None,
    content_bytes: bytes | None = None,
    content_type: str = "application/pdf",
    make_public: bool = False,
    signed_url_expiration_days: int = 7,
) -> str:
    """Upload a file to Google Cloud Storage.

    Args:
        gcs_uri: Destination GCS URI (gs://bucket/path/to/file)
        local_path: Optional local file path to upload
        content_bytes: Optional bytes to upload (used if local_path is None)
        content_type: MIME type of the file (default: application/pdf)
        make_public: Whether to make the uploaded file publicly accessible (default: False)
        signed_url_expiration_days: Number of days the signed URL is valid (default: 7)

    Returns:
        Public URL or signed URL to the uploaded file

    Raises:
        ValueError: If neither local_path nor content_bytes is provided
        RuntimeError: If upload fails or authentication fails
    """
    if local_path is None and content_bytes is None:
        raise ValueError("Either local_path or content_bytes must be provided")

    try:
        from google.api_core import exceptions as gcp_exceptions
        from google.cloud import storage  # type: ignore[import-untyped]

        # Parse GCS URI
        bucket_name, blob_path = parse_gcs_uri(gcs_uri)

        logger.debug(
            f"Uploading to GCS: {bucket_name}/{blob_path}",
            extra={"bucket": bucket_name, "blob_path": blob_path},
        )

        # Initialize storage client
        try:
            client = storage.Client()
        except Exception as e:
            logger.error(
                "Failed to initialize GCS client. Ensure Application Default Credentials are configured.",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise RuntimeError(
                f"GCS authentication failed: {e}. "
                "Run 'gcloud auth application-default login' to configure credentials."
            ) from e

        # Get bucket
        try:
            bucket = client.bucket(bucket_name)
            if not bucket.exists():
                logger.warning(
                    f"Bucket {bucket_name} does not exist",
                    extra={"bucket": bucket_name},
                )
                raise RuntimeError(
                    f"Bucket '{bucket_name}' does not exist. Create it first or check permissions."
                )
        except gcp_exceptions.NotFound:
            raise RuntimeError(
                f"Bucket '{bucket_name}' not found. "
                "Verify the bucket name or create it first."
            ) from None
        except gcp_exceptions.Forbidden:
            raise RuntimeError(
                f"Access denied to bucket '{bucket_name}'. "
                "Check your GCP permissions (storage.buckets.get required)."
            ) from None
        except RuntimeError:
            # Re-raise our own RuntimeErrors
            raise
        except Exception as e:
            logger.error(
                f"Failed to access bucket {bucket_name}",
                extra={"bucket": bucket_name, "error": str(e)},
                exc_info=True,
            )
            raise RuntimeError(f"Failed to access GCS bucket: {e}") from e

        # Create blob
        blob = bucket.blob(blob_path)

        # Upload file
        try:
            if local_path:
                blob.upload_from_filename(local_path, content_type=content_type)
                file_size = Path(local_path).stat().st_size
            else:
                blob.upload_from_string(content_bytes, content_type=content_type)
                file_size = len(content_bytes) if content_bytes else 0

            logger.info(
                f"Successfully uploaded to gs://{bucket_name}/{blob_path}",
                extra={"bucket": bucket_name, "blob_path": blob_path, "size": file_size},
            )

        except Exception as e:
            logger.error(
                f"Failed to upload to gs://{bucket_name}/{blob_path}",
                extra={"bucket": bucket_name, "blob_path": blob_path, "error": str(e)},
                exc_info=True,
            )
            raise RuntimeError(f"GCS upload failed: {e}") from e

        # Generate URL
        if make_public:
            blob.make_public()
            url: str = blob.public_url
            logger.debug(f"File made public: {url}")
        else:
            # Generate signed URL with configurable expiration
            from datetime import timedelta

            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(days=signed_url_expiration_days),
                method="GET",
            )
            logger.debug(f"Generated signed URL (expires in {signed_url_expiration_days} days)")

        return url

    except (ValueError, RuntimeError):
        # Re-raise our own exceptions
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during GCS upload: {e}",
            extra={"error_type": type(e).__name__, "error": str(e)},
            exc_info=True,
        )
        raise RuntimeError(f"GCS upload failed: {e}") from e


def upload_pdf_to_gcs(
    pdf_path: str, gcs_uri: str, make_public: bool = False
) -> str:
    """Upload a PDF file to Google Cloud Storage.

    Convenience function specifically for PDF uploads.

    Args:
        pdf_path: Local path to PDF file
        gcs_uri: Destination GCS URI (gs://bucket/path/to/file.pdf)
        make_public: Whether to make the uploaded file publicly accessible (default: False)

    Returns:
        URL to the uploaded PDF

    Raises:
        RuntimeError: If upload fails
    """
    return upload_file_to_gcs(
        gcs_uri=gcs_uri,
        local_path=pdf_path,
        content_type="application/pdf",
        make_public=make_public,
    )
