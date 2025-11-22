# Google Sheets Integration Setup

This guide explains how to set up Google Sheets integration for PaidSocialNav audit reports.

## Overview

The Google Sheets integration allows you to export audit data to Google Sheets for:
- Interactive data exploration and drill-down analysis
- Sharing audit results with stakeholders
- Creating custom pivot tables and charts
- Exporting data to other tools

## Prerequisites

- A Google Cloud Platform (GCP) project
- Access to create service accounts in GCP
- The Google Sheets API enabled in your GCP project

## Setup Instructions

### Step 1: Create a GCP Project (if you don't have one)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter a project name (e.g., "paidsocialnav-sheets")
4. Click "Create"

### Step 2: Enable the Google Sheets API

1. In the Google Cloud Console, navigate to "APIs & Services" → "Library"
2. Search for "Google Sheets API"
3. Click on "Google Sheets API"
4. Click "Enable"

### Step 3: Create a Service Account

1. Navigate to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Fill in the service account details:
   - **Name**: `paidsocialnav-sheets` (or your preferred name)
   - **Description**: "Service account for PaidSocialNav Google Sheets export"
4. Click "Create and Continue"
5. Skip the optional "Grant this service account access to project" step
6. Click "Done"

### Step 4: Create and Download Service Account Key

1. On the "Credentials" page, find your newly created service account
2. Click on the service account email to open its details
3. Go to the "Keys" tab
4. Click "Add Key" → "Create new key"
5. Select "JSON" as the key type
6. Click "Create"
7. The JSON key file will be downloaded to your computer
8. **Important**: Store this file securely - it contains credentials that grant access to Google APIs

### Step 5: Configure PaidSocialNav

1. Move the downloaded JSON key file to a secure location on your server/machine
   ```bash
   # Example: move to a credentials directory
   mkdir -p ~/.config/paidsocialnav
   mv ~/Downloads/paidsocialnav-sheets-*.json ~/.config/paidsocialnav/service-account-key.json
   chmod 600 ~/.config/paidsocialnav/service-account-key.json
   ```

2. Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable:

   **Option A: In your .env file (recommended for local development)**
   ```bash
   # Add to .env file in project root
   GOOGLE_APPLICATION_CREDENTIALS=/home/user/.config/paidsocialnav/service-account-key.json
   ```

   **Option B: Export in your shell (temporary)**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/home/user/.config/paidsocialnav/service-account-key.json"
   ```

   **Option C: System-wide (for production servers)**
   ```bash
   # Add to /etc/environment or ~/.bashrc
   export GOOGLE_APPLICATION_CREDENTIALS="/home/user/.config/paidsocialnav/service-account-key.json"
   ```

### Step 6: Install Dependencies

Ensure you have the required Google Sheets dependencies installed:

```bash
pip install -e .
```

This will install `google-auth` and `google-api-python-client` as specified in `pyproject.toml`.

## Usage

### Basic Usage

Run an audit with Google Sheets export enabled:

```bash
psn skills audit \
  --tenant-id puttery \
  --audit-config configs/audit_puttery.yaml \
  --sheets-output
```

### Complete Example with All Options

```bash
psn skills audit \
  --tenant-id puttery \
  --audit-config configs/audit_puttery.yaml \
  --output-dir reports/ \
  --assets-dir reports/assets \
  --sheets-output
```

### Output

When Google Sheets export is successful, you'll see output like:

```
✅ Audit complete: 85.5/100

Reports generated:
  Markdown: /path/to/reports/puttery_audit_20250122.md
  HTML: /path/to/reports/puttery_audit_20250122.html

📊 Google Sheets:
  https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
```

The HTML report will also include a "View Data in Google Sheets" button in the header.

## Google Sheet Structure

The exported Google Sheet contains three tabs:

### 1. Executive Summary
- Overall audit score
- Audit date and period
- Key metrics summary
- Number of rules passed/failed
- AI-generated insights summary (if available)

### 2. Rule Details
- Complete rule-by-rule breakdown
- Columns: Rule | Window | Level | Score | Findings Summary
- Conditional formatting for scores:
  - Green (90+): Excellent
  - Yellow-green (75-89): Good
  - Yellow (60-74): Fair
  - Red (<60): Poor

### 3. Raw Data
- Complete audit data dump
- Rule findings in JSON format
- AI-generated insights (recommendations, strengths, issues)
- Useful for custom analysis and data export

## Sharing and Permissions

By default, the service account is the owner of created sheets. To share with others:

1. Open the Google Sheet URL
2. Click "Share" in the top-right corner
3. Add email addresses of users who should have access
4. Set their permission level (Viewer, Commenter, or Editor)
5. Click "Send"

**Tip**: You can also set sharing permissions programmatically by granting the service account domain-wide delegation, but this requires additional GCP configuration.

## Troubleshooting

### Error: "Google Sheets credentials not configured"

**Problem**: The `GOOGLE_APPLICATION_CREDENTIALS` environment variable is not set.

**Solution**: Follow Step 5 above to set the environment variable.

### Error: "Credentials file not found"

**Problem**: The path in `GOOGLE_APPLICATION_CREDENTIALS` points to a non-existent file.

**Solution**:
- Verify the file path is correct
- Check file permissions (should be readable)
- Use absolute paths, not relative paths

### Error: "Failed to initialize Google Sheets API"

**Problem**: The credentials file is invalid or corrupted.

**Solution**:
- Re-download the service account key from GCP Console
- Ensure the file is valid JSON
- Create a new service account key if needed

### Warning: "Google Sheets export skipped: credentials not configured"

**Note**: This is a warning, not an error. The audit will complete successfully without Google Sheets export.

**Solution**: If you want Google Sheets export, configure credentials as described above.

### Sheets export fails silently

**Problem**: Google Sheets API might not be enabled.

**Solution**:
- Go to GCP Console → "APIs & Services" → "Library"
- Search for "Google Sheets API"
- Ensure it shows "Manage" (meaning it's enabled)
- If it shows "Enable", click it to enable the API

## Security Best Practices

1. **Never commit service account keys to version control**
   - Add `*.json` to `.gitignore` for credential files
   - Use environment variables or secret management services

2. **Restrict service account permissions**
   - Only grant the service account access to Google Sheets API
   - Don't grant unnecessary IAM roles

3. **Rotate keys regularly**
   - Create new service account keys periodically
   - Delete old keys from GCP Console

4. **Use different service accounts per environment**
   - Separate service accounts for dev, staging, and production
   - Easier to track usage and revoke access if needed

5. **Monitor API usage**
   - Check GCP Console → "APIs & Services" → "Dashboard"
   - Set up billing alerts for unexpected usage

## API Quotas and Limits

Google Sheets API has the following default quotas (as of 2025):

- **Read requests**: 300 per minute per project
- **Write requests**: 300 per minute per project
- **Per user rate limit**: 60 requests per minute per user

For typical PaidSocialNav usage (1-2 audits per day), these limits are more than sufficient.

If you need higher quotas:
1. Go to GCP Console → "APIs & Services" → "Quotas"
2. Search for "Google Sheets API"
3. Request a quota increase

## Additional Resources

- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [Google Cloud Service Accounts](https://cloud.google.com/iam/docs/service-accounts)
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)

## Support

If you encounter issues not covered in this guide:

1. Check the application logs for detailed error messages
2. Verify all setup steps were completed correctly
3. Consult the Google Sheets API documentation
4. File an issue on the PaidSocialNav GitHub repository
