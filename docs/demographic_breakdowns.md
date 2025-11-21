# Demographic Breakdowns Guide

This guide explains how to pull and analyze demographic data from Meta's advertising platform to understand who actually saw your ads vs. who you targeted.

## Overview

Meta's Insights API supports "breakdowns" - additional dimensions that split performance data by:
- **Age**: 18-24, 25-34, 35-44, 45-54, 55-64, 65+
- **Gender**: male, female, unknown
- **Region**: State/province
- **Country**: Country code
- **Platform**: facebook, instagram, audience_network, messenger
- **Device**: mobile, desktop, unknown
- **Placement**: feed, story, reels, etc.

## Quick Start

### 1. Pull Demographic Data

```bash
# Pull data with age and gender breakdowns
psn meta sync-insights \
  --account-id act_229793224304371 \
  --level campaign \
  --date-preset last_30d \
  --breakdowns "age,gender"

# Pull with multiple breakdowns (region, platform)
psn meta sync-insights \
  --account-id act_229793224304371 \
  --level campaign \
  --date-preset last_30d \
  --breakdowns "age,gender,region,publisher_platform"
```

### 2. Analyze Demographics in BigQuery

```sql
-- View all demographic breakdowns
SELECT * FROM `puttery-golf-001.paid_social.v_demographics`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
LIMIT 100;

-- Aggregate by age and gender
SELECT
  age_range,
  gender,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(AVG(ctr_pct), 2) as avg_ctr_pct,
  ROUND(SUM(spend), 2) as spend
FROM `puttery-golf-001.paid_social.v_demographics`
GROUP BY age_range, gender
ORDER BY impressions DESC;

-- Use the summary view for quick insights
SELECT * FROM `puttery-golf-001.paid_social.v_demographic_summary`
WHERE age_range IS NOT NULL
ORDER BY impression_share_pct DESC;
```

## Supported Breakdowns

| Breakdown | Description | Example Values |
|-----------|-------------|----------------|
| `age` | Age ranges | 18-24, 25-34, 35-44, 45-54, 55-64, 65+ |
| `gender` | Gender | male, female, unknown |
| `region` | State/Province | California, Texas, New York |
| `country` | Country | US, CA, GB |
| `publisher_platform` | Where ad showed | facebook, instagram, audience_network, messenger |
| `device_platform` | Device type | mobile, desktop, unknown |
| `placement` | Ad placement | feed, story, reels, right_hand_column, instant_article |

## Common Analysis Queries

### Who Saw Your Ads? (Actual Delivery)

```sql
-- Age breakdown
SELECT
  age_range,
  SUM(impressions) as impressions,
  ROUND(SUM(impressions) / SUM(SUM(impressions)) OVER () * 100, 1) AS pct_of_total
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE age_range IS NOT NULL
GROUP BY age_range
ORDER BY impressions DESC;

-- Gender breakdown
SELECT
  gender,
  SUM(impressions) as impressions,
  ROUND(SUM(impressions) / SUM(SUM(impressions)) OVER () * 100, 1) AS pct_of_total,
  ROUND(AVG(ctr_pct), 2) as avg_ctr
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE gender IS NOT NULL
GROUP BY gender
ORDER BY impressions DESC;

-- Geographic breakdown
SELECT
  region,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(SUM(spend), 2) as spend,
  ROUND(AVG(ctr_pct), 2) as avg_ctr
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE region IS NOT NULL
GROUP BY region
ORDER BY impressions DESC
LIMIT 10;
```

### Platform Performance

```sql
-- Which platform performs best?
SELECT
  platform,
  SUM(impressions) as impressions,
  ROUND(AVG(ctr_pct), 2) as avg_ctr,
  ROUND(AVG(conv_rate_pct), 2) as avg_conv_rate,
  ROUND(SUM(spend), 2) as spend
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE platform IS NOT NULL
GROUP BY platform
ORDER BY impressions DESC;
```

### Age x Gender Matrix

```sql
-- Performance by age and gender combination
SELECT
  age_range,
  gender,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(AVG(ctr_pct), 2) as ctr,
  ROUND(SUM(spend), 2) as spend
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE age_range IS NOT NULL AND gender IS NOT NULL
GROUP BY age_range, gender
ORDER BY impressions DESC;
```

## Targeted vs. Actual Analysis

To compare targeting settings vs. actual delivery:

### Step 1: Get Targeting Configuration

```bash
# Query Meta API for targeting settings
curl "https://graph.facebook.com/v18.0/{campaign_id}?fields=targeting&access_token={token}"
```

### Step 2: Compare to Actual Delivery

```sql
-- Actual delivery (from breakdowns data)
SELECT
  age_range,
  gender,
  SUM(impressions) as actual_impressions,
  ROUND(SUM(impressions) / SUM(SUM(impressions)) OVER () * 100, 1) AS actual_pct
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE campaign_global_id = 'meta:campaign:120216654363600515'
  AND age_range IS NOT NULL
GROUP BY age_range, gender
ORDER BY actual_impressions DESC;
```

Then manually compare to targeting settings from API:
```json
{
  "targeting": {
    "age_min": 25,
    "age_max": 54,
    "genders": [1, 2]  // 1=Male, 2=Female
  }
}
```

## Important Notes

### API Limitations

- **Maximum 2 breakdowns per request**: Meta API allows max 2 breakdown dimensions simultaneously
  - ✅ Valid: `age,gender`
  - ✅ Valid: `region,publisher_platform`
  - ❌ Invalid: `age,gender,region` (3 breakdowns)

- **Some combinations not supported**: Not all breakdowns work together
  - Check [Meta's documentation](https://developers.facebook.com/docs/marketing-api/insights/breakdowns) for valid combinations

### Data Volume

Breakdowns significantly increase row count:
- **Without breakdowns**: 1 row per day per campaign = ~365 rows/year
- **With age,gender**: 6 ages × 3 genders = 18x more rows = ~6,570 rows/year
- **With age,gender,region**: Could be 50+ states × 18 = 900x = ~328,500 rows/year

**Recommendation**: Start with `age,gender` for most analyses.

### Performance Considerations

- Pull breakdowns data separately from base metrics
- Use date filters to limit scope (`--date-preset last_30d`)
- Consider pulling breakdowns only for top-performing campaigns

## Example Workflow

### For Puttery Golf:

```bash
# 1. Pull base campaign data (no breakdowns)
psn meta sync-insights \
  --account-id act_229793224304371 \
  --level campaign \
  --date-preset last_90d

# 2. Pull demographic breakdowns for recent period only
psn meta sync-insights \
  --account-id act_229793224304371 \
  --level campaign \
  --date-preset last_30d \
  --breakdowns "age,gender"

# 3. Analyze in BigQuery
bq query --use_legacy_sql=false "
SELECT
  age_range,
  gender,
  SUM(impressions) as impressions,
  ROUND(AVG(ctr_pct), 2) as avg_ctr,
  ROUND(SUM(spend), 2) as spend
FROM \`puttery-golf-001.paid_social.v_demographics\`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND age_range IS NOT NULL
GROUP BY age_range, gender
ORDER BY impressions DESC
"
```

## Troubleshooting

**Q: Demographic data not showing up in views?**
- Check that `v_demographics` view exists: `bq ls puttery-golf-001:paid_social`
- Verify `raw_metrics` JSON contains breakdown fields: `SELECT JSON_KEYS(raw_metrics) FROM fct_ad_insights_daily LIMIT 1`
- Confirm you used `--breakdowns` flag in sync command

**Q: Getting "invalid breakdown combination" error?**
- Reduce to 2 breakdowns max
- Check Meta's docs for valid combinations
- Try simpler breakdown first (just `age` or `gender`)

**Q: Why do numbers not match non-breakdown data?**
- Breakdown data may exclude some impressions (e.g., unknown age/gender)
- Sum of breakdown totals may be <100% of overall totals
- This is normal Meta API behavior

## Next Steps

- Review [Meta Marketing API Breakdowns Documentation](https://developers.facebook.com/docs/marketing-api/insights/breakdowns)
- Explore additional breakdowns: DMA, impression_device, product_id
- Build demographic dashboards in your BI tool
- Set up automated demographic reports
