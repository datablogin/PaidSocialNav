#!/bin/bash
# Setup script for Puttery GCP project

set -e

PROJECT_ID="puttery-golf-001"
BILLING_ACCOUNT="${TF_VAR_billing_account_id:-01223B-5E74E5-1C2A94}"
ORG_ID="${TF_VAR_org_id:-230523359416}"
DATASET="paid_social"
LOCATION="US"

echo "=================================================="
echo "Setting up GCP project for Puttery"
echo "=================================================="
echo ""
echo "Project ID: $PROJECT_ID"
echo "Billing Account: $BILLING_ACCOUNT"
echo "Organization: $ORG_ID"
echo ""

# Step 1: Create the project
echo "Step 1: Creating GCP project..."
gcloud projects create $PROJECT_ID \
  --organization=$ORG_ID \
  --name="Puttery Golf" \
  --set-as-default

echo "✓ Project created"
echo ""

# Step 2: Link billing account
echo "Step 2: Linking billing account..."
gcloud billing projects link $PROJECT_ID \
  --billing-account=$BILLING_ACCOUNT

echo "✓ Billing linked"
echo ""

# Step 3: Enable required APIs
echo "Step 3: Enabling required APIs..."
gcloud services enable bigquery.googleapis.com \
  --project=$PROJECT_ID

gcloud services enable bigquerystorage.googleapis.com \
  --project=$PROJECT_ID

echo "✓ APIs enabled"
echo ""

# Step 4: Create BigQuery dataset
echo "Step 4: Creating BigQuery dataset..."
bq --project_id=$PROJECT_ID mk \
  --dataset \
  --location=$LOCATION \
  --description="Paid social advertising data for Puttery/Drive Shack" \
  $DATASET

echo "✓ Dataset created: $PROJECT_ID.$DATASET"
echo ""

# Step 5: Create the insights table
echo "Step 5: Creating fct_ad_insights_daily table..."
python3 << 'PYTHON_EOF'
from paid_social_nav.storage.bq import ensure_dataset, ensure_insights_table, ensure_dim_ad_table

project_id = "puttery-golf-001"
dataset = "paid_social"

print(f"  Creating dataset and tables in {project_id}.{dataset}...")
ensure_dataset(project_id, dataset)
ensure_insights_table(project_id, dataset)
ensure_dim_ad_table(project_id, dataset)
print(f"  ✓ Tables created successfully")
PYTHON_EOF

echo ""
echo "=================================================="
echo "✓ GCP project setup complete!"
echo "=================================================="
echo ""
echo "Project: $PROJECT_ID"
echo "Dataset: $PROJECT_ID.$DATASET"
echo ""
echo "Next steps:"
echo "  1. Run the historical data sync:"
echo "     psn meta sync-insights \\"
echo "       --tenant puttery \\"
echo "       --account-id act_229793224304371 \\"
echo "       --since 2024-11-15 \\"
echo "       --until 2025-11-15"
echo ""
