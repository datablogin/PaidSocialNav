CREATE OR REPLACE VIEW `fleming-424413.paid_social.v_creative_mix` AS
-- Note: current fact schema does not include creative-type breakdowns; this view returns NULL shares.
-- When video_impressions/image_impressions are available in insights_rollups, replace with proper aggregations.
SELECT
  `level`,
  `window`,
  CAST(NULL AS FLOAT64) AS video_share,
  CAST(NULL AS FLOAT64) AS image_share
FROM (
  SELECT DISTINCT `level`, `window` FROM `fleming-424413.paid_social.insights_rollups`
);

