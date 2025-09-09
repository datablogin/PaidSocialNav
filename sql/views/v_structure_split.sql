CREATE OR REPLACE VIEW `fleming-424413.paid_social.v_structure_split` AS
SELECT
  `level`,
  `window`,
  COUNT(DISTINCT COALESCE(CAST(ad_id AS STRING), CAST(adset_id AS STRING), CAST(campaign_id AS STRING), CAST(account_id AS STRING))) AS entity_count,
  SUM(spend) AS spend_total
FROM `fleming-424413.paid_social.insights_rollups`
GROUP BY `level`, `window`;

