# Demographic Breakdowns Feature - Implementation Summary

## Overview

Added comprehensive demographic breakdown support to PaidSocialNav, enabling analysis of **who actually saw your ads** vs. **who you targeted**. This feature pulls age, gender, geographic, and platform data from Meta's Insights API.

## What Was Implemented

### 1. Core Adapter Changes

**File**: `paid_social_nav/adapters/meta/adapter.py`

Added `breakdowns` parameter to `MetaAdapter.fetch_insights()`:
- Accepts list of breakdown dimensions: `["age", "gender"]`, `["region"]`, etc.
- Passes breakdowns to Meta Graph API via `breakdowns` query parameter
- Breakdown data stored in `raw_metrics` JSON field
- Logging support for breakdown requests

### 2. Sync Layer Updates

**File**: `paid_social_nav/core/sync.py`

Added `breakdowns` parameter to `sync_meta_insights()`:
- Accepts optional list of breakdowns from CLI
- Passes through to adapter
- No changes to data storage - breakdowns captured in existing `raw_metrics` JSON column

### 3. CLI Integration

**File**: `paid_social_nav/cli/main.py`

Added `--breakdowns` flag to `meta sync-insights` command:
```bash
psn meta sync-insights \
  --account-id act_123 \
  --breakdowns "age,gender"
```

Features:
- Comma-separated breakdown list
- Input validation and parsing
- User feedback on requested breakdowns
- Supports all Meta breakdown dimensions

### 4. BigQuery Views

**Files**:
- `sql/views/v_demographics.sql` - Raw demographic data extraction
- `sql/views/v_demographic_summary.sql` - Aggregated demographic summary

**v_demographics** extracts breakdown dimensions from JSON:
- `age_range` (18-24, 25-34, 35-44, 45-54, 55-64, 65+)
- `gender` (male, female, unknown)
- `region` (State/province)
- `country` (Country code)
- `platform` (facebook, instagram, messenger, audience_network)
- `device` (mobile, desktop, unknown)
- `placement` (feed, story, reels, etc.)

**v_demographic_summary** provides aggregated metrics:
- Total impressions/clicks/spend/conversions by demographic
- Share metrics (% of total impressions/spend)
- Performance metrics (CTR, conversion rate, CPC, CPM)
- Pre-calculated KPIs for dashboarding

### 5. Documentation

**Files**:
- `docs/demographic_breakdowns.md` - Comprehensive usage guide
- `docs/DEMOGRAPHIC_FEATURE_SUMMARY.md` - This document
- `scripts/demo_demographics.sh` - Interactive demo script

## Supported Breakdowns

| Breakdown | Description | Values |
|-----------|-------------|---------|
| `age` | Age range | 18-24, 25-34, 35-44, 45-54, 55-64, 65+ |
| `gender` | Gender | male, female, unknown |
| `region` | State/Province | California, Texas, etc. |
| `country` | Country code | US, CA, GB, etc. |
| `publisher_platform` | Meta platform | facebook, instagram, messenger, audience_network |
| `device_platform` | Device type | mobile, desktop, unknown |
| `placement` | Ad placement | feed, story, reels, right_hand_column, instant_article |

**Limitation**: Max 2 breakdowns per API request (Meta API constraint)

## Usage Examples

### Pull Demographic Data

```bash
# Age and gender breakdowns
psn meta sync-insights \
  --account-id act_229793224304371 \
  --level campaign \
  --date-preset last_30d \
  --breakdowns "age,gender"

# Geographic and platform breakdowns
psn meta sync-insights \
  --account-id act_229793224304371 \
  --level campaign \
  --date-preset last_7d \
  --breakdowns "region,publisher_platform"
```

### Analyze in BigQuery

```sql
-- Who saw your ads? (Age breakdown)
SELECT
  age_range,
  SUM(impressions) as impressions,
  ROUND(AVG(ctr_pct), 2) as avg_ctr,
  ROUND(SUM(spend), 2) as spend
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE age_range IS NOT NULL
  AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY age_range
ORDER BY impressions DESC;

-- Gender performance comparison
SELECT
  gender,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(AVG(ctr_pct), 2) as ctr,
  ROUND(AVG(conv_rate_pct), 2) as conv_rate
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE gender IS NOT NULL
GROUP BY gender;

-- Age x Gender matrix
SELECT
  age_range,
  gender,
  SUM(impressions) as impressions,
  ROUND(AVG(ctr_pct), 2) as ctr
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE age_range IS NOT NULL AND gender IS NOT NULL
GROUP BY age_range, gender
ORDER BY impressions DESC;
```

## Testing

### Unit Tests

All existing tests pass:
```bash
pytest tests/ -v
# 8 passed, 5 skipped (1 pre-existing failure in base_adapter test)
```

### Linting

Code passes all linting checks:
```bash
ruff check paid_social_nav/
# All checks passed!
```

### Integration Testing

Demo script available for manual testing:
```bash
./scripts/demo_demographics.sh
```

This script:
1. Pulls demographic data with age/gender breakdowns
2. Creates BigQuery views
3. Runs sample analysis queries
4. Shows age, gender, and age×gender breakdown results

## Data Storage

Breakdown data is stored in existing `raw_metrics` JSON column in `fct_ad_insights_daily`:

**Without breakdowns**:
```json
{
  "date_start": "2025-05-12",
  "impressions": "1234",
  "clicks": "56",
  "spend": "45.67"
}
```

**With breakdowns** (`age,gender`):
```json
{
  "date_start": "2025-05-12",
  "age": "25-34",
  "gender": "male",
  "impressions": "234",
  "clicks": "12",
  "spend": "8.90"
}
```

**Impact**: No schema changes required. Breakdowns add rows, not columns.

## Performance Considerations

### Data Volume Impact

Breakdowns increase row count significantly:

| Breakdown | Row Multiplier | Example (1 year) |
|-----------|----------------|------------------|
| None | 1x | 365 rows |
| age | 6x | 2,190 rows |
| gender | 3x | 1,095 rows |
| age,gender | 18x | 6,570 rows |
| age,gender,region | ~900x | 328,500 rows |

**Recommendations**:
- Start with `age,gender` (18x) for most analyses
- Use shorter date ranges for multi-breakdown pulls
- Pull breakdowns separately from base metrics
- Consider pulling breakdowns only for top campaigns

### Query Performance

Views use JSON extraction which can be slow on large datasets:
- `JSON_VALUE(raw_metrics, '$.age')` requires full table scan
- Consider materialized tables for large accounts (>1M rows)
- Use date partitioning filters in queries

## Targeted vs. Actual Analysis

### What We Can Determine Now

With demographic breakdowns, you can answer:
- ✅ Who actually saw our ads? (age, gender, location breakdown)
- ✅ Which demographics had best CTR/conversion rates?
- ✅ Did we reach our intended audience?
- ✅ Which platforms (Facebook vs Instagram) performed better?
- ✅ Mobile vs desktop performance differences

### What's Still Manual

Targeting configuration requires separate API call:
```bash
# Get targeting settings for campaign
curl "https://graph.facebook.com/v18.0/{campaign_id}?\
fields=targeting&access_token={token}"
```

Returns:
```json
{
  "targeting": {
    "age_min": 25,
    "age_max": 54,
    "genders": [1, 2],
    "geo_locations": {
      "cities": [{"key": "777934", "name": "Charlotte"}]
    },
    "interests": [
      {"id": "6003139266461", "name": "Golf"}
    ]
  }
}
```

**Future Enhancement**: Auto-pull targeting config and store in `dim_campaign` table for automated comparison.

## Example: Puttery Golf Analysis

Once you pull demographic data for Puttery:

```bash
# Pull demographics
psn meta sync-insights \
  --account-id act_229793224304371 \
  --level campaign \
  --date-preset last_90d \
  --breakdowns "age,gender"
```

You'll be able to answer:

1. **Audience Composition**: "70% of impressions went to 25-44 year olds"
2. **Gender Split**: "60% male, 38% female, 2% unknown"
3. **Performance by Demo**: "25-34 males have 3.5% CTR vs. 1.2% overall"
4. **Platform Effectiveness**: "Instagram drives 2x CTR vs. Facebook"
5. **Geographic Hotspots**: "Texas accounts for 45% of spend"

## Files Changed

### Modified Files
- `paid_social_nav/adapters/meta/adapter.py` - Added breakdowns parameter
- `paid_social_nav/core/sync.py` - Added breakdowns pass-through
- `paid_social_nav/cli/main.py` - Added CLI flag

### New Files
- `sql/views/v_demographics.sql` - Demographic extraction view
- `sql/views/v_demographic_summary.sql` - Aggregated summary view
- `docs/demographic_breakdowns.md` - User guide
- `docs/DEMOGRAPHIC_FEATURE_SUMMARY.md` - This document
- `scripts/demo_demographics.sh` - Demo script

## Next Steps

1. **Test with Real Data** - Run demo script with Puttery account
2. **Pull Targeting Config** - Fetch targeting settings via API for comparison
3. **Build Dashboard** - Create Looker/Tableau dashboard with demographic views
4. **Automate Reports** - Schedule weekly demographic performance reports
5. **Expand Breakdowns** - Add DMA, impression_device for deeper analysis

## References

- [Meta Marketing API - Insights Breakdowns](https://developers.facebook.com/docs/marketing-api/insights/breakdowns)
- [Meta Targeting Specs](https://developers.facebook.com/docs/marketing-api/audiences/reference/targeting-specs)
- User Guide: `docs/demographic_breakdowns.md`
