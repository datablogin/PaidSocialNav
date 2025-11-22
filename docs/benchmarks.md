# Benchmarks Feature Guide

## Overview

The benchmarks feature (Issue #16) enables you to compare your campaign performance against industry benchmarks. This provides context for audit scores and helps identify whether your performance is above or below industry standards.

## Key Components

### 1. Benchmarks Table

**Table**: `benchmarks_performance`

**Schema**:
- `industry` (STRING, REQUIRED): Industry vertical (e.g., "retail", "finance", "healthcare")
- `region` (STRING, REQUIRED): Geographic region (e.g., "US", "EU", "GLOBAL")
- `spend_band` (STRING, REQUIRED): Spend tier (e.g., "0-10k", "10k-50k", "50k+")
- `metric_name` (STRING, REQUIRED): Metric identifier (e.g., "ctr", "frequency", "conv_rate", "cpc", "cpm")
- `p25` (FLOAT64, NULLABLE): 25th percentile value
- `p50` (FLOAT64, NULLABLE): 50th percentile (median) value
- `p75` (FLOAT64, NULLABLE): 75th percentile value
- `p90` (FLOAT64, NULLABLE): 90th percentile value

### 2. Seed Data

**File**: `data/benchmarks_performance.csv`

The seed CSV contains realistic benchmark data for the retail industry across different regions and spend bands. Currently includes:

- **Industry**: retail
- **Regions**: US, GLOBAL
- **Spend Bands**: 0-10k, 10k-50k, 50k+
- **Metrics**: ctr, frequency, conv_rate, cpc, cpm

### 3. Audit Configuration

To enable benchmark comparisons, add these fields to your audit config YAML:

```yaml
# Benchmark mapping for performance comparison
industry: retail
region: US
spend_band: 10k-50k

# Add benchmark rule to weights
weights:
  performance_vs_benchmarks: 1.0  # Performance vs industry benchmarks
```

**Fields**:
- `industry`: Your business vertical (must match a value in benchmarks table)
- `region`: Your primary market region (must match a value in benchmarks table)
- `spend_band`: Your approximate monthly ad spend tier (must match a value in benchmarks table)

### 4. Benchmark Rule

**Rule**: `performance_vs_benchmarks`

This rule compares your actual metrics against industry benchmarks and scores based on:
- How many metrics meet or exceed the p50 (median) benchmark
- The percentile tier for each metric (p90+, p75-p90, p50-p75, p25-p50, below p25)

**Score Calculation**:
- Score = (metrics_above_p50 / total_metrics) × 100
- Where metrics_above_p50 includes metrics at or above the median benchmark

## Usage

### Step 1: Load Benchmark Data

Load the seed CSV into BigQuery:

```python
from paid_social_nav.storage.bq import load_benchmarks_csv

rows_loaded = load_benchmarks_csv(
    project_id="your-project",
    dataset="paid_social",
    csv_path="data/benchmarks_performance.csv"
)
print(f"Loaded {rows_loaded} benchmark rows")
```

Or use the test script:
```bash
python test_benchmarks.py
```

### Step 2: Configure Your Audit

Update your audit config YAML (e.g., `configs/audit_puttery.yaml`):

```yaml
project: your-project-id
dataset: paid_social
tenant: your_tenant
level: campaign

# Benchmark mapping
industry: retail
region: US
spend_band: 10k-50k

weights:
  budget_concentration: 1.0
  creative_diversity: 1.0
  ctr_threshold: 1.0
  frequency_threshold: 1.0
  tracking_health: 1.0
  performance_vs_benchmarks: 1.0  # Enable benchmark comparisons
```

### Step 3: Run Audit

```bash
psn audit run --config configs/audit_puttery.yaml
```

### Step 4: Review Results

The audit output will include benchmark comparisons showing:

```
Performance vs Benchmarks (window=Q2):
  Score: 66.67
  Metrics Above P50: 2/3

  Metric Comparisons:
    ctr:
      Actual: 0.0160
      Benchmark P50: 0.0150
      Tier: p50-p75
      vs Benchmark: ABOVE

    frequency:
      Actual: 2.0000
      Benchmark P50: 2.3000
      Tier: p25-p50
      vs Benchmark: BELOW

    conv_rate:
      Actual: 0.0180
      Benchmark P50: 0.0150
      Tier: p75-p90
      vs Benchmark: ABOVE
```

## Metric Definitions

### Supported Metrics

1. **CTR (Click-Through Rate)**: clicks / impressions
2. **Frequency**: impressions / reach (average times a user sees an ad)
3. **Conversion Rate**: conversions / clicks
4. **CPC (Cost Per Click)**: spend / clicks
5. **CPM (Cost Per Mille)**: (spend / impressions) × 1000

### Percentile Tiers

- **p90+**: Top 10% performance (excellent)
- **p75-p90**: Top 25% performance (good)
- **p50-p75**: Above average performance (decent)
- **p25-p50**: Below average performance (needs improvement)
- **below p25**: Bottom 25% performance (poor)

## Adding New Benchmarks

To add benchmarks for a new industry, region, or spend band:

1. **Edit the CSV**: Add rows to `data/benchmarks_performance.csv`

```csv
industry,region,spend_band,metric_name,p25,p50,p75,p90
finance,US,10k-50k,ctr,0.007,0.011,0.016,0.023
finance,US,10k-50k,frequency,1.6,2.1,2.8,3.5
```

2. **Reload Data**: Run the load function to refresh the benchmarks table

```python
from paid_social_nav.storage.bq import load_benchmarks_csv

load_benchmarks_csv(
    project_id="your-project",
    dataset="paid_social",
    csv_path="data/benchmarks_performance.csv"
)
```

3. **Update Config**: Point your audit config to the new benchmark mapping

```yaml
industry: finance
region: US
spend_band: 10k-50k
```

## Benchmarks Unavailable

If no benchmarks are found for your industry/region/spend_band combination:
- The rule will return a neutral score of 50.0
- The findings will show `"benchmarks_available": false`
- No performance comparisons will be displayed

This allows the audit to run without failing, even if benchmarks aren't configured.

## Testing

A comprehensive test suite is available in `test_benchmarks.py`:

```bash
python test_benchmarks.py
```

This tests:
1. Loading benchmark CSV data into BigQuery
2. Running audit with benchmark comparisons
3. Unit testing the benchmark rule logic

## API Reference

### Storage Functions

```python
# Create benchmarks table
from paid_social_nav.storage.bq import ensure_benchmarks_table
ensure_benchmarks_table(project_id="project", dataset="dataset")

# Load benchmarks from CSV
from paid_social_nav.storage.bq import load_benchmarks_csv
rows = load_benchmarks_csv(
    project_id="project",
    dataset="dataset",
    csv_path="path/to/benchmarks.csv"
)
```

### Audit Rule

```python
from paid_social_nav.audit.rules import performance_vs_benchmarks

result = performance_vs_benchmarks(
    actual_metrics={"ctr": 0.016, "frequency": 2.0},
    benchmarks={
        "ctr": {"p25": 0.01, "p50": 0.015, "p75": 0.022, "p90": 0.03},
        "frequency": {"p25": 1.8, "p50": 2.3, "p75": 3.0, "p90": 3.8}
    },
    level="campaign",
    window="Q2"
)
```

## Troubleshooting

### "Benchmarks not available for this configuration"

**Cause**: No matching rows in benchmarks table for your industry/region/spend_band.

**Solution**:
1. Check your audit config values match exactly what's in the CSV
2. Verify the CSV has been loaded: `SELECT * FROM benchmarks_performance LIMIT 10`
3. Add missing benchmarks to the CSV and reload

### "Table not found: benchmarks_performance"

**Cause**: The benchmarks table hasn't been created.

**Solution**: Run the loader function which creates the table automatically:
```python
from paid_social_nav.storage.bq import load_benchmarks_csv
load_benchmarks_csv(project_id="...", dataset="...", csv_path="...")
```

### Benchmark rule not appearing in results

**Cause**: Missing one or more of: industry, region, spend_band in config.

**Solution**: Ensure all three benchmark mapping fields are set in your YAML config.
