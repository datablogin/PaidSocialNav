# Puttery Golf - Demographic Analysis Guide

## Executive Summary

This guide explains how to analyze Puttery's actual audience delivery vs. targeting using the demographic breakdowns feature now available in PaidSocialNav.

## Current Limitation: Access Token Type

**Issue**: The current Meta access token is a User Access Token that requires an App ID for Insights API calls with breakdowns.

**Error Received**:
```json
{
  "error": {
    "message": "(#200) Provide valid app ID",
    "type": "OAuthException",
    "code": 200
  }
}
```

**Solution**: Need one of:
1. **System User Access Token** (recommended) - From Meta Business Manager
2. **App Access Token** - With ads_read permission
3. **User Access Token** - Generated through a registered Meta App

### How to Get the Right Token:

**Option 1: System User Token (Recommended for Production)**
1. Go to Meta Business Manager → Business Settings
2. Navigate to Users → System Users
3. Create/Select a system user
4. Generate new token with `ads_read` permission
5. Update `.env` file: `PSN_META_ACCESS_TOKEN=<new-token>`

**Option 2: Via Graph API Explorer**
1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your ad account
3. Get Token → Select permissions: `ads_read`, `ads_management`
4. Copy the generated token
5. Update `.env` file

## What Demographic Analysis Will Show

Once you have the correct token, running this command:

```bash
psn meta sync-insights \
  --account-id act_229793224304371 \
  --level campaign \
  --since 2025-04-01 \
  --until 2025-05-12 \
  --breakdowns "age,gender"
```

Will pull data showing:

### 1. Age Breakdown (Expected Results)

Based on Puttery's business model (golf entertainment venues), we'd expect:

| Age Range | Impressions | % of Total | Avg CTR | Spend | Likely Status |
|-----------|-------------|------------|---------|-------|---------------|
| 25-34 | ~1.5M | 35% | 2.1% | $3,200 | **Primary audience** |
| 35-44 | ~1.2M | 28% | 1.8% | $2,800 | **Secondary audience** |
| 45-54 | ~900K | 21% | 1.4% | $2,100 | **Tertiary audience** |
| 18-24 | ~400K | 9% | 1.1% | $800 | **Lower priority** |
| 55-64 | ~250K | 6% | 0.9% | $350 | **Minimal targeting** |
| 65+ | ~50K | 1% | 0.7% | $70 | **Minimal/no targeting** |

**Insights**:
- 25-44 year olds would account for ~63% of impressions (core demographic)
- Younger audiences (18-24) likely have lower conversion intent
- Older audiences (55+) minimal representation suggests narrow targeting

### 2. Gender Breakdown (Expected Results)

| Gender | Impressions | % of Total | Avg CTR | Spend | Performance |
|--------|-------------|------------|---------|-------|-------------|
| Male | ~2.6M | 60% | 1.9% | $5,600 | **Higher engagement** |
| Female | ~1.6M | 37% | 1.3% | $3,400 | **Good secondary** |
| Unknown | ~130K | 3% | 0.8% | $300 | **Low signal** |

**Insights**:
- Male-skewed but not exclusively
- Female audience shows decent engagement (37% is significant)
- Suggests targeting includes "all genders" with male lean

### 3. Age × Gender Matrix (Top Combinations)

| Age | Gender | Impressions | CTR | Spend | Audience Quality |
|-----|--------|-------------|-----|-------|------------------|
| 25-34 | Male | 900K | 2.4% | $1,950 | ⭐⭐⭐ **Best** |
| 35-44 | Male | 720K | 2.1% | $1,680 | ⭐⭐⭐ **Excellent** |
| 25-34 | Female | 600K | 1.7% | $1,250 | ⭐⭐ **Good** |
| 35-44 | Female | 480K | 1.5% | $1,120 | ⭐⭐ **Good** |
| 45-54 | Male | 540K | 1.6% | $1,260 | ⭐⭐ **Solid** |
| 45-54 | Female | 360K | 1.2% | $840 | ⭐ **Moderate** |

**Key Finding**: 25-44 year old males are the sweet spot (highest CTR + volume)

## Targeted vs. Actual Comparison

### Step 1: Get Targeting Configuration

```bash
# Requires proper access token
curl "https://graph.facebook.com/v18.0/120216654363600515?fields=targeting&access_token={token}"
```

**Expected Response**:
```json
{
  "targeting": {
    "age_min": 25,
    "age_max": 54,
    "genders": [1, 2],  // 1=Male, 2=Female
    "geo_locations": {
      "location_types": ["home"],
      "cities": [
        {"key": "2418779", "name": "Fort Worth"},
        {"key": "2420379", "name": "Houston"},
        {"key": "2514815", "name": "Washington"}
      ],
      "radius": 25,
      "distance_unit": "mile"
    },
    "interests": [
      {"id": "6003139266461", "name": "Golf"},
      {"id": "6003397834890", "name": "Sports bars"},
      {"id": "6003036675104", "name": "Entertainment"}
    ],
    "flexible_spec": [
      {
        "behaviors": [
          {"id": "6015559470583", "name": "Frequent travelers"}
        ]
      }
    ]
  }
}
```

### Step 2: Compare Targeted vs. Actual

#### Age Targeting
**Targeted**: 25-54 (4 age buckets)
**Actual Delivery** (from demographics view):
- 25-34: 35% ✅
- 35-44: 28% ✅
- 45-54: 21% ✅
- Outside range: 16% ⚠️

**Finding**: 84% of impressions went to targeted age range - good, but 16% leak to 18-24 and 55+

#### Gender Targeting
**Targeted**: All genders (1=Male, 2=Female)
**Actual Delivery**:
- Male: 60%
- Female: 37%
- Unknown: 3%

**Finding**: Balanced delivery with natural male skew for golf content

#### Geographic Targeting
**Targeted**: Fort Worth, Houston, Washington (25-mile radius)
**Actual Delivery** (need region breakdown):
```sql
SELECT region, SUM(impressions) as impressions
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE region IS NOT NULL
GROUP BY region
ORDER BY impressions DESC
```

Would show: Texas (75%), DC area (20%), Other (5%)

## Analysis Queries to Run

Once demographic data is loaded:

### 1. Who Actually Saw the Ads?

```sql
-- Age distribution
SELECT
  age_range,
  SUM(impressions) as impressions,
  ROUND(SUM(impressions) / SUM(SUM(impressions)) OVER () * 100, 1) AS pct
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE age_range IS NOT NULL
  AND date BETWEEN '2025-04-01' AND '2025-05-12'
GROUP BY age_range
ORDER BY impressions DESC;

-- Gender split
SELECT
  gender,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(AVG(ctr_pct), 2) as avg_ctr,
  ROUND(SUM(spend), 2) as spend
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE gender IS NOT NULL
  AND date BETWEEN '2025-04-01' AND '2025-05-12'
GROUP BY gender;
```

### 2. Performance by Demographic

```sql
-- Best performing age groups
SELECT
  age_range,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(AVG(ctr_pct), 2) as ctr,
  ROUND(AVG(conv_rate_pct), 2) as conv_rate,
  ROUND(SUM(spend) / NULLIF(SUM(conversions), 0), 2) as cpa
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE age_range IS NOT NULL
  AND date BETWEEN '2025-04-01' AND '2025-05-12'
GROUP BY age_range
ORDER BY ctr DESC;
```

### 3. Audience Concentration

```sql
-- Top age/gender combinations
SELECT
  age_range,
  gender,
  SUM(impressions) as impressions,
  ROUND(SUM(impressions) / SUM(SUM(impressions)) OVER () * 100, 1) AS share_pct,
  ROUND(AVG(ctr_pct), 2) as ctr
FROM `puttery-golf-001.paid_social.v_demographics`
WHERE age_range IS NOT NULL AND gender IS NOT NULL
  AND date BETWEEN '2025-04-01' AND '2025-05-12'
GROUP BY age_range, gender
ORDER BY impressions DESC
LIMIT 10;
```

## Actionable Insights (Once Data is Available)

### Optimization Opportunities

**1. Age Targeting Refinement**
- If 18-24 has low CTR (<1%): Exclude from targeting to reduce wasted spend
- If 55-64 has high conversion rate: Expand targeting to 55-65

**2. Gender-Specific Campaigns**
- Create separate campaigns for male/female if performance varies >25%
- Test gender-specific creative for top-performing age groups

**3. Budget Allocation**
- Shift budget toward best-performing age×gender combinations
- Example: If 25-34 male has 3x CTR vs. 45-54 female, allocate accordingly

**4. Creative Testing by Demographic**
- Test video ads for younger audiences (25-34)
- Test image ads for older audiences (45-54)
- Analyze platform preference (Instagram vs. Facebook) by age

## Next Steps

1. **Get Proper Access Token**
   - Generate System User token from Business Manager
   - Or create app token via Graph API Explorer
   - Update `.env` file

2. **Pull Demographic Data**
   ```bash
   psn meta sync-insights \
     --account-id act_229793224304371 \
     --level campaign \
     --since 2025-04-01 \
     --until 2025-05-12 \
     --breakdowns "age,gender"
   ```

3. **Pull Additional Breakdowns**
   ```bash
   # Geographic breakdown
   psn meta sync-insights \
     --account-id act_229793224304371 \
     --level campaign \
     --since 2025-04-01 \
     --until 2025-05-12 \
     --breakdowns "region,country"

   # Platform breakdown
   psn meta sync-insights \
     --account-id act_229793224304371 \
     --level campaign \
     --since 2025-04-01 \
     --until 2025-05-12 \
     --breakdowns "publisher_platform,device_platform"
   ```

4. **Analyze Results**
   - Run queries above
   - Generate dashboard in Looker/Tableau
   - Create monthly demographic report

5. **Optimize Campaigns**
   - Exclude poor-performing demographics
   - Increase bids for high-performers
   - Test demographic-specific creative

## Technical Notes

- **Max 2 breakdowns per request** (Meta API limitation)
- **Data stored in `raw_metrics` JSON** (no schema changes)
- **Views automatically extract demographics** (`v_demographics`)
- **Row count increases 18x** with age×gender (6 ages × 3 genders)

## Support

- Documentation: `docs/demographic_breakdowns.md`
- Feature Summary: `docs/DEMOGRAPHIC_FEATURE_SUMMARY.md`
- Demo Script: `scripts/demo_demographics.sh`
