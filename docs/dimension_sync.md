# BigQuery Dimension Sync

This document describes the dimension sync functionality for Meta advertising data in PaidSocialNav.

## Overview

The dimension sync feature pulls dimension data (accounts, campaigns, ad sets, ads, and creatives) from the Meta Graph API and loads them into BigQuery dimension tables. This enables proper referential integrity and rich reporting capabilities when joined with the fact table `fct_ad_insights_daily`.

## Dimension Tables

### dim_account

Stores Meta ad account information.

**Schema:**
- `account_global_id` (STRING, REQUIRED): Global identifier in format `meta:account:{act_id}`
- `platform_account_id` (STRING, REQUIRED): Meta platform account ID
- `account_name` (STRING): Account display name
- `currency` (STRING): Account currency code
- `timezone` (STRING): Account timezone
- `account_status` (STRING): Account status
- `updated_at` (TIMESTAMP): Last sync timestamp
- `raw_data` (JSON): Complete API response

**Primary Key:** `account_global_id`

### dim_campaign

Stores campaign-level dimension data.

**Schema:**
- `campaign_global_id` (STRING, REQUIRED): Global identifier in format `meta:campaign:{campaign_id}`
- `platform_campaign_id` (STRING, REQUIRED): Meta platform campaign ID
- `account_global_id` (STRING, REQUIRED): Foreign key to dim_account
- `campaign_name` (STRING): Campaign name
- `campaign_status` (STRING): Campaign status (ACTIVE, PAUSED, etc.)
- `objective` (STRING): Campaign objective
- `buying_type` (STRING): Buying type (AUCTION, RESERVED)
- `daily_budget` (FLOAT64): Daily budget in account currency
- `lifetime_budget` (FLOAT64): Lifetime budget in account currency
- `created_time` (TIMESTAMP): Campaign creation timestamp
- `updated_at` (TIMESTAMP): Last sync timestamp
- `raw_data` (JSON): Complete API response

**Primary Key:** `campaign_global_id`
**Foreign Keys:** `account_global_id` → `dim_account.account_global_id`

### dim_adset

Stores ad set dimension data.

**Schema:**
- `adset_global_id` (STRING, REQUIRED): Global identifier in format `meta:adset:{adset_id}`
- `platform_adset_id` (STRING, REQUIRED): Meta platform ad set ID
- `campaign_global_id` (STRING, REQUIRED): Foreign key to dim_campaign
- `account_global_id` (STRING, REQUIRED): Foreign key to dim_account
- `adset_name` (STRING): Ad set name
- `adset_status` (STRING): Ad set status
- `optimization_goal` (STRING): Optimization goal
- `billing_event` (STRING): Billing event type
- `bid_strategy` (STRING): Bid strategy
- `daily_budget` (FLOAT64): Daily budget
- `lifetime_budget` (FLOAT64): Lifetime budget
- `start_time` (TIMESTAMP): Ad set start time
- `end_time` (TIMESTAMP): Ad set end time
- `created_time` (TIMESTAMP): Creation timestamp
- `updated_at` (TIMESTAMP): Last sync timestamp
- `raw_data` (JSON): Complete API response

**Primary Key:** `adset_global_id`
**Foreign Keys:**
- `campaign_global_id` → `dim_campaign.campaign_global_id`
- `account_global_id` → `dim_account.account_global_id`

### dim_ad

Stores ad-level dimension data.

**Schema:**
- `ad_global_id` (STRING, REQUIRED): Global identifier in format `meta:ad:{ad_id}`
- `platform_ad_id` (STRING, REQUIRED): Meta platform ad ID
- `adset_global_id` (STRING, REQUIRED): Foreign key to dim_adset
- `campaign_global_id` (STRING, REQUIRED): Foreign key to dim_campaign
- `account_global_id` (STRING, REQUIRED): Foreign key to dim_account
- `ad_name` (STRING): Ad name
- `ad_status` (STRING): Ad status
- `creative_global_id` (STRING): Foreign key to dim_creative
- `created_time` (TIMESTAMP): Creation timestamp
- `updated_at` (TIMESTAMP): Last sync timestamp
- `raw_data` (JSON): Complete API response

**Primary Key:** `ad_global_id`
**Foreign Keys:**
- `adset_global_id` → `dim_adset.adset_global_id`
- `campaign_global_id` → `dim_campaign.campaign_global_id`
- `account_global_id` → `dim_account.account_global_id`
- `creative_global_id` → `dim_creative.creative_global_id`

### dim_creative

Stores creative dimension data.

**Schema:**
- `creative_global_id` (STRING, REQUIRED): Global identifier in format `meta:creative:{creative_id}`
- `platform_creative_id` (STRING, REQUIRED): Meta platform creative ID
- `account_global_id` (STRING, REQUIRED): Foreign key to dim_account
- `creative_name` (STRING): Creative name
- `creative_status` (STRING): Creative status
- `title` (STRING): Creative title
- `body` (STRING): Creative body text
- `call_to_action` (STRING): Call to action type
- `image_url` (STRING): Image URL
- `video_url` (STRING): Video URL
- `thumbnail_url` (STRING): Thumbnail URL
- `created_time` (TIMESTAMP): Creation timestamp
- `updated_at` (TIMESTAMP): Last sync timestamp
- `raw_data` (JSON): Complete API response

**Primary Key:** `creative_global_id`
**Foreign Keys:** `account_global_id` → `dim_account.account_global_id`

## Usage

### CLI Command

Sync all dimensions for a Meta ad account:

```bash
psn meta sync-dimensions --tenant <tenant_id> --use-secret --account-id <account_id>
```

**Options:**
- `--account-id` (required): Meta ad account ID (with or without `act_` prefix)
- `--tenant` (optional): Tenant ID from `configs/tenants.yaml` for project/dataset routing
- `--use-secret`: Fetch `META_ACCESS_TOKEN` from Secret Manager
- `--secret-name`: Secret name (default: `META_ACCESS_TOKEN`)
- `--secret-version`: Secret version (default: `latest`)
- `--page-size`: API page size (default: 500, max: 1000)
- `--retries`: Number of retry attempts on API failures (default: 3)
- `--retry-backoff-seconds`: Backoff time between retries (default: 2.0)

### Example

```bash
# Sync dimensions for Fleming tenant
psn meta sync-dimensions \
  --tenant fleming \
  --use-secret \
  --account-id act_123456789 \
  --page-size 500 \
  --retries 3
```

### Programmatic Usage

```python
from paid_social_nav.adapters.meta.dimensions import sync_all_dimensions

counts = sync_all_dimensions(
    account_id="act_123456789",
    project_id="my-gcp-project",
    dataset="paid_social",
    access_token="EAABsbCS...",
    page_size=500,
    retries=3,
    retry_backoff=2.0,
)

print(f"Synced {counts['campaigns']} campaigns")
print(f"Synced {counts['adsets']} ad sets")
print(f"Synced {counts['ads']} ads")
print(f"Synced {counts['creatives']} creatives")
```

## Data Flow

1. **Fetch**: Data is fetched from Meta Graph API with pagination
2. **Transform**: API responses are transformed into standardized dimension records
3. **Stage**: Records are loaded into temporary staging tables
4. **Merge**: Staging data is merged into dimension tables using `MERGE` statements
5. **Cleanup**: Staging tables are removed

## Upsert Logic

All dimension syncs use `MERGE` statements to ensure idempotency:

- **ON MATCH**: Updates all fields except the primary key
- **ON NO MATCH**: Inserts new record

This ensures that:
- Re-running sync updates existing records with latest data
- New records are added without duplication
- No data loss occurs during sync operations

## Referential Integrity

To verify that fact table foreign keys match dimension primary keys:

```sql
-- Check campaign coverage
SELECT
  COUNT(DISTINCT f.campaign_global_id) as fact_campaigns,
  COUNT(DISTINCT d.campaign_global_id) as dim_campaigns,
  COUNT(DISTINCT f.campaign_global_id) - COUNT(DISTINCT d.campaign_global_id) as missing
FROM `project.dataset.fct_ad_insights_daily` f
LEFT JOIN `project.dataset.dim_campaign` d
  ON f.campaign_global_id = d.campaign_global_id;

-- Check for orphaned facts (facts without matching dimensions)
SELECT
  f.campaign_global_id,
  COUNT(*) as fact_rows
FROM `project.dataset.fct_ad_insights_daily` f
LEFT JOIN `project.dataset.dim_campaign` d
  ON f.campaign_global_id = d.campaign_global_id
WHERE d.campaign_global_id IS NULL
GROUP BY f.campaign_global_id;
```

## Performance Considerations

- **Pagination**: API requests use pagination to handle large datasets efficiently
- **Retries**: Automatic retry with exponential backoff handles transient API errors
- **Staging Tables**: Unique staging table names prevent race conditions during concurrent syncs
- **Batch Loading**: Data is loaded in batches to minimize memory usage
- **Idempotency**: MERGE operations ensure safe re-runs without duplicates

## Error Handling

The sync process includes comprehensive error handling:

- **API Errors**: Retries with exponential backoff
- **Rate Limiting**: Configurable rate limiting (via page size and retries)
- **Data Validation**: Safe type conversion for nullable fields
- **Logging**: Structured logging with context at each step
- **Transaction Safety**: Staging tables ensure all-or-nothing semantics

## KPIs

Issue #4 specifies the following KPIs:

- **Completeness**: Number of entities in BigQuery should be within ±5% of API counts
- **Staleness**: All dimensions should be updated within 24 hours of sync
- **Integrity**: 100% referential coverage of fact FK → dim PK for the loaded window

To measure these:

```sql
-- Completeness: Compare counts
SELECT
  'campaigns' as dimension,
  COUNT(*) as bq_count
FROM `project.dataset.dim_campaign`;

-- Staleness: Check last update times
SELECT
  MAX(updated_at) as last_sync,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(updated_at), HOUR) as hours_since_sync
FROM `project.dataset.dim_campaign`;

-- Integrity: Check join coverage
SELECT
  COUNT(DISTINCT f.campaign_global_id) as total_campaigns,
  COUNT(DISTINCT d.campaign_global_id) as matched_campaigns,
  ROUND(COUNT(DISTINCT d.campaign_global_id) / COUNT(DISTINCT f.campaign_global_id) * 100, 2) as coverage_pct
FROM `project.dataset.fct_ad_insights_daily` f
LEFT JOIN `project.dataset.dim_campaign` d
  ON f.campaign_global_id = d.campaign_global_id;
```

## Scheduling

For automated daily sync, set up a Cloud Scheduler job:

```bash
gcloud scheduler jobs create http meta-dimension-sync \
  --schedule="0 2 * * *" \
  --uri="https://your-cloud-run-url/sync-dimensions" \
  --http-method=POST \
  --message-body='{"account_id":"act_123456789","tenant":"fleming"}'
```

Or use a cron job:

```bash
# Daily at 2 AM
0 2 * * * cd /path/to/PaidSocialNav && psn meta sync-dimensions --tenant fleming --use-secret --account-id act_123456789
```
