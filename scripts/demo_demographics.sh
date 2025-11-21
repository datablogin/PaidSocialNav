#!/bin/bash
# Demo script showing how to pull and analyze demographic data for Puttery Golf

set -e

echo "================================================"
echo "Demographic Breakdowns Demo for Puttery Golf"
echo "================================================"
echo ""

# Check for access token
if [ -z "$PSN_META_ACCESS_TOKEN" ]; then
  echo "❌ ERROR: PSN_META_ACCESS_TOKEN environment variable not set"
  echo "Please set it with: export PSN_META_ACCESS_TOKEN='your-token-here'"
  exit 1
fi

echo "✓ Access token found"
echo ""

# Account details
ACCOUNT_ID="act_229793224304371"
PROJECT_ID="puttery-golf-001"
DATASET="paid_social"

echo "Account: $ACCOUNT_ID"
echo "Project: $PROJECT_ID"
echo "Dataset: $DATASET"
echo ""

# Step 1: Pull demographic data with age and gender breakdowns
echo "================================================"
echo "Step 1: Pulling demographic data (age, gender)"
echo "================================================"
echo ""
echo "Command:"
echo "psn meta sync-insights \\"
echo "  --account-id $ACCOUNT_ID \\"
echo "  --level campaign \\"
echo "  --date-preset last_30d \\"
echo "  --breakdowns 'age,gender' \\"
echo "  --log-level INFO"
echo ""
read -p "Press Enter to execute this command..."

python3 -m paid_social_nav.cli.main meta sync-insights \
  --account-id "$ACCOUNT_ID" \
  --level campaign \
  --date-preset last_30d \
  --breakdowns "age,gender" \
  --log-level INFO

echo ""
echo "✓ Demographic data pulled successfully"
echo ""

# Step 2: Create demographic views
echo "================================================"
echo "Step 2: Creating demographic analysis views"
echo "================================================"
echo ""
echo "Creating v_demographics view..."

bq query --project_id="$PROJECT_ID" --use_legacy_sql=false < sql/views/v_demographics.sql

echo ""
echo "Creating v_demographic_summary view..."

bq query --project_id="$PROJECT_ID" --use_legacy_sql=false < sql/views/v_demographic_summary.sql

echo ""
echo "✓ Views created successfully"
echo ""

# Step 3: Run analysis queries
echo "================================================"
echo "Step 3: Analyzing demographic data"
echo "================================================"
echo ""

echo "Query 1: Age breakdown"
echo "----------------------"
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=prettyjson "
SELECT
  age_range,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(AVG(ctr_pct), 2) as avg_ctr,
  ROUND(SUM(spend), 2) as spend,
  ROUND(SUM(impressions) / SUM(SUM(impressions)) OVER () * 100, 1) AS pct_of_total
FROM \`$PROJECT_ID.$DATASET.v_demographics\`
WHERE age_range IS NOT NULL
GROUP BY age_range
ORDER BY impressions DESC
"

echo ""
echo "Query 2: Gender breakdown"
echo "-------------------------"
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=prettyjson "
SELECT
  gender,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(AVG(ctr_pct), 2) as avg_ctr,
  ROUND(SUM(spend), 2) as spend,
  ROUND(SUM(impressions) / SUM(SUM(impressions)) OVER () * 100, 1) AS pct_of_total
FROM \`$PROJECT_ID.$DATASET.v_demographics\`
WHERE gender IS NOT NULL
GROUP BY gender
ORDER BY impressions DESC
"

echo ""
echo "Query 3: Age x Gender matrix"
echo "-----------------------------"
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=prettyjson "
SELECT
  age_range,
  gender,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  ROUND(AVG(ctr_pct), 2) as ctr_pct,
  ROUND(SUM(spend), 2) as spend
FROM \`$PROJECT_ID.$DATASET.v_demographics\`
WHERE age_range IS NOT NULL AND gender IS NOT NULL
GROUP BY age_range, gender
ORDER BY impressions DESC
LIMIT 10
"

echo ""
echo "================================================"
echo "Demo Complete!"
echo "================================================"
echo ""
echo "Summary:"
echo "--------"
echo "✓ Pulled demographic data with age and gender breakdowns"
echo "✓ Created demographic analysis views in BigQuery"
echo "✓ Ran sample queries showing who actually saw the ads"
echo ""
echo "Next steps:"
echo "- Review the documentation: docs/demographic_breakdowns.md"
echo "- Pull additional breakdowns (region, platform)"
echo "- Compare targeting settings vs actual delivery"
echo "- Build demographic dashboards in your BI tool"
echo ""
