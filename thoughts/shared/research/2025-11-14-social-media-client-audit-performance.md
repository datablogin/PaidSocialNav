---
date: 2025-11-14T02:04:28Z
researcher: Claude
git_commit: 68a4dc96e8250a467c004ee385ea27514e895de5
branch: feature/issue-20-fallback-multilevel-chunking
repository: PaidSocialNav
topic: "Social Media Client Audit Checklist and Performance Improvement Strategies"
tags: [research, codebase, audit, performance, meta-adapter, bigquery, testing, monitoring]
status: complete
last_updated: 2025-11-14
last_updated_by: Claude
---

# Research: Social Media Client Audit Checklist and Performance Improvement Strategies

**Date**: 2025-11-14T02:04:28Z
**Researcher**: Claude
**Git Commit**: 68a4dc96e8250a467c004ee385ea27514e895de5
**Branch**: feature/issue-20-fallback-multilevel-chunking
**Repository**: PaidSocialNav

## Research Question

Review README.md and codebase to determine:
1. What should be considered to fully audit a new social media client
2. How to improve social media performance

## Summary

The PaidSocialNav codebase implements a comprehensive paid social advertising data pipeline focused on Meta platforms (Facebook, Instagram, WhatsApp). The system provides a complete audit framework with 6 performance rules, multi-tenant BigQuery data warehousing with MERGE-based deduplication, and configurable data fetching with chunking, rate limiting, and retry logic. The architecture supports multi-level hierarchy (account/campaign/adset/ad) with automatic fallback, pre-aggregated views across 10 time windows, and weighted scoring for performance evaluation.

For auditing new clients, the system evaluates: platform integration & API access, data collection quality, configuration setup, performance metrics across 6 dimensions, data storage integrity, and testing validation. For improving performance, it offers: data fetching optimization, multi-level fallback strategies, weighted audit scoring, BigQuery query optimization, and monitoring patterns.

## Detailed Findings

### Component 1: Platform Integration & API Access

**Current Implementation**

The Meta adapter (`paid_social_nav/adapters/meta/adapter.py:25-154`) provides the foundation for all platform integrations:

- **MetaAdapter Class** (`adapter.py:25-30`): Uses Graph API v18.0 with access token-based authentication
- **Authentication** (`adapter.py:28-29`): Token stored as instance variable, passed as query parameter in all requests
- **Token Sourcing**:
  - Environment variables: `PSN_META_ACCESS_TOKEN` with fallback to `META_ACCESS_TOKEN` (`config.py:62-73`)
  - GCP Secret Manager integration (`storage/secrets.py:4-12`, `cli/main.py:119-139`)
  - `.env` file parsing with PSN_ prefix support (`config.py:15-38`)

- **Data Model** (`adapter.py:12-23`): `InsightRecord` dataclass contains:
  - `date`, `level`, `impressions`, `clicks`, `spend`, `conversions`
  - `ctr`, `frequency`, `raw` (complete API response)

**Audit Points for New Clients:**
1. Verify access token validity and secure storage (environment or Secret Manager)
2. Confirm account IDs follow platform format (`act_` prefix for Meta - `sync.py:22-23`)
3. Test API connectivity with appropriate API version
4. Validate pagination handling (default 500 rows per page - `adapter.py:38`)
5. Check error response parsing (`adapter.py:88-93`)

**Code References:**
- `paid_social_nav/adapters/meta/adapter.py:25` - MetaAdapter class
- `paid_social_nav/core/config.py:62` - get_settings() for env vars
- `paid_social_nav/storage/secrets.py:4` - access_secret() for GCP Secret Manager
- `paid_social_nav/cli/main.py:119` - CLI integration with Secret Manager

### Component 2: Data Collection & Quality

**Metrics Tracked**

The system collects 13 fields per insight record (`storage/bq.py:62-82`):

**Schema for `fct_ad_insights_daily`:**
```
date                 DATE       - Fact date dimension
level                STRING     - Hierarchy level: 'ad', 'adset', or 'campaign'
account_global_id    STRING     - Platform-qualified account ID
campaign_global_id   STRING     - Platform-qualified campaign ID (nullable)
adset_global_id      STRING     - Platform-qualified ad set ID (nullable)
ad_global_id         STRING     - Platform-qualified ad ID (nullable)
impressions          INT64      - Total impressions
clicks               INT64      - Total clicks
spend                FLOAT64    - Total spend in account currency
conversions          FLOAT64    - Total conversions
ctr                  FLOAT64    - Click-through rate
frequency            FLOAT64    - Frequency metric
raw_metrics          JSON       - Full API response for extensibility
```

**Data Transformation** (`sync.py:179-198`):
- Global IDs prefixed with platform namespace: `"meta:account:{act}"`, `"meta:campaign:{campaign_id}"`
- Date converted to ISO format: `ir.date.isoformat()`
- Complete raw API response preserved in `raw_metrics` field

**Quality Controls:**

1. **Account ID Normalization** (`sync.py:22-23`):
   ```python
   def _norm_act(account_id: str) -> str:
       return account_id if account_id.startswith("act_") else f"act_{account_id}"
   ```

2. **Date Validation** (`cli/main.py:149-168`):
   - ISO format validation (YYYY-MM-DD)
   - Logical validation (since not after until)
   - Precedence warnings when both preset and explicit dates provided

3. **NULL Handling in BigQuery**:
   - All views use `SAFE_DIVIDE()` to prevent division by zero
   - `NULLIF(denominator, 0)` prevents invalid calculations
   - Explicit type casting in views (`sql/views/insights_rollups.sql:12-21`)

4. **Deduplication** (`storage/bq.py:137-161`):
   - MERGE statement with composite natural key
   - Key fields: date + level + account_global_id + campaign_global_id + adset_global_id + ad_global_id
   - `IFNULL(field, '')` treats NULL as empty string for matching

**Audit Points:**
- Verify all required fields are populated (no unexpected NULLs)
- Check for data gaps in expected date ranges
- Validate metric totals match platform reporting UI
- Confirm raw API responses stored for future metric extraction
- Test deduplication by re-running same date range

**Code References:**
- `paid_social_nav/storage/bq.py:62` - ensure_insights_table() schema definition
- `paid_social_nav/core/sync.py:179` - Row transformation logic
- `paid_social_nav/storage/bq.py:137` - MERGE-based deduplication
- `sql/views/insights_rollups.sql:68` - SAFE_DIVIDE usage

### Component 3: Multi-Tenant Configuration

**Tenant System** (`core/tenants.py:27-40`):

Loads from `configs/tenants.yaml`:
```yaml
tenants:
  fleming:
    project_id: fleming-424413
    dataset: paid_social
    default_level: ad
```

**Configuration Precedence** (`cli/main.py:93-117`):
1. CLI flags (`--project`, `--dataset`, `--level`)
2. Tenant configuration (`--tenant` flag)
3. Environment variables (`PSN_GCP_PROJECT_ID`, `PSN_BQ_DATASET`)
4. Defaults

**Environment Variable Resolution** (`config.py:62-73`):
- Supports PSN_ prefixed variables with fallback to unprefixed
- Priority: process environment → `.env` file → fallback names
- Example: `PSN_META_ACCESS_TOKEN` or `META_ACCESS_TOKEN`

**Audit Points:**
1. Tenant configuration exists in `configs/tenants.yaml`
2. GCP project has proper IAM permissions:
   - BigQuery Data Editor (for table creation/loading)
   - BigQuery Job User (for query execution)
   - Secret Manager Secret Accessor (if using Secret Manager)
3. Dataset and table structures exist or can be created
4. Default level appropriate for use case (ad vs campaign granularity)
5. Environment variables use PSN_ prefix convention

**Code References:**
- `paid_social_nav/core/tenants.py:27` - get_tenant() function
- `configs/tenants.yaml` - Tenant configuration data
- `paid_social_nav/core/config.py:15` - Environment variable parsing
- `paid_social_nav/cli/main.py:93` - Configuration resolution logic

### Component 4: Performance Audit System

**Architecture** (`audit/engine.py:43-307`):

The `AuditEngine` class implements a weighted scoring system:
1. Fetches base KPI data via `_fetch_kpis()` (`engine.py:197-213`)
2. Evaluates each enabled rule (weight > 0)
3. Calculates rule scores (0-100 scale)
4. Computes weighted average as overall score
5. Returns structured results with per-rule findings

**Six Audit Rules** (`audit/rules.py`):

**Rule 1: Pacing vs Target** (`rules.py:45-87`)
- **Purpose**: Validates spend pacing against budget targets
- **Parameters**:
  - `actual_spend`: From `v_budget_pacing` view
  - `target_spend`: From optional plan table or config
  - `tolerance`: Default 0.1 (10% acceptable deviation)
  - `tol_cap`: Default 0.5 (50% max deviation)
- **Scoring Logic**:
  - If target ≤ 0: returns 100 if actual also ≤ 0, else 0
  - Calculates ratio: `actual_spend / target_spend`
  - Within tolerance: score = 100
  - Outside tolerance: linear penalty based on excess, capped by `tol_cap`
- **Invoked**: `engine.py:66-85` for each configured window

**Rule 2: CTR Threshold** (`rules.py:90-103`)
- **Purpose**: Ensures click-through rate meets minimum performance
- **Parameters**:
  - `ctr`: Average CTR from KPIs (`engine.py:93-101`)
  - `min_ctr`: Default 0.01 (1%)
- **Scoring**: Uses `_score_linear_ok_above()` helper
  - Returns 100 if ctr ≥ min_ctr
  - Otherwise: `100 * (ctr / min_ctr)` clamped to [0, 100]
- **Invoked**: `engine.py:104-114`

**Rule 3: Frequency Threshold** (`rules.py:106-120`)
- **Purpose**: Prevents ad fatigue by monitoring frequency
- **Parameters**:
  - `frequency`: Average frequency from KPIs (`engine.py:98-102`)
  - `max_frequency`: Default 2.5
  - `overage_cap`: Default 1.0 (100% overage allowed)
- **Scoring**: Uses `_score_linear_ok_below()` helper
  - Returns 100 if frequency ≤ max_frequency
  - Otherwise: `100 * (1.0 - ((actual - max) / (max * overage_cap)))`
- **Invoked**: `engine.py:116-131`

**Rule 4: Budget Concentration** (`rules.py:123-143`)
- **Purpose**: Identifies over-reliance on top-performing entities
- **Parameters**:
  - `top_n_cum_share`: Cumulative share of top-N entities
  - `max_share`: Default 0.7 (70%)
  - `top_n`: Configurable (e.g., top 3 campaigns)
- **Scoring**:
  - If cumulative share ≤ max_share: 100
  - Otherwise: linear penalty based on overage
- **Data Source**: `v_budget_concentration` view (referenced but SQL not in repo)
- **Invoked**: `engine.py:134-148` when `top_n` config present

**Rule 5: Creative Diversity** (`rules.py:146-171`)
- **Purpose**: Validates mix of video vs image creative content
- **Parameters**:
  - `video_share`: From `v_creative_mix` view
  - `image_share`: From `v_creative_mix` view
  - `min_video_share`: Default 0.2 (20%)
  - `min_image_share`: Default 0.2 (20%)
- **Scoring**:
  - Calculates shortfall as max of video or image deficiency
  - `score = 100 * (1.0 - clamp(shortfall / 1.0))`
- **Data Source**: `sql/views/v_creative_mix.sql`
- **Invoked**: `engine.py:151-169`

**Rule 6: Tracking Health** (`rules.py:174-202`)
- **Purpose**: Verifies conversion tracking implementation
- **Parameters**:
  - `conversions_present`: Boolean flag
  - `conv_rate`: Conversion rate
  - `min_conv_rate`: Default 0.01 (1%)
  - `min_clicks`: Default 100 (minimum sample size)
  - `clicks`: Total clicks
- **Scoring** (three-tier logic):
  1. If conversions exist: 100
  2. If no conversions but sufficient clicks and positive conv_rate: score based on meeting minimum
  3. Otherwise: 0
- **Invoked**: `engine.py:172-189`

**Configuration Structure** (`engine.py:16-25`):

```yaml
project: fleming-424413
dataset: paid_social
tenant: fleming
windows: [last_7d, last_28d, MTD, Q2]
level: campaign
weights:
  pacing_vs_target: 2.0
  ctr_threshold: 1.5
  frequency_threshold: 1.0
  budget_concentration: 1.0
  creative_diversity: 1.0
  tracking_health: 2.0
thresholds:
  min_ctr: 0.01
  max_frequency: 2.5
  pacing_tolerance: 0.1
  pacing_tol_cap: 0.5
  max_topn_share: 0.7
  min_video_share: 0.2
  min_image_share: 0.2
  min_conv_rate: 0.01
  min_clicks_for_tracking: 100
top_n: 3
```

**Weighted Scoring** (`engine.py:58-195`):
- Each rule score multiplied by weight
- Accumulated: `weighted_sum` and `weight_total`
- Overall score: `weighted_sum / max(weight_total, 1e-9)`
- Returns 0.0 if total weights ≤ 0

**Audit Points:**
1. Review default thresholds against client industry benchmarks
2. Adjust weights to prioritize critical performance areas
3. Configure appropriate time windows for business cycle
4. Set `top_n` based on account structure complexity
5. Validate BigQuery views exist and return data
6. Run audit after initial data load to baseline performance

**Code References:**
- `paid_social_nav/audit/engine.py:34` - run_audit() entry point
- `paid_social_nav/audit/rules.py:45` - All 6 rule implementations
- `paid_social_nav/cli/main.py:214` - audit_run() CLI command
- `sql/views/v_creative_mix.sql` - Creative diversity data source

### Component 5: BigQuery Data Warehouse

**Storage Architecture**

**Primary Fact Table** (`storage/bq.py:62-82`):
- Table: `fct_ad_insights_daily`
- 13 fields with explicit types
- No explicit primary key (relies on MERGE uniqueness)
- JSON field preserves original API response

**Staging Pattern** (`storage/bq.py:88-161`):
1. **Staging Table** (`__stg_fct_ad_insights_daily`): Identical schema, temporary holding area
2. **Load to Staging** (`bq.py:122-135`): NDJSON format via `load_table_from_file()`
3. **MERGE Operation** (`bq.py:137-158`): Deduplicates into fact table
4. **Cleanup** (`bq.py:161`): Truncates staging table

**Composite Natural Key** (`bq.py:142-147`):
```sql
ON T.date = S.date
   AND T.level = S.level
   AND IFNULL(T.account_global_id, '') = IFNULL(S.account_global_id, '')
   AND IFNULL(T.campaign_global_id, '') = IFNULL(S.campaign_global_id, '')
   AND IFNULL(T.adset_global_id, '') = IFNULL(S.adset_global_id, '')
   AND IFNULL(T.ad_global_id, '') = IFNULL(S.ad_global_id, '')
```

**Update vs Insert Behavior**:
- **WHEN MATCHED**: Updates all metric fields with latest values
- **WHEN NOT MATCHED**: Inserts entire row from staging
- Last write wins for metric values
- Supports backfill and incremental loads idempotently

**SQL Views** (analytics layer):

**View 1: insights_rollups** (`sql/views/insights_rollups.sql`)
- **Purpose**: Pre-aggregated metrics across 10 time windows
- **Architecture**:
  - `params` CTE: Computes date anchors (lines 2-9)
  - `base` CTE: Type-casts and aliases fact table (lines 10-23)
  - `windows` CTE: Defines 10 time windows (lines 24-35)
  - `rolled` CTE: Cross joins facts × windows, aggregates (lines 36-57)
  - Final SELECT: Computes CTR and CPA via SAFE_DIVIDE (lines 58-72)
- **Time Windows**:
  - Rolling: last_7d, last_28d, last_90d
  - Period-to-date: MTD, YTD
  - Quarters: last_quarter, Q1, Q2, Q3, Q4
- **Grain**: One row per (level, platform, window, account_id, campaign_id, adset_id, ad_id)

**View 2: v_creative_mix** (`sql/views/v_creative_mix.sql`)
- **Purpose**: Calculate video vs image impression share
- **Architecture**:
  - `fact` CTE: Filters to ad-level only (line 31)
  - `with_media` CTE: Left joins `dim_ad` dimension for media_type (lines 33-40)
  - `rolled` CTE: Aggregates by window and level (lines 41-52)
  - Final SELECT: Calculates video_share and image_share (lines 53-58)
- **Grain**: One row per (level, window)

**View 3: v_budget_pacing** (`sql/views/v_budget_pacing.sql`)
- **Purpose**: Total spend per level and window
- **Architecture**: Simple aggregation from `insights_rollups`
- **Grain**: One row per (level, window)

**View 4: v_structure_split** (`sql/views/v_structure_split.sql`)
- **Purpose**: Entity counts and spend totals
- **Architecture**:
  - Uses `COALESCE()` to pick first non-null ID based on hierarchy (line 5)
  - Counts distinct entities at appropriate level
- **Grain**: One row per (level, window)

**Audit Points:**
1. Table exists: `{project}.{dataset}.fct_ad_insights_daily`
2. Row counts match expected: query for date range and compare to API expectations
3. No duplicate rows: verify MERGE worked by checking for duplicate keys
4. Views accessible: test queries against all 4 views
5. Computed metrics correct: validate CTR = clicks/impressions, CPA = spend/conversions
6. Time windows aligned: verify window boundaries match business expectations
7. Staging table empty: confirms cleanup ran successfully

**Code References:**
- `paid_social_nav/storage/bq.py:62` - ensure_insights_table()
- `paid_social_nav/storage/bq.py:110` - load_json_rows()
- `paid_social_nav/storage/bq.py:137` - MERGE statement
- `sql/views/insights_rollups.sql` - Base aggregation view
- `sql/views/v_creative_mix.sql` - Creative diversity view

### Component 6: Data Fetching & Performance Optimization

**Orchestration Layer** (`sync.py:101-249`):

The `sync_meta_insights()` function implements comprehensive orchestration:

**Date Handling** (`sync.py:62-85`):

1. **Resolution Function** (`_resolve_dates`):
   - Explicit dates take precedence over presets
   - Validates both since and until provided together
   - Defaults to yesterday if nothing specified

2. **Preset Conversion** (`_preset_to_range` at `sync.py:32-59`):
   - Converts named presets to date ranges
   - Supports: YESTERDAY, LAST_7D, LAST_14D, LAST_28D, LAST_30D, LAST_90D
   - Returns None for LIFETIME (handled by adapter)
   - Uses UTC timezone: `datetime.now(UTC)`

3. **Precedence Warning** (`cli/main.py:141-146`):
   ```python
   if date_preset and (since or until):
       typer.secho(
           "Warning: --date-preset provided together with --since/--until; "
           "explicit dates will be used.",
           fg=typer.colors.YELLOW,
       )
   ```

**Chunking Logic** (`sync.py:88-99`):

```python
def _chunks(dr: DateRange, *, chunk_days: int) -> Iterable[DateRange]:
    total_days = (dr.until - dr.since).days + 1
    if total_days <= 60:
        yield dr
        return
    step = timedelta(days=chunk_days)
    cursor = dr.since
    while cursor <= dr.until:
        end = min(cursor + step - timedelta(days=1), dr.until)
        yield DateRange(since=cursor, until=end)
        cursor = end + timedelta(days=1)
```

- Ranges ≤60 days: no chunking
- Ranges >60 days: split into `chunk_days` chunks (default 30)
- Generator pattern for memory efficiency

**Rate Limiting** (`sync.py:132-151`):

```python
min_interval = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 0.0
last_time: float | None = None

def _maybe_sleep() -> None:
    nonlocal last_time
    if min_interval <= 0:
        return
    now = _t.time()
    if last_time is None:
        last_time = now
        return
    elapsed = now - last_time
    if elapsed < min_interval:
        sleep(min_interval - elapsed)
    last_time = _t.time()
```

- Configurable requests-per-second: `--rate-limit-rps` flag
- Default 0.0 (disabled)
- Calculates minimum interval between requests
- Sleeps to maintain rate limit

**Retry Logic** (`sync.py:162-215`):

```python
for chunk in dr_iter:
    attempt = 0
    while True:
        try:
            _maybe_sleep()
            for ir in adapter.fetch_insights(...):
                # ... processing
            # ... loading
            break
        except Exception:
            attempt += 1
            if attempt > retries:
                raise
            sleep(retry_backoff)
```

- Default: 3 retries with 2.0s backoff
- Retries entire chunk on failure
- Exponential backoff configurable
- Re-raises after exhausting retries

**Multi-Level Support** (`sync.py:220-248`):

**Explicit Levels** (lines 220-226):
- `--levels ad,adset,campaign` runs sequentially
- No fallback between levels
- Accumulates all rows from all levels

**Single Level with Fallback** (lines 227-248):
- `FALLBACK_ORDER = [Entity.AD, Entity.ADSET, Entity.CAMPAIGN]` (line 19)
- Attempts ad-level first (most granular)
- Falls back to adset if ad fails (controlled by `--fallback-levels` flag)
- Falls back to campaign if both fail
- Default: `--fallback-levels` enabled
- Disable with `--no-fallback-levels` flag

**Tenant Default Level** (`cli/main.py:93-117`, `configs/tenants.yaml`):
- Resolution order: `--levels` (if provided) → `--level` (if provided) → tenant `default_level` → `ad`
- Allows per-tenant granularity preferences

**Performance Optimization Strategies:**

1. **Adjust Page Size** (`--page-size`):
   - Default: 500 rows per page
   - Increase for faster networks/APIs
   - Decrease if encountering timeouts

2. **Configure Rate Limiting** (`--rate-limit-rps`):
   - Set based on platform rate limits
   - Meta: typically allows ~200 requests/hour
   - Calculate: 200/3600 ≈ 0.055 RPS

3. **Optimize Chunk Size** (`--chunk-days`):
   - Default: 30 days
   - Smaller chunks: more frequent BigQuery loads, better progress visibility
   - Larger chunks: fewer API requests, lower overhead

4. **Choose Appropriate Level**:
   - Campaign: fastest, least granular
   - Adset: medium performance
   - Ad: slowest, most detailed
   - Use tenant default_level to avoid specifying each time

5. **Leverage Fallback**:
   - Enable for comprehensive data collection
   - Disable (`--no-fallback-levels`) for faster targeted fetches

**Code References:**
- `paid_social_nav/core/sync.py:101` - sync_meta_insights() orchestration
- `paid_social_nav/core/sync.py:88` - _chunks() chunking logic
- `paid_social_nav/core/sync.py:132` - Rate limiting implementation
- `paid_social_nav/core/sync.py:162` - Retry logic
- `paid_social_nav/cli/main.py:25` - CLI parameter definitions

### Component 7: Testing & Quality Assurance

**Test Structure**

Total: 8 tests (5 unit, 3 integration)

**Test Files:**
- `tests/test_insights_cli.py` - 5 CLI validation unit tests
- `tests/integration/test_meta_e2e.py` - 1 end-to-end integration test
- `tests/integration/test_bq_views.py` - 2 BigQuery view integration tests

**Unit Testing Approach** (`tests/test_insights_cli.py`):

All tests use pytest's `monkeypatch` fixture (no unittest.mock):

**Test 1: Invalid Date Format** (lines 8-30)
- Patches `get_settings` with `DummySettings` stub
- Uses `CliRunner` from typer.testing
- Invokes CLI with invalid date "2025-13-01"
- Asserts non-zero exit code and "YYYY-MM-DD" in error message

**Test 2: Tenant Not Found** (lines 33-52)
- Patches `get_settings`
- Invokes CLI with tenant "missing"
- Asserts "not found" in error message

**Test 3: Secret Retrieval Failure** (lines 55-85)
- Defines `NoTokenSettings` with `meta_access_token = None`
- Patches both `get_settings` and `access_secret` (raises RuntimeError)
- Asserts "Failed to read secret" message

**Test 4: Conflicting Flags** (lines 94-128)
- Creates inline `fake_sync` function that captures kwargs
- Patches `sync_meta_insights`
- Invokes CLI with both `--date-preset yesterday` and explicit dates
- Asserts warning message and date precedence

**Test 5: Defaults to Yesterday** (lines 131-169)
- Uses `fake_sync` to capture parameters
- Invokes CLI without date parameters
- Asserts `date_preset`, `since`, and `until` are all None
- Verifies `page_size` parameter passed through

**Integration Testing Approach**:

**Environment Gating**:
- All integration tests require `PSN_INTEGRATION=1`
- Meta e2e test also requires `PSN_META_ACCOUNT_ID`
- Skip tests if conditions not met

**Test: Meta E2E** (`test_meta_e2e.py:47-107`):
1. Loads `.env` file via custom `_load_dotenv` function (lines 11-28)
2. Retrieves real token from environment
3. Invokes CLI with real Meta account for date range 2025-04-29 to 2025-05-31
4. Parses stdout for "Loaded (\d+) rows" using regex
5. Validates BigQuery data using `bq query` subprocess
6. Asserts row count > 0

**Test: Rollups Q2 Has Rows** (`test_bq_views.py:15-32`):
- Queries `insights_rollups` with `WHERE window='Q2'`
- Uses `bq query --format=csv`
- Asserts row count > 0

**Test: Creative Mix Has Values** (`test_bq_views.py:35-54`):
- Queries `v_creative_mix`
- Uses `bq query --format=prettyjson`
- Validates JSON structure

**Test Coverage Configuration** (`pyproject.toml:52-59`):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
addopts = "-v"

[tool.coverage.run]
source = ["paid_social_nav"]
omit = ["*/tests/*", "*/test_*"]
```

**CI/CD Quality Gates** (`.github/workflows/ci.yml`):

**Pipeline Steps:**
1. **Dependency Installation** (lines 24-27): `pip install -e ".[test]"`
2. **Ruff Linting** (lines 29-32): `ruff check .` - hard failure
3. **Mypy Type Checking** (lines 34-37): `mypy .` - soft failure
4. **Pytest with Coverage** (lines 39-41): `pytest tests/ -v --cov=paid_social_nav --cov-report=xml`
5. **Codecov Upload** (lines 43-47): `fail_ci_if_error: false`

**Python Matrix**: Tests run on Python 3.11 and 3.12

**Pre-commit Hooks** (`.pre-commit-config.yaml`):
- Standard hooks: check-toml, check-yaml, end-of-file-fixer, trailing-whitespace
- Ruff hooks: `ruff` with `--fix` flag, `ruff-format`
- Installed via `make dev-setup`

**Ruff Configuration** (`pyproject.toml:35-44`):
- Line length: 88 characters
- Select: E (pycodestyle errors), F (pyflakes), I (isort), N (pep8-naming), W (warnings), B (flake8-bugbear), UP (pyupgrade)
- Ignore: E501 (line too long), I001 (import order), N812 (lowercase import alias)

**Mypy Configuration** (`pyproject.toml:46-50`):
- `disallow_untyped_defs = true` - strict typing enforcement
- `warn_return_any = true`
- `warn_unused_configs = true`

**Audit Points:**
1. Integration tests pass with `PSN_INTEGRATION=1`
2. Unit tests cover CLI validation and error handling
3. Pre-commit hooks installed and passing
4. CI pipeline green on both Python 3.11 and 3.12
5. No ruff linting errors
6. Type checking passes (or known issues documented)
7. Coverage report generated (no minimum threshold enforced)

**Code References:**
- `tests/test_insights_cli.py` - CLI validation unit tests
- `tests/integration/test_meta_e2e.py` - End-to-end Meta integration
- `tests/integration/test_bq_views.py` - BigQuery view tests
- `.github/workflows/ci.yml` - CI pipeline configuration
- `.pre-commit-config.yaml` - Pre-commit hooks

## Architecture Documentation

### Current Patterns

**1. Generator Pattern** (`adapter.py:39`, `133`)
- `fetch_insights()` yields records incrementally
- Enables memory-efficient processing of large datasets
- Avoids loading entire API response into memory

**2. Staging-and-Merge Pattern** (`storage/bq.py:110-161`)
- Staging table receives batch data
- MERGE operation deduplicates into fact table
- Atomic transaction ensures consistency
- Idempotent: safe re-execution

**3. Multi-Level Hierarchy** (`core/enums.py:10-14`)
- `Entity` enum: AD, ADSET, CAMPAIGN
- Nullable ID fields support different aggregation levels
- Same schema accommodates all hierarchy levels

**4. Retry with Backoff** (`sync.py:162-215`)
- Configurable retry count (default: 3)
- Exponential backoff between attempts (default: 2.0s)
- Wraps adapter calls in orchestration layer

**5. Idempotent Operations**
- `create_table(..., exists_ok=True)` throughout
- `create_dataset(..., exists_ok=True)`
- MERGE updates existing rows, inserts new
- Safe re-execution without duplication

**6. Weighted Audit Scoring** (`audit/engine.py:58-195`)
- Each rule independently weighted
- Overall score = weighted average
- Flexible prioritization of performance dimensions

**7. View-Based Analytics Layer**
- Raw fact table separated from analytics
- Pre-aggregated views reduce query complexity
- Consistent use of `SAFE_DIVIDE()` for safety

**8. Tenant Configuration Pattern** (`tenants.py:27-40`)
- YAML-based multi-tenant setup
- Per-tenant: project_id, dataset, default_level
- CLI `--tenant` flag overrides defaults

### Platform Support

**Currently Implemented:**
- Meta (Facebook, Instagram, WhatsApp) - Full adapter implementation

**Defined but Not Implemented:**
- Reddit - `Platform.REDDIT` enum only
- Pinterest - `Platform.PINTEREST` enum only
- TikTok - `Platform.TIKTOK` enum only
- X (Twitter) - `Platform.X` enum only

**Architecture Prepared:**
- `Platform` enum defines all platforms (`core/enums.py:5-11`)
- Adapter directory structure: `paid_social_nav/adapters/{platform}/`
- No base adapter class or abstract interface exists
- Pattern established by MetaAdapter can be replicated

## Code References

### Core Modules
- `paid_social_nav/adapters/meta/adapter.py:25` - MetaAdapter class, fetch_insights() method
- `paid_social_nav/core/sync.py:101` - sync_meta_insights() orchestration
- `paid_social_nav/core/config.py:62` - get_settings() configuration
- `paid_social_nav/core/tenants.py:27` - get_tenant() multi-tenant config
- `paid_social_nav/core/enums.py:5` - Platform, Entity, DatePreset enums
- `paid_social_nav/core/models.py:7` - DateRange dataclass

### Storage Layer
- `paid_social_nav/storage/bq.py:14` - BQClient.query_rows()
- `paid_social_nav/storage/bq.py:62` - ensure_insights_table() schema
- `paid_social_nav/storage/bq.py:110` - load_json_rows() MERGE pattern
- `paid_social_nav/storage/secrets.py:4` - access_secret() GCP integration

### Audit System
- `paid_social_nav/audit/engine.py:34` - run_audit() entry point
- `paid_social_nav/audit/engine.py:43` - AuditEngine class
- `paid_social_nav/audit/rules.py:45` - pacing_vs_target()
- `paid_social_nav/audit/rules.py:90` - ctr_threshold()
- `paid_social_nav/audit/rules.py:106` - frequency_threshold()
- `paid_social_nav/audit/rules.py:123` - budget_concentration()
- `paid_social_nav/audit/rules.py:146` - creative_diversity()
- `paid_social_nav/audit/rules.py:174` - tracking_health()

### CLI & Testing
- `paid_social_nav/cli/main.py:25` - meta_sync_insights() CLI command
- `paid_social_nav/cli/main.py:214` - audit_run() CLI command
- `tests/test_insights_cli.py:8` - CLI validation unit tests
- `tests/integration/test_meta_e2e.py:47` - End-to-end integration test
- `tests/integration/test_bq_views.py:15` - BigQuery view tests

### SQL Views
- `sql/views/insights_rollups.sql:58` - Base aggregation view with CTR/CPA
- `sql/views/v_creative_mix.sql:53` - Video/image share calculation
- `sql/views/v_budget_pacing.sql:5` - Spend aggregation
- `sql/views/v_structure_split.sql:5` - Entity counting

### Configuration Files
- `configs/tenants.yaml` - Multi-tenant configuration
- `pyproject.toml:35` - Ruff, mypy, pytest configuration
- `.pre-commit-config.yaml` - Pre-commit hooks
- `.github/workflows/ci.yml` - CI pipeline

## Historical Context (from thoughts/)

No existing research documents or historical context found in `thoughts/` directory.

## Related Research

This is the first research document for the PaidSocialNav codebase.

## Open Questions

1. **Missing SQL View**: `v_budget_concentration` is referenced in `audit/engine.py:217-227` but SQL file does not exist in `sql/views/`. Implementation needed for budget concentration rule.

2. **Base Adapter Pattern**: No abstract base class exists for adapters. Should a base adapter interface be created before implementing Reddit, Pinterest, TikTok, X platforms?

3. **Logging Framework**: No structured logging (Python `logging` module) used. Error communication via exceptions and CLI output only. Should structured logging be added for production monitoring?

4. **Test Coverage Threshold**: Coverage collected but no minimum percentage enforced. Should a threshold be established?

5. **Creative Dimension Table**: `v_creative_mix` view references `dim_ad` table for `media_type` classification (`sql/views/v_creative_mix.sql:38-39`). Where is this dimension table populated? Is it manually maintained or automatically synced?

6. **Audit Report Templates**: Report rendering uses placeholder implementation (`render/renderer.py:6-9`) with comment indicating Jinja2 planned. What template format should be used?

7. **Platform Adapter Differences**: Meta uses Graph API v18.0. What API versions/patterns do other platforms use? Should version be configurable per platform?

8. **Rate Limit Platform Differences**: Current rate limiting is generic RPS. Do different platforms have different rate limit structures (e.g., hourly quotas, concurrent request limits)?
