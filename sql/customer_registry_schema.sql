-- Customer Registry Schema
-- This table stores all PaidSocialNav customers in a central BigQuery registry
-- Location: Primary GCP project (e.g., topgolf-460202)
-- Dataset: paidsocialnav_registry

CREATE TABLE IF NOT EXISTS `{project_id}.paidsocialnav_registry.customers` (
  -- Core Identity
  customer_id STRING NOT NULL,  -- Unique identifier (e.g., 'puttery', 'fleming')
  customer_name STRING NOT NULL,  -- Display name (e.g., 'Puttery Golf')

  -- GCP Configuration
  gcp_project_id STRING NOT NULL,  -- Customer's GCP project
  bq_dataset STRING NOT NULL DEFAULT 'paid_social',  -- BigQuery dataset for paid social data

  -- Meta/Facebook Configuration
  meta_ad_account_ids ARRAY<STRING>,  -- Array of Meta ad account IDs
  meta_access_token_secret STRING,  -- Secret Manager reference (e.g., 'projects/PROJECT/secrets/CUSTOMER_META_TOKEN')

  -- Platform Configuration
  default_level STRING DEFAULT 'campaign',  -- Default aggregation level (ad, adset, campaign)
  active_platforms ARRAY<STRING> DEFAULT ['meta'],  -- Active platforms (meta, reddit, pinterest, tiktok, x)

  -- Status and Metadata
  status STRING DEFAULT 'active',  -- active, paused, churned
  onboarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  created_by STRING,  -- User who onboarded this customer

  -- Billing and Usage
  monthly_spend_limit FLOAT64,  -- Optional monthly spend limit for audits
  usage_tier STRING DEFAULT 'standard',  -- standard, premium, enterprise

  -- Contact Information
  primary_contact_email STRING,
  primary_contact_name STRING,

  -- Audit Configuration
  audit_schedule STRING,  -- Cron expression for scheduled audits (optional)
  alert_thresholds JSON,  -- Custom alert thresholds as JSON

  -- Custom Metadata
  tags ARRAY<STRING>,  -- Tags for organization (e.g., ['golf', 'entertainment', 'franchise'])
  notes STRING  -- Free-form notes
)
PARTITION BY DATE(onboarded_at)
CLUSTER BY customer_id, status, usage_tier;

-- Create a view for active customers only
CREATE OR REPLACE VIEW `{project_id}.paidsocialnav_registry.active_customers` AS
SELECT
  customer_id,
  customer_name,
  gcp_project_id,
  bq_dataset,
  meta_ad_account_ids,
  default_level,
  active_platforms,
  onboarded_at,
  usage_tier,
  primary_contact_email
FROM `{project_id}.paidsocialnav_registry.customers`
WHERE status = 'active';

-- Create usage tracking table
CREATE TABLE IF NOT EXISTS `{project_id}.paidsocialnav_registry.customer_usage` (
  customer_id STRING NOT NULL,
  usage_date DATE NOT NULL,

  -- API Usage
  meta_api_calls INT64 DEFAULT 0,
  bigquery_bytes_processed INT64 DEFAULT 0,

  -- Audit Metrics
  audits_run INT64 DEFAULT 0,
  reports_generated INT64 DEFAULT 0,

  -- AI Usage
  anthropic_input_tokens INT64 DEFAULT 0,
  anthropic_output_tokens INT64 DEFAULT 0,

  -- Costs (estimated)
  estimated_cost_usd FLOAT64 DEFAULT 0.0,

  -- Metadata
  recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY usage_date
CLUSTER BY customer_id, usage_date;

-- Create audit history table
CREATE TABLE IF NOT EXISTS `{project_id}.paidsocialnav_registry.audit_history` (
  audit_id STRING NOT NULL,  -- Unique audit run ID
  customer_id STRING NOT NULL,

  -- Audit Configuration
  audit_level STRING,  -- ad, adset, campaign, account
  audit_window STRING,  -- last_7d, last_14d, last_28d, custom
  audit_config_path STRING,  -- Path to audit config used

  -- Results
  overall_score FLOAT64,
  total_issues INT64,
  critical_issues INT64,
  warnings INT64,

  -- Performance
  execution_time_seconds FLOAT64,
  rows_analyzed INT64,

  -- Outputs
  report_formats ARRAY<STRING>,  -- ['md', 'html', 'pdf', 'sheets']
  sheets_url STRING,  -- Google Sheets URL if exported

  -- Metadata
  executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  executed_by STRING,  -- User or 'mcp-server' or 'cli'
  execution_mode STRING  -- 'manual', 'scheduled', 'mcp'
)
PARTITION BY DATE(executed_at)
CLUSTER BY customer_id, audit_level, DATE(executed_at);
