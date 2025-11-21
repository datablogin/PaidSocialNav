-- v_demographic_summary.sql
-- Aggregated demographic performance summary
-- Shows who actually saw the ads (age, gender, location breakdown)

CREATE OR REPLACE VIEW `fleming-424413.paid_social.v_demographic_summary` AS

WITH demographics AS (
  SELECT
    age_range,
    gender,
    region,
    country,
    platform,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    SUM(spend) AS spend,
    SUM(conversions) AS conversions
  FROM `fleming-424413.paid_social.v_demographics`
  GROUP BY age_range, gender, region, country, platform
)

SELECT
  age_range,
  gender,
  region,
  country,
  platform,

  -- Volume metrics
  impressions,
  clicks,
  conversions,
  ROUND(spend, 2) AS spend,

  -- Share metrics (% of total)
  ROUND(impressions / SUM(impressions) OVER () * 100, 2) AS impression_share_pct,
  ROUND(spend / SUM(spend) OVER () * 100, 2) AS spend_share_pct,

  -- Performance metrics
  ROUND(SAFE_DIVIDE(clicks, NULLIF(impressions, 0)) * 100, 2) AS ctr_pct,
  ROUND(SAFE_DIVIDE(conversions, NULLIF(clicks, 0)) * 100, 2) AS conv_rate_pct,
  ROUND(SAFE_DIVIDE(spend, NULLIF(conversions, 0)), 2) AS cost_per_conversion,
  ROUND(SAFE_DIVIDE(spend, NULLIF(clicks, 0)), 2) AS cpc,
  ROUND(SAFE_DIVIDE(spend, NULLIF(impressions, 0)) * 1000, 2) AS cpm

FROM demographics

ORDER BY impressions DESC;
