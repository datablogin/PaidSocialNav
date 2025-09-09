CREATE OR REPLACE VIEW `fleming-424413.paid_social.v_creative_mix` AS
WITH params AS (
  SELECT
    CURRENT_DATE() AS today,
    DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) AS yesterday,
    DATE_TRUNC(CURRENT_DATE(), MONTH) AS month_start,
    DATE_TRUNC(CURRENT_DATE(), QUARTER) AS quarter_start,
    EXTRACT(YEAR FROM CURRENT_DATE()) AS y
),
windows AS (
  SELECT 'last_7d' AS `window`, DATE_SUB(p.today, INTERVAL 7 DAY) AS window_start, p.yesterday AS window_end FROM params p
  UNION ALL SELECT 'last_28d', DATE_SUB(p.today, INTERVAL 28 DAY), p.yesterday FROM params p
  UNION ALL SELECT 'last_90d', DATE_SUB(p.today, INTERVAL 90 DAY), p.yesterday FROM params p
  UNION ALL SELECT 'MTD', p.month_start, p.yesterday FROM params p
  UNION ALL SELECT 'YTD', DATE(p.y, 1, 1), p.yesterday FROM params p
  UNION ALL SELECT 'last_quarter', DATE_SUB(p.quarter_start, INTERVAL 1 QUARTER), DATE_SUB(p.quarter_start, INTERVAL 1 DAY) FROM params p
  UNION ALL SELECT 'Q1', DATE(p.y, 1, 1), DATE(p.y, 3, 31) FROM params p
  UNION ALL SELECT 'Q2', DATE(p.y, 4, 1), DATE(p.y, 6, 30) FROM params p
  UNION ALL SELECT 'Q3', DATE(p.y, 7, 1), DATE(p.y, 9, 30) FROM params p
  UNION ALL SELECT 'Q4', DATE(p.y, 10, 1), DATE(p.y, 12, 31) FROM params p
),
fact AS (
  SELECT DATE(date) AS dt,
         `level`,
         account_global_id AS account_id,
         campaign_global_id AS campaign_id,
         adset_global_id AS adset_id,
         ad_global_id AS ad_id,
         CAST(impressions AS INT64) AS impressions
  FROM `fleming-424413.paid_social.fct_ad_insights_daily`
  WHERE ad_global_id IS NOT NULL
),
with_media AS (
  SELECT f.dt, f.`level`, f.account_id, f.campaign_id, f.adset_id, f.ad_id, f.impressions,
         IF(d.media_type = 'video', f.impressions, 0) AS video_impr,
         IF(d.media_type = 'image', f.impressions, 0) AS image_impr
  FROM fact f
  LEFT JOIN `fleming-424413.paid_social.dim_ad` d
  ON d.ad_global_id = f.ad_id
),
rolled AS (
  SELECT
    w.`window`,
    f.`level`,
    SUM(impressions) AS impressions,
    SUM(video_impr) AS video_impressions,
    SUM(image_impr) AS image_impressions
  FROM with_media f
  CROSS JOIN windows w
  WHERE f.dt BETWEEN w.window_start AND w.window_end
  GROUP BY w.`window`, f.`level`
)
SELECT
  `level`,
  `window`,
  SAFE_DIVIDE(video_impressions, NULLIF(impressions, 0)) AS video_share,
  SAFE_DIVIDE(image_impressions, NULLIF(impressions, 0)) AS image_share
FROM rolled;

