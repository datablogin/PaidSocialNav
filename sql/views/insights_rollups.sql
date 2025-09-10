CREATE OR REPLACE VIEW `fleming-424413.paid_social.insights_rollups` AS
WITH params AS (
  SELECT
    CURRENT_DATE() AS today,
    DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) AS yesterday,
    DATE_TRUNC(CURRENT_DATE(), MONTH) AS month_start,
    DATE_TRUNC(CURRENT_DATE(), QUARTER) AS quarter_start,
    EXTRACT(YEAR FROM CURRENT_DATE()) AS y
),
base AS (
  SELECT
    DATE(date) AS dt,
    `level`,
    account_global_id AS account_id,
    campaign_global_id AS campaign_id,
    adset_global_id AS adset_id,
    ad_global_id AS ad_id,
    CAST(spend AS NUMERIC) AS spend,
    CAST(impressions AS INT64) AS impressions,
    CAST(clicks AS INT64) AS clicks,
    CAST(conversions AS INT64) AS conversions
  FROM `fleming-424413.paid_social.fct_ad_insights_daily`
),
windows AS (
  SELECT 'last_7d' AS `window`, DATE_SUB(p.today, INTERVAL 7 DAY) AS window_start, p.yesterday AS window_end FROM params p
  UNION ALL SELECT 'last_28d', DATE_SUB(p.today, INTERVAL 28 DAY), p.yesterday FROM params p
  UNION ALL SELECT 'last_90d', DATE_SUB(p.today, INTERVAL 90 DAY), p.yesterday FROM params p
  UNION ALL SELECT 'MTD', p.month_start, p.yesterday FROM params p
  UNION ALL SELECT 'YTD', DATE(p.y, 1, 1), p.yesterday FROM params p
  UNION ALL SELECT 'last_quarter', DATE_SUB(p.quarter_start, INTERVAL 1 QUARTER), DATE_SUB(p.quarter_start, INTERVAL 1 DAY) FROM params p
  UNION ALL SELECT 'Q1', DATE(p.y, 1, 1), LEAST(DATE(p.y, 3, 31), p.yesterday) FROM params p
  UNION ALL SELECT 'Q2', DATE(p.y, 4, 1), LEAST(DATE(p.y, 6, 30), p.yesterday) FROM params p
  UNION ALL SELECT 'Q3', DATE(p.y, 7, 1), LEAST(DATE(p.y, 9, 30), p.yesterday) FROM params p
  UNION ALL SELECT 'Q4', DATE(p.y, 10, 1), LEAST(DATE(p.y, 12, 31), p.yesterday) FROM params p
),
rolled AS (
  SELECT
    b.`level`,
    'paid_social' AS platform,
    w.`window`,
    w.window_start,
    w.window_end,
    b.account_id,
    b.campaign_id,
    b.adset_id,
    b.ad_id,
    SUM(b.spend) AS spend,
    SUM(b.impressions) AS impressions,
    SUM(b.clicks) AS clicks,
    SUM(b.conversions) AS conversions
  FROM base b
  CROSS JOIN windows w
  WHERE b.dt BETWEEN w.window_start AND w.window_end
  GROUP BY
    b.`level`, platform, w.`window`, w.window_start, w.window_end,
    account_id, campaign_id, adset_id, ad_id
)
SELECT
  `level`,
  platform,
  `window`,
  window_start,
  window_end,
  account_id, campaign_id, adset_id, ad_id,
  spend,
  impressions,
  clicks,
  SAFE_DIVIDE(clicks, NULLIF(impressions, 0)) AS ctr,
  conversions,
  SAFE_DIVIDE(spend, NULLIF(conversions, 0)) AS cpa,
  CURRENT_TIMESTAMP() AS updated_at
FROM rolled;
