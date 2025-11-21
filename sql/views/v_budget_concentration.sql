-- v_budget_concentration.sql
-- Provides entity-level spend ranking and cumulative budget share analysis

CREATE OR REPLACE VIEW `puttery-golf-001.paid_social.v_budget_concentration` AS

-- Use same window definitions as insights_rollups for consistency
WITH params AS (
  SELECT
    CURRENT_DATE() AS today,
    DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) AS yesterday,
    DATE_TRUNC(CURRENT_DATE(), MONTH) AS month_start,
    DATE_TRUNC(CURRENT_DATE(), QUARTER) AS quarter_start,
    EXTRACT(YEAR FROM CURRENT_DATE()) AS y
),

windows AS (
  SELECT 'last_7d' AS `window`, DATE_SUB(yesterday, INTERVAL 6 DAY) AS window_start, yesterday AS window_end FROM params
  UNION ALL SELECT 'last_28d', DATE_SUB(yesterday, INTERVAL 27 DAY), yesterday FROM params
  UNION ALL SELECT 'last_90d', DATE_SUB(yesterday, INTERVAL 89 DAY), yesterday FROM params
  UNION ALL SELECT 'MTD', month_start, yesterday FROM params
  UNION ALL SELECT 'YTD', DATE(y, 1, 1), yesterday FROM params
  UNION ALL SELECT 'last_quarter', DATE_SUB(quarter_start, INTERVAL 1 QUARTER), DATE_SUB(quarter_start, INTERVAL 1 DAY) FROM params
  UNION ALL SELECT 'Q1', DATE(y, 1, 1), LEAST(DATE(y, 3, 31), yesterday) FROM params
  UNION ALL SELECT 'Q2', DATE(y, 4, 1), LEAST(DATE(y, 6, 30), yesterday) FROM params
  UNION ALL SELECT 'Q3', DATE(y, 7, 1), LEAST(DATE(y, 9, 30), yesterday) FROM params
  UNION ALL SELECT 'Q4', DATE(y, 10, 1), LEAST(DATE(y, 12, 31), yesterday) FROM params
),

-- Aggregate spend by entity (handles different levels via COALESCE)
entity_spend AS (
  SELECT
    b.`level`,
    w.`window`,
    COALESCE(
      CAST(b.ad_global_id AS STRING),
      CAST(b.adset_global_id AS STRING),
      CAST(b.campaign_global_id AS STRING),
      CAST(b.account_global_id AS STRING)
    ) AS entity_id,
    SUM(CAST(b.spend AS FLOAT64)) AS spend
  FROM `puttery-golf-001.paid_social.fct_ad_insights_daily` b
  CROSS JOIN windows w
  WHERE b.date BETWEEN w.window_start AND w.window_end
  GROUP BY b.`level`, w.`window`, entity_id
),

-- Calculate total spend per level/window for share calculation
total_spend AS (
  SELECT
    `level`,
    `window`,
    SUM(spend) AS total
  FROM entity_spend
  GROUP BY `level`, `window`
),

-- Rank entities and calculate shares
ranked AS (
  SELECT
    e.`level`,
    e.`window`,
    e.entity_id,
    e.spend,
    t.total AS total_spend,
    RANK() OVER (PARTITION BY e.`level`, e.`window` ORDER BY e.spend DESC) AS rank,
    SAFE_DIVIDE(e.spend, NULLIF(t.total, 0)) AS spend_share
  FROM entity_spend e
  JOIN total_spend t
    ON e.`level` = t.`level` AND e.`window` = t.`window`
)

-- Calculate cumulative share
SELECT
  `level`,
  `window`,
  entity_id,
  rank,
  spend,
  spend_share,
  SUM(spend_share) OVER (
    PARTITION BY `level`, `window`
    ORDER BY rank
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cum_share
FROM ranked
ORDER BY `level`, `window`, rank;
