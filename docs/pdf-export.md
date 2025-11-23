# PDF Export Feature

This document describes how to set up and use the PDF export feature for audit reports.

## Overview

The PDF export feature allows you to generate professional PDF reports from your audit data using WeasyPrint, a Python library that converts HTML to PDF. This feature is integrated into both the `audit run` and `skills audit` commands.

## System Requirements

WeasyPrint requires system dependencies to render PDFs. You must install these before using PDF export.

### macOS

```bash
brew install cairo pango gdk-pixbuf libffi
```

### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
```

### Other Linux Distributions

#### Fedora/RHEL/CentOS

```bash
sudo dnf install cairo pango gdk-pixbuf2 libffi-devel
```

#### Arch Linux

```bash
sudo pacman -S cairo pango gdk-pixbuf2 libffi
```

### Windows

WeasyPrint on Windows requires GTK+. Follow the official WeasyPrint documentation:
https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows

## Python Dependencies

Install the Python dependencies (already included in pyproject.toml):

```bash
pip install -e .
```

This will install:
- `weasyprint>=60.0` - HTML to PDF conversion
- `google-cloud-storage>=2.0.0` - GCS upload support (optional)

## Usage

### Basic PDF Export

Generate a PDF report using the `audit run` command:

```bash
# Generate PDF only
psn audit run --config configs/audit_puttery.yaml --format pdf

# Generate both Markdown and PDF
psn audit run --config configs/audit_puttery.yaml --format md,pdf

# Specify custom output path
psn audit run --config configs/audit_puttery.yaml --pdf-output reports/custom_audit.pdf
```

### Using Skills Workflow

The skills workflow provides the most comprehensive audit experience:

```bash
# Generate all formats (Markdown, HTML, PDF)
psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml --format md,html,pdf

# Generate PDF only
psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml --format pdf
```

## Upload to Google Cloud Storage

You can automatically upload generated PDFs to Google Cloud Storage.

### Prerequisites

1. Install Google Cloud SDK:
   ```bash
   # macOS
   brew install google-cloud-sdk

   # Ubuntu/Debian
   curl https://sdk.cloud.google.com | bash
   ```

2. Authenticate:
   ```bash
   gcloud auth application-default login
   ```

3. Ensure you have permissions:
   - `storage.objects.create` on the target bucket
   - `storage.buckets.get` on the target bucket

### Upload Examples

```bash
# Generate PDF and upload to GCS
psn audit run \
  --config configs/audit_puttery.yaml \
  --format pdf \
  --upload gs://my-bucket/audits/puttery_audit_20250122.pdf

# Using skills workflow with upload
psn skills audit \
  --tenant-id puttery \
  --audit-config configs/audit_puttery.yaml \
  --format pdf \
  --upload gs://my-bucket/audits/puttery_audit_20250122.pdf
```

The upload will return a signed URL that's valid for 7 days. You can use this URL to share the report securely.

## PDF Features

The generated PDF includes:

- **Executive Summary**: Overall audit score and high-level insights
- **Visual Charts**: All matplotlib charts (score distribution, pacing, creative mix, performance trends)
- **Rule-by-Rule Analysis**: Detailed findings for each audit rule
- **Strategic Insights**: AI-generated strengths and issues (if Claude API key is configured)
- **Recommendations**: Prioritized action items
- **Quick Wins**: Immediate opportunities
- **90-Day Roadmap**: Phased implementation plan
- **Evidence Appendix**: Detailed data tables supporting all findings

### Chart Rendering

Charts are rendered as static PNG images embedded in the PDF using matplotlib. This ensures:
- Charts display correctly in all PDF viewers
- No dependency on external JavaScript libraries
- Consistent appearance across platforms
- Professional print quality

### Page Formatting

- **Page Size**: A4 (210mm × 297mm)
- **Margins**: 2cm on all sides
- **Page Breaks**: Automatically avoid breaking:
  - Charts and tables
  - Section headers
  - Rule cards
- **Styling**: Professional gradient headers, color-coded scores, clean typography

## Performance

PDF generation typically takes 5-15 seconds depending on:
- Number of audit rules
- Number of charts generated
- System performance

The process includes:
1. Generating HTML from template (~1-2s)
2. Rendering charts as images (~2-5s)
3. Converting HTML to PDF with WeasyPrint (~2-8s)

## Troubleshooting

### WeasyPrint Import Error

**Error**: `ModuleNotFoundError: No module named 'weasyprint'`

**Solution**:
```bash
pip install -e .
```

### System Dependencies Missing

**Error**: `OSError: cannot load library 'gobject-2.0-0'` or similar

**Solution**: Install system dependencies (see System Requirements above)

### PDF Generation Timeout

If PDF generation is taking too long, check:
- Reduce the number of audit rules in your config
- Ensure matplotlib is using the 'Agg' backend (should be automatic)
- Check system resources (CPU, memory)

### GCS Upload Fails

**Error**: `RuntimeError: GCS authentication failed`

**Solution**:
```bash
gcloud auth application-default login
```

**Error**: `RuntimeError: Bucket 'my-bucket' does not exist`

**Solution**: Create the bucket first:
```bash
gsutil mb gs://my-bucket
```

Or use an existing bucket you have access to.

### Charts Not Appearing in PDF

Charts are embedded as base64-encoded PNG images. If they're missing:
1. Check that matplotlib is installed: `pip list | grep matplotlib`
2. Verify chart generation is enabled (it's on by default)
3. Check logs for chart generation errors

## CLI Reference

### `psn audit run` Options

- `--format`: Output format(s). Options: `md`, `html`, `pdf` (comma-separated)
- `--pdf-output`: Custom path for PDF output (overrides default naming)
- `--upload`: GCS URI for uploading PDF (e.g., `gs://bucket/path/file.pdf`)
- `--assets-dir`: Directory to save chart images (optional, for debugging)

### `psn skills audit` Options

- `--format`: Output format(s). Default: `md,html`. Options: `md`, `html`, `pdf`
- `--upload`: GCS URI for uploading PDF
- `--output-dir`: Directory for all report outputs (default: `reports/`)
- `--assets-dir`: Directory to save chart images

## Examples

### Basic Usage

```bash
# Single PDF
psn audit run --config configs/audit_puttery.yaml --format pdf

# All formats
psn audit run --config configs/audit_puttery.yaml --format md,html,pdf

# Custom output paths
psn audit run \
  --config configs/audit_puttery.yaml \
  --output reports/audit.md \
  --html-output reports/audit.html \
  --pdf-output reports/audit.pdf
```

### Production Workflow

```bash
# Full audit with all outputs and GCS upload
psn skills audit \
  --tenant-id puttery \
  --audit-config configs/audit_puttery.yaml \
  --format md,html,pdf \
  --upload gs://puttery-audits/$(date +%Y%m%d)/audit.pdf \
  --assets-dir reports/assets \
  --sheets-output
```

### Automated Reports

```bash
#!/bin/bash
# automated-audit.sh - Run daily audits with PDF upload

TENANT="puttery"
DATE=$(date +%Y%m%d)
BUCKET="gs://my-audits"

psn skills audit \
  --tenant-id "$TENANT" \
  --audit-config "configs/audit_${TENANT}.yaml" \
  --format pdf \
  --upload "$BUCKET/$TENANT/$DATE/audit.pdf" \
  --output-dir "reports/$DATE"

echo "Audit complete! PDF uploaded to $BUCKET/$TENANT/$DATE/audit.pdf"
```

## Architecture Notes

### Implementation Details

- **Rendering**: WeasyPrint converts HTML to PDF using Cairo graphics library
- **Templates**: Reuses existing `audit_report.html.j2` with print-specific CSS
- **Charts**: matplotlib generates static PNG images (Chart.js not used in PDF)
- **Storage**: Optional GCS upload using `google-cloud-storage` client library

### Code Organization

```
paid_social_nav/
├── render/
│   ├── pdf.py              # PDF export logic
│   ├── renderer.py         # render_pdf() method
│   └── templates/
│       └── audit_report.html.j2  # HTML template with print CSS
├── storage/
│   └── gcs.py              # GCS upload utilities
├── skills/
│   └── audit_workflow.py   # Skills orchestration with PDF support
└── cli/
    └── main.py             # CLI commands with --format and --upload flags
```

## Security Considerations

- **GCS URLs**: Signed URLs expire after 7 days by default
- **Permissions**: Upload requires `storage.objects.create` permission
- **Authentication**: Uses Application Default Credentials (ADC)
- **Data Privacy**: PDFs contain sensitive audit data - ensure proper bucket permissions

## Future Enhancements

Potential future improvements:
- Custom PDF templates
- Configurable page size and margins
- Watermarking support
- Password protection for PDFs
- Email delivery integration
- Scheduled report generation
- Multi-tenant batch processing

## Support

For issues or questions:
1. Check this documentation
2. Review the error messages and troubleshooting section
3. Ensure all system dependencies are installed
4. Check WeasyPrint documentation: https://doc.courtbouillon.org/weasyprint/
5. File an issue in the project repository
