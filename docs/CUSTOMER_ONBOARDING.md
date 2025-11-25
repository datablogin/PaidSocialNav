# Customer Onboarding Guide

This guide explains how to onboard new customers to PaidSocialNav using the multi-tenant customer registry.

## Architecture Overview

PaidSocialNav uses a **centralized BigQuery customer registry** that allows you to onboard and manage multiple clients without code changes. The system supports:

- **Dynamic customer onboarding** via command-line scripts
- **Central registry** in BigQuery (project: `topgolf-460202`, dataset: `paidsocialnav_registry`)
- **Per-customer GCP projects** for data isolation
- **Backward compatibility** with existing `tenants.yaml` configuration

### Registry Structure

```
topgolf-460202 (Central Registry Project)
└── paidsocialnav_registry dataset
    ├── customers (Main registry table)
    ├── active_customers (View of active customers only)
    ├── customer_usage (Usage tracking)
    └── audit_history (Audit execution logs)

customer-project-1 (Customer's Project)
└── paid_social dataset
    ├── fct_ad_insights_daily
    └── benchmarks_performance

customer-project-2 (Customer's Project)
└── paid_social dataset
    ├── fct_ad_insights_daily
    └── benchmarks_performance
```

## Prerequisites

1. **GCP Authentication**: Authenticated to the registry project (`topgolf-460202`)
2. **BigQuery Access**: Permissions to create datasets and tables
3. **Secret Manager Access**: Permissions to store API credentials
4. **Customer GCP Project**: Customer's own GCP project for data storage

## Initial Setup (One-Time)

### 1. Initialize the Customer Registry

```bash
# Create registry dataset and tables
python scripts/setup_registry_python.py --project=topgolf-460202
```

This creates:
- `paidsocialnav_registry` dataset
- `customers` table with partitioning and clustering
- `active_customers` view
- `customer_usage` tracking table
- `audit_history` audit log table

### 2. Migrate Existing Tenants (Optional)

If you have existing tenants in `configs/tenants.yaml`:

```bash
python scripts/migrate_tenants_to_registry.py --registry-project=topgolf-460202
```

## Onboarding a New Customer

### Method 1: Command-Line Script (Recommended)

```bash
python scripts/onboard_customer.py \
  <customer_id> \
  "<customer_name>" \
  <gcp_project_id> \
  --meta-accounts="act_123456789,act_987654321" \
  --meta-token="YOUR_META_ACCESS_TOKEN" \
  --registry-project="topgolf-460202" \
  --email="contact@customer.com" \
  --tags="industry,region" \
  --created-by="your.name@company.com"
```

**Example:**
```bash
python scripts/onboard_customer.py \
  newclient \
  "New Client Inc." \
  newclient-gcp-project \
  --meta-accounts="act_123456789" \
  --meta-token="EAABsb..." \
  --email="john@newclient.com" \
  --tags="retail,usa" \
  --created-by="robert@company.com"
```

This script will:
1. Create customer record in BigQuery registry
2. Store Meta API credentials in Secret Manager
3. Create BigQuery dataset and tables in customer's GCP project
4. Set up necessary infrastructure

### Method 2: Python API

```python
from paid_social_nav.core.customer_registry import CustomerRegistry

registry = CustomerRegistry(registry_project_id="topgolf-460202")

customer = registry.add_customer(
    customer_id="newclient",
    customer_name="New Client Inc.",
    gcp_project_id="newclient-gcp-project",
    bq_dataset="paid_social",
    meta_ad_account_ids=["act_123456789"],
    default_level="campaign",
    primary_contact_email="contact@newclient.com",
    tags=["retail", "usa"],
    created_by="robert@company.com"
)

print(f"✓ Customer '{customer.customer_id}' onboarded!")
```

## Managing Customers

### List All Customers

```bash
# List active customers
python scripts/list_customers.py

# List all customers (including paused/churned)
python scripts/list_customers.py --status=all

# Export to JSON
python scripts/list_customers.py --format=json

# Export to CSV
python scripts/list_customers.py --format=csv > customers.csv
```

### View Customer Details

```python
from paid_social_nav.core.customer_registry import get_customer

customer = get_customer("newclient")
print(f"Customer: {customer.customer_name}")
print(f"GCP Project: {customer.gcp_project_id}")
print(f"Meta Accounts: {customer.meta_ad_account_ids}")
```

### Update Customer

```python
from paid_social_nav.core.customer_registry import CustomerRegistry

registry = CustomerRegistry()
registry.update_customer(
    "newclient",
    status="paused",  # or "active", "churned"
    tags=["retail", "usa", "premium"],
    usage_tier="enterprise"
)
```

## Using Customers with Existing Tools

### CLI Commands

The existing CLI automatically works with the customer registry:

```bash
# Sync data for a customer
python -m paid_social_nav.cli.main sync-meta \
  act_123456789 \
  --tenant=newclient

# Run audit for a customer
python -m paid_social_nav.cli.main audit \
  --tenant=newclient \
  --config=configs/audit_config.yaml
```

### Backward Compatibility

Customers can still be defined in `configs/tenants.yaml`. The system automatically falls back to YAML if a customer is not found in BigQuery:

```yaml
tenants:
  legacyclient:
    project_id: legacy-project-123
    dataset: paid_social
    default_level: campaign
```

## Customer Data Isolation

Each customer's data is stored in their own GCP project:

- **Registry** (topgolf-460202): Customer metadata only
- **Customer Project** (customer's project): All advertising data

This ensures:
- Data isolation and security
- Customer ownership of their data
- Compliance with data residency requirements
- Easy offboarding (just revoke access to customer's project)

## Credentials Management

Customer API credentials are stored securely in Secret Manager:

```
projects/topgolf-460202/secrets/NEWCLIENT_META_ACCESS_TOKEN
```

Access controlled via IAM:
- MCP server service account has `secretAccessor` role
- Customer-specific secrets are isolated
- Automatic secret rotation supported

## Onboarding Checklist

- [ ] Customer has their own GCP project created
- [ ] Customer has provided Meta ad account IDs
- [ ] Customer has provided Meta API access token
- [ ] Run onboarding script
- [ ] Verify customer in registry: `python scripts/list_customers.py`
- [ ] Run initial data sync
- [ ] Run first audit to validate setup
- [ ] Share audit results with customer
- [ ] Add customer to MCP server (if using remote access)

## Troubleshooting

### Customer Not Found

**Problem**: "Customer 'xyz' not found"

**Solution**:
1. Check if customer exists: `python scripts/list_customers.py --status=all`
2. Check BigQuery registry directly:
   ```bash
   bq query --use_legacy_sql=false "SELECT * FROM \`topgolf-460202.paidsocialnav_registry.customers\` WHERE customer_id='xyz'"
   ```
3. Re-run onboarding script

### Permission Denied

**Problem**: Cannot access customer's GCP project

**Solution**:
1. Verify customer project exists
2. Ensure service account has necessary roles in customer project:
   - `roles/bigquery.dataEditor`
   - `roles/bigquery.jobUser`

### Registry Not Found

**Problem**: Registry dataset doesn't exist

**Solution**:
```bash
python scripts/setup_registry_python.py --project=topgolf-460202
```

## Next Steps

After onboarding a customer:

1. **Initial Data Sync**:
   ```bash
   python -m paid_social_nav.cli.main sync-meta <account_id> --tenant=<customer_id>
   ```

2. **First Audit**:
   ```bash
   python -m paid_social_nav.cli.main audit --tenant=<customer_id>
   ```

3. **Set Up Scheduled Syncs** (optional):
   - Use Cloud Scheduler to run syncs daily
   - Configure via Cloud Functions or Cloud Run Jobs

4. **Configure Alerts** (optional):
   - Set alert thresholds in customer record
   - Configure Cloud Monitoring alerts

## References

- [Customer Registry Module](../paid_social_nav/core/customer_registry.py)
- [Onboarding Script](../scripts/onboard_customer.py)
- [Registry Schema](../sql/customer_registry_schema.sql)
