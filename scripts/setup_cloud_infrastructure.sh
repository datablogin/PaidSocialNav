#!/bin/bash
set -e

PROJECT_ID="${GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"

echo "🔧 Setting up Cloud infrastructure for PaidSocialNav MCP"

# Enable required APIs
echo "Enabling required Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  bigquery.googleapis.com \
  storage-api.googleapis.com \
  --project="${PROJECT_ID}"

# Create service account
echo "Creating service account..."
gcloud iam service-accounts create paidsocialnav-sa \
  --display-name="PaidSocialNav MCP Server" \
  --project="${PROJECT_ID}" || true

SA_EMAIL="paidsocialnav-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant necessary permissions
echo "Granting IAM permissions..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Create secrets (if they don't exist)
echo "Creating secrets..."
echo -n "placeholder" | gcloud secrets create META_ACCESS_TOKEN \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || true

echo -n "placeholder" | gcloud secrets create ANTHROPIC_API_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || true

echo -n "placeholder" | gcloud secrets create MCP_GOOGLE_CLIENT_SECRET \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || true

echo "✅ Infrastructure setup complete!"
echo ""
echo "⚠️  IMPORTANT: Update the following secrets with actual values:"
echo "  gcloud secrets versions add META_ACCESS_TOKEN --data-file=- --project=${PROJECT_ID}"
echo "  gcloud secrets versions add ANTHROPIC_API_KEY --data-file=- --project=${PROJECT_ID}"
echo "  gcloud secrets versions add MCP_GOOGLE_CLIENT_SECRET --data-file=- --project=${PROJECT_ID}"
