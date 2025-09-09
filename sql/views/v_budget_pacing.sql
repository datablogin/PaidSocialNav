CREATE OR REPLACE VIEW `fleming-424413.paid_social.v_budget_pacing` AS
SELECT
  `level`,
  `window`,
  SUM(spend) AS spend
FROM `fleming-424413.paid_social.insights_rollups`
GROUP BY `level`, `window`;

