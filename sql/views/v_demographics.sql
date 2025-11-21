-- v_demographics.sql
-- Demographic breakdown analysis from Meta insights with age/gender/region breakdowns
-- Extracts breakdown dimensions from raw_metrics JSON field

CREATE OR REPLACE VIEW `fleming-424413.paid_social.v_demographics` AS

SELECT
  date,
  level,
  campaign_global_id,
  adset_global_id,
  ad_global_id,

  -- Extract demographic breakdowns from raw_metrics JSON
  JSON_VALUE(raw_metrics, '$.age') AS age_range,
  JSON_VALUE(raw_metrics, '$.gender') AS gender,
  JSON_VALUE(raw_metrics, '$.region') AS region,
  JSON_VALUE(raw_metrics, '$.country') AS country,
  JSON_VALUE(raw_metrics, '$.publisher_platform') AS platform,
  JSON_VALUE(raw_metrics, '$.device_platform') AS device,
  JSON_VALUE(raw_metrics, '$.placement') AS placement,

  -- Performance metrics
  impressions,
  clicks,
  spend,
  conversions,
  ctr,
  frequency,

  -- Calculated metrics
  SAFE_DIVIDE(clicks, NULLIF(impressions, 0)) * 100 AS ctr_pct,
  SAFE_DIVIDE(conversions, NULLIF(clicks, 0)) * 100 AS conv_rate_pct,
  SAFE_DIVIDE(spend, NULLIF(conversions, 0)) AS cost_per_conversion,
  SAFE_DIVIDE(spend, NULLIF(clicks, 0)) AS cpc,
  SAFE_DIVIDE(spend, NULLIF(impressions, 0)) * 1000 AS cpm

FROM `fleming-424413.paid_social.fct_ad_insights_daily`

-- Only include rows where at least one breakdown dimension exists
WHERE
  JSON_VALUE(raw_metrics, '$.age') IS NOT NULL
  OR JSON_VALUE(raw_metrics, '$.gender') IS NOT NULL
  OR JSON_VALUE(raw_metrics, '$.region') IS NOT NULL
  OR JSON_VALUE(raw_metrics, '$.country') IS NOT NULL
  OR JSON_VALUE(raw_metrics, '$.publisher_platform') IS NOT NULL
  OR JSON_VALUE(raw_metrics, '$.device_platform') IS NOT NULL
  OR JSON_VALUE(raw_metrics, '$.placement') IS NOT NULL;
