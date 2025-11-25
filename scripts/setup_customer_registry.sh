#!/bin/bash
set -e

# Configuration
REGISTRY_PROJECT_ID="${REGISTRY_PROJECT_ID:-topgolf-460202}"
REGISTRY_DATASET="paidsocialnav_registry"

echo "🏗️  Setting up PaidSocialNav Customer Registry"
echo "=============================================="
echo "Registry Project: $REGISTRY_PROJECT_ID"
echo "Registry Dataset: $REGISTRY_DATASET"
echo ""

# Create dataset
echo "📦 Creating BigQuery dataset..."
bq mk \
  --dataset \
  --location=US \
  --description="PaidSocialNav customer registry and usage tracking" \
  "${REGISTRY_PROJECT_ID}:${REGISTRY_DATASET}" \
  2>/dev/null || echo "✓ Dataset already exists"

# Create tables from schema
echo ""
echo "📋 Creating registry tables..."

# Replace project_id placeholder in schema
sed "s/{project_id}/${REGISTRY_PROJECT_ID}/g" sql/customer_registry_schema.sql > /tmp/registry_schema_tmp.sql

# Split SQL file by semicolons and execute each CREATE statement
awk 'BEGIN{RS=";"} /CREATE/{print $0";"}' /tmp/registry_schema_tmp.sql | while read -r statement; do
  if [ -n "$statement" ]; then
    echo "$statement" | bq query \
      --use_legacy_sql=false \
      --project_id="${REGISTRY_PROJECT_ID}" \
      2>/dev/null || echo "✓ Table/view already exists"
  fi
done

rm /tmp/registry_schema_tmp.sql

echo ""
echo "✅ Registry setup complete!"
echo ""
echo "Next steps:"
echo "1. Migrate existing tenants to registry:"
echo "   python scripts/migrate_tenants_to_registry.py"
echo ""
echo "2. Onboard a new customer:"
echo "   python scripts/onboard_customer.py <customer_id> <customer_name> <gcp_project_id> --meta-accounts=<account_ids>"
echo ""
echo "3. List all customers:"
echo "   python scripts/list_customers.py"
