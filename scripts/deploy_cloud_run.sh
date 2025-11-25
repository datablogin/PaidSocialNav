#!/bin/bash
set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="paidsocialnav-mcp"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying PaidSocialNav MCP Server to Cloud Run"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"

# Build container image
echo "📦 Building container image..."
gcloud builds submit \
  --tag="${IMAGE_NAME}" \
  --project="${PROJECT_ID}"

# Deploy to Cloud Run
echo "🌐 Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_NAME}" \
  --platform=managed \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account=paidsocialnav-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --set-env-vars="MCP_TRANSPORT=http" \
  --set-env-vars="MCP_AUTH_TYPE=google" \
  --set-secrets="META_ACCESS_TOKEN=META_ACCESS_TOKEN:latest" \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" \
  --set-secrets="GOOGLE_CLIENT_SECRET=MCP_GOOGLE_CLIENT_SECRET:latest" \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300 \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=10 \
  --project="${PROJECT_ID}"

# Get service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --platform=managed \
  --region="${REGION}" \
  --format='value(status.url)' \
  --project="${PROJECT_ID}")

echo "✅ Deployment complete!"
echo "Service URL: ${SERVICE_URL}"
echo "MCP Endpoint: ${SERVICE_URL}/mcp"
echo ""
echo "To test the deployment:"
echo "  gcloud run services proxy ${SERVICE_NAME} --region=${REGION}"
echo "  Then connect to http://localhost:8080/mcp"
