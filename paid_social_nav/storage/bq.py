from __future__ import annotations

from typing import Any

from google.cloud import bigquery

INSIGHTS_TABLE = "fct_ad_insights_daily"


class BQClient:
    def __init__(self, project: str | None = None):
        self.client = bigquery.Client(project=project)

    def query_rows(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        location: str | None = None,
        timeout: float | None = 60.0,
    ) -> list[dict[str, Any]]:
        job_config = bigquery.QueryJobConfig()
        if params:
            job_config.query_parameters = [
                self._to_bq_param(k, v) for k, v in params.items()
            ]
        try:
            job = self.client.query(sql, job_config=job_config, location=location)
            result = job.result(timeout=timeout)
            rows: list[dict[str, Any]] = []
            for row in result:
                rows.append(dict(row.items()))
            return rows
        except Exception as e:
            # Surface a concise error while preserving original exception for callers to log
            raise RuntimeError(f"BigQuery query failed: {e}") from e

    @staticmethod
    def _to_bq_param(name: str, value: Any) -> bigquery.ScalarQueryParameter:
        if isinstance(value, bool):
            bq_type = "BOOL"
        elif isinstance(value, int):
            bq_type = "INT64"
        elif isinstance(value, float):
            bq_type = "FLOAT64"
        elif isinstance(value, str):
            bq_type = "STRING"
        else:
            bq_type = "STRING"
        return bigquery.ScalarQueryParameter(name, bq_type, value)


def ensure_dataset(project_id: str, dataset: str) -> None:
    client = bigquery.Client(project=project_id)
    ds_ref = bigquery.Dataset(f"{project_id}.{dataset}")
    ds_ref.location = "US"
    try:
        client.get_dataset(ds_ref.reference)
    except Exception:
        client.create_dataset(ds_ref, exists_ok=True)


def ensure_insights_table(project_id: str, dataset: str) -> None:
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.{INSIGHTS_TABLE}"
    schema = [
        bigquery.SchemaField("date", "DATE"),
        bigquery.SchemaField("level", "STRING"),
        bigquery.SchemaField("account_global_id", "STRING"),
        bigquery.SchemaField("campaign_global_id", "STRING"),
        bigquery.SchemaField("adset_global_id", "STRING"),
        bigquery.SchemaField("ad_global_id", "STRING"),
        bigquery.SchemaField("impressions", "INT64"),
        bigquery.SchemaField("clicks", "INT64"),
        bigquery.SchemaField("spend", "FLOAT64"),
        bigquery.SchemaField("conversions", "FLOAT64"),
        bigquery.SchemaField("ctr", "FLOAT64"),
        bigquery.SchemaField("frequency", "FLOAT64"),
        bigquery.SchemaField("raw_metrics", "JSON"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)


def ensure_dim_ad_table(project_id: str, dataset: str) -> None:
    """Ensure dim_ad dimension table exists with proper schema."""
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.dim_ad"

    schema = [
        bigquery.SchemaField("ad_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("platform_ad_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("adset_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("campaign_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("account_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("ad_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ad_status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("creative_global_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("created_time", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("raw_data", "JSON", mode="NULLABLE"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)


def ensure_dim_account_table(project_id: str, dataset: str) -> None:
    """Ensure dim_account dimension table exists with proper schema."""
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.dim_account"

    schema = [
        bigquery.SchemaField("account_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("platform_account_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("account_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("currency", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("timezone", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("account_status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("raw_data", "JSON", mode="NULLABLE"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)


def ensure_dim_campaign_table(project_id: str, dataset: str) -> None:
    """Ensure dim_campaign dimension table exists with proper schema."""
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.dim_campaign"

    schema = [
        bigquery.SchemaField("campaign_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("platform_campaign_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("account_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("campaign_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("campaign_status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("objective", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("buying_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("daily_budget", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("lifetime_budget", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("created_time", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("raw_data", "JSON", mode="NULLABLE"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)


def ensure_dim_adset_table(project_id: str, dataset: str) -> None:
    """Ensure dim_adset dimension table exists with proper schema."""
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.dim_adset"

    schema = [
        bigquery.SchemaField("adset_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("platform_adset_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("campaign_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("account_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("adset_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("adset_status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("optimization_goal", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("billing_event", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("bid_strategy", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("daily_budget", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("lifetime_budget", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("start_time", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("end_time", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("created_time", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("raw_data", "JSON", mode="NULLABLE"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)


def ensure_dim_creative_table(project_id: str, dataset: str) -> None:
    """Ensure dim_creative dimension table exists with proper schema."""
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.dim_creative"

    schema = [
        bigquery.SchemaField("creative_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("platform_creative_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("account_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("creative_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("creative_status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("body", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("call_to_action", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("image_url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("video_url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("thumbnail_url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("created_time", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("raw_data", "JSON", mode="NULLABLE"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)


def ensure_benchmarks_table(project_id: str, dataset: str) -> None:
    """Ensure benchmarks_performance table exists with proper schema and clustering."""
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.benchmarks_performance"

    schema = [
        bigquery.SchemaField("industry", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("spend_band", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("metric_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("p25", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("p50", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("p75", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("p90", "FLOAT64", mode="NULLABLE"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    # Add clustering for efficient queries on industry, region, spend_band
    table.clustering_fields = ["industry", "region", "spend_band"]
    client.create_table(table, exists_ok=True)


def _staging_table(project_id: str, dataset: str, unique_id: str | None = None) -> str:
    """Generate staging table name with optional unique ID to prevent race conditions."""
    if unique_id:
        return f"{project_id}.{dataset}.__stg_{INSIGHTS_TABLE}_{unique_id}"
    return f"{project_id}.{dataset}.__stg_{INSIGHTS_TABLE}"


def _create_staging_table(project_id: str, dataset: str, table_id: str) -> None:
    """Create a staging table with the insights schema."""
    client = bigquery.Client(project=project_id)
    schema = [
        bigquery.SchemaField("date", "DATE"),
        bigquery.SchemaField("level", "STRING"),
        bigquery.SchemaField("account_global_id", "STRING"),
        bigquery.SchemaField("campaign_global_id", "STRING"),
        bigquery.SchemaField("adset_global_id", "STRING"),
        bigquery.SchemaField("ad_global_id", "STRING"),
        bigquery.SchemaField("impressions", "INT64"),
        bigquery.SchemaField("clicks", "INT64"),
        bigquery.SchemaField("spend", "FLOAT64"),
        bigquery.SchemaField("conversions", "FLOAT64"),
        bigquery.SchemaField("ctr", "FLOAT64"),
        bigquery.SchemaField("frequency", "FLOAT64"),
        bigquery.SchemaField("raw_metrics", "JSON"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)


def load_json_rows(
    *, project_id: str, dataset: str, table: str, rows: list[dict[str, Any]]
) -> None:
    """Stage rows and merge into the destination table to avoid duplicates."""
    if not rows:
        return

    import json
    import uuid
    from io import BytesIO

    client = bigquery.Client(project=project_id)

    ensure_insights_table(project_id, dataset)

    # Use unique staging table name to prevent race conditions
    unique_id = uuid.uuid4().hex[:8]
    stg_table = _staging_table(project_id, dataset, unique_id=unique_id)

    try:
        # Create temporary staging table
        _create_staging_table(project_id, dataset, stg_table)

        # Load to staging
        job_config = bigquery.LoadJobConfig()
        job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON

        buf = BytesIO()
        for r in rows:
            buf.write((json.dumps(r) + "\n").encode("utf-8"))
        buf.seek(0)

        load_job = client.load_table_from_file(buf, stg_table, job_config=job_config)
        load_job.result()

        # Merge into destination
        dest = f"{project_id}.{dataset}.{table}"
        merge_sql = f"""
        MERGE `{dest}` T
        USING `{stg_table}` S
        ON T.date = S.date
           AND T.level = S.level
           AND IFNULL(T.account_global_id, '') = IFNULL(S.account_global_id, '')
           AND IFNULL(T.campaign_global_id, '') = IFNULL(S.campaign_global_id, '')
           AND IFNULL(T.adset_global_id, '') = IFNULL(S.adset_global_id, '')
           AND IFNULL(T.ad_global_id, '') = IFNULL(S.ad_global_id, '')
        WHEN MATCHED THEN UPDATE SET
          impressions = S.impressions,
          clicks = S.clicks,
          spend = S.spend,
          conversions = S.conversions,
          ctr = S.ctr,
          frequency = S.frequency,
          raw_metrics = S.raw_metrics
        WHEN NOT MATCHED THEN INSERT ROW
        """
        client.query(merge_sql).result()
    finally:
        # Clean up staging table
        client.delete_table(stg_table, not_found_ok=True)


def _safe_float(value: str | None) -> float | None:
    """Safely convert a value to float, returning None for invalid values."""
    if not value or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def load_benchmarks_csv(
    *, project_id: str, dataset: str, csv_path: str
) -> int:
    """Load benchmarks from CSV file into benchmarks_performance table.

    Uses atomic table replacement to prevent data loss and race conditions.
    Validates CSV data before creating any staging tables.

    Args:
        project_id: GCP project ID (validated against SQL injection)
        dataset: BigQuery dataset name (validated against SQL injection)
        csv_path: Path to CSV file (absolute or relative to CWD)
                 Must not contain path traversal sequences (.., ~)

    Returns:
        Number of rows loaded

    Raises:
        ValueError: If inputs contain invalid characters or CSV data is malformed
        FileNotFoundError: If CSV file doesn't exist
        RuntimeError: If load fails

    Note:
        Path security: Only loads from paths without traversal sequences.
        Concurrent access: Uses unique staging table names to prevent conflicts.
    """
    import csv
    import json
    import re
    import uuid
    from io import BytesIO
    from pathlib import Path

    # Validate inputs to prevent SQL injection
    if not re.match(r"^[A-Za-z0-9_\-]+$", project_id):
        raise ValueError("Invalid project_id: must contain only alphanumeric, underscore, or hyphen characters")
    if not re.match(r"^[A-Za-z0-9_]+$", dataset):
        raise ValueError("Invalid dataset: must contain only alphanumeric or underscore characters")

    # Validate CSV path to prevent path traversal attacks
    # Check for path traversal sequences BEFORE resolving
    if ".." in csv_path or "~" in csv_path:
        raise ValueError(f"Path traversal not allowed in csv_path: {csv_path}")

    csv_file = Path(csv_path)
    # Resolve to absolute path
    try:
        resolved_path = csv_file.resolve(strict=True)
    except Exception as e:
        raise FileNotFoundError(f"Invalid CSV path: {csv_path}") from e

    if not resolved_path.exists():
        raise FileNotFoundError(f"Benchmarks CSV not found: {csv_path}")

    # Validate CSV and prepare rows BEFORE creating any tables
    rows = []
    required_cols = {"industry", "region", "spend_band", "metric_name", "p25", "p50", "p75", "p90"}

    with resolved_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate CSV schema
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no header")
        if not required_cols.issubset(set(reader.fieldnames)):
            missing = required_cols - set(reader.fieldnames)
            raise ValueError(f"CSV missing required columns: {missing}")

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
            # Validate string fields
            industry = row.get("industry", "").strip()
            region = row.get("region", "").strip()
            spend_band = row.get("spend_band", "").strip()
            metric_name = row.get("metric_name", "").strip()

            if not industry or len(industry) > 50:
                raise ValueError(f"Row {row_num}: industry must be non-empty and <= 50 chars")
            if not region or len(region) > 20:
                raise ValueError(f"Row {row_num}: region must be non-empty and <= 20 chars")
            if not spend_band or len(spend_band) > 20:
                raise ValueError(f"Row {row_num}: spend_band must be non-empty and <= 20 chars")
            if not metric_name or len(metric_name) > 50:
                raise ValueError(f"Row {row_num}: metric_name must be non-empty and <= 50 chars")

            # Safely convert percentile values
            p25 = _safe_float(row.get("p25"))
            p50 = _safe_float(row.get("p50"))
            p75 = _safe_float(row.get("p75"))
            p90 = _safe_float(row.get("p90"))

            # Validate percentile values are in reasonable range
            for name, value in [("p25", p25), ("p50", p50), ("p75", p75), ("p90", p90)]:
                if value is not None and (value < 0 or value > 1000000):
                    raise ValueError(
                        f"Row {row_num}: {name}={value} is out of reasonable range (0-1000000). "
                        "Check if this is a valid metric value."
                    )

            # Validate percentile ordering (if all present)
            if all(v is not None for v in [p25, p50, p75, p90]):
                # Type narrowing: mypy now knows these are all floats
                assert p25 is not None and p50 is not None and p75 is not None and p90 is not None
                if not (p25 <= p50 <= p75 <= p90):
                    raise ValueError(
                        f"Invalid percentile ordering in row {row_num}: "
                        f"p25={p25}, p50={p50}, p75={p75}, p90={p90}. "
                        f"Expected p25 <= p50 <= p75 <= p90"
                    )

            benchmark_row = {
                "industry": industry,
                "region": region,
                "spend_band": spend_band,
                "metric_name": metric_name,
                "p25": p25,
                "p50": p50,
                "p75": p75,
                "p90": p90,
            }
            rows.append(benchmark_row)

    if not rows:
        return 0

    # Now create client and tables (after validation succeeds)
    client = bigquery.Client(project=project_id)

    # Ensure main table exists
    ensure_benchmarks_table(project_id, dataset)

    table_id = f"{project_id}.{dataset}.benchmarks_performance"

    # Use atomic table replacement (safer than MERGE for full refresh)
    unique_id = uuid.uuid4().hex[:8]
    temp_table = f"{project_id}.{dataset}.__temp_benchmarks_{unique_id}"

    try:
        # Create temporary table with same schema and clustering
        temp_schema = [
            bigquery.SchemaField("industry", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("region", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("spend_band", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("metric_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("p25", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("p50", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("p75", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("p90", "FLOAT64", mode="NULLABLE"),
        ]
        temp_table_obj = bigquery.Table(temp_table, schema=temp_schema)
        temp_table_obj.clustering_fields = ["industry", "region", "spend_band"]
        client.create_table(temp_table_obj)

        # Load to temporary table using batch load
        job_config = bigquery.LoadJobConfig()
        job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON

        buf = BytesIO()
        for r in rows:
            buf.write((json.dumps(r) + "\n").encode("utf-8"))
        buf.seek(0)

        load_job = client.load_table_from_file(buf, temp_table, job_config=job_config)
        load_job.result()  # Wait for load to complete

        # Atomically swap tables using CREATE OR REPLACE
        # This is safer than MERGE for full refresh as it's a single atomic operation
        swap_sql = f"""
        CREATE OR REPLACE TABLE `{table_id}`
        CLUSTER BY industry, region, spend_band
        AS SELECT * FROM `{temp_table}`
        """
        client.query(swap_sql).result()

        return len(rows)

    finally:
        # Clean up temporary table
        client.delete_table(temp_table, not_found_ok=True)


def upsert_dimension(
    *,
    project_id: str,
    dataset: str,
    table_name: str,
    rows: list[dict[str, Any]],
    merge_key: str,
) -> int:
    """Upsert dimension records using MERGE statement.

    Args:
        project_id: GCP project ID (alphanumeric, underscore, hyphen only)
        dataset: BigQuery dataset name (alphanumeric, underscore only)
        table_name: Dimension table name (e.g., 'dim_account', 'dim_campaign')
        rows: List of dimension records to upsert
        merge_key: Primary key field for matching (e.g., 'account_global_id')

    Returns:
        Number of rows processed

    Raises:
        ValueError: If inputs contain invalid characters (SQL injection prevention)
        RuntimeError: If upsert fails
    """
    import json
    import re
    import uuid
    from io import BytesIO

    if not rows:
        return 0

    # Validate inputs to prevent SQL injection
    if not re.match(r"^[A-Za-z0-9_\-]+$", project_id):
        raise ValueError(
            f"Invalid project_id '{project_id}': must contain only alphanumeric, underscore, or hyphen"
        )
    if not re.match(r"^[A-Za-z0-9_]+$", dataset):
        raise ValueError(
            f"Invalid dataset '{dataset}': must contain only alphanumeric or underscore"
        )
    if not re.match(r"^[A-Za-z0-9_]+$", table_name):
        raise ValueError(
            f"Invalid table_name '{table_name}': must contain only alphanumeric or underscore"
        )
    if not re.match(r"^[A-Za-z0-9_]+$", merge_key):
        raise ValueError(
            f"Invalid merge_key '{merge_key}': must contain only alphanumeric or underscore"
        )

    client = bigquery.Client(project=project_id)
    dest_table = f"{project_id}.{dataset}.{table_name}"

    # Create unique staging table
    unique_id = uuid.uuid4().hex[:8]
    stg_table = f"{project_id}.{dataset}.__stg_{table_name}_{unique_id}"

    try:
        # Get schema from destination table
        dest_table_obj = client.get_table(dest_table)
        schema = dest_table_obj.schema

        # Create staging table with same schema
        stg_table_obj = bigquery.Table(stg_table, schema=schema)
        client.create_table(stg_table_obj)

        # Load data to staging table
        job_config = bigquery.LoadJobConfig()
        job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON

        buf = BytesIO()
        for r in rows:
            buf.write((json.dumps(r) + "\n").encode("utf-8"))
        buf.seek(0)

        load_job = client.load_table_from_file(buf, stg_table, job_config=job_config)
        load_job.result()

        # Build MERGE statement
        # Get all field names except the merge key
        field_names = [field.name for field in schema]
        update_fields = [f for f in field_names if f != merge_key]

        # Build UPDATE SET clause
        update_set = ",\n          ".join([f"{f} = S.{f}" for f in update_fields])

        merge_sql = f"""
        MERGE `{dest_table}` T
        USING `{stg_table}` S
        ON T.{merge_key} = S.{merge_key}
        WHEN MATCHED THEN UPDATE SET
          {update_set}
        WHEN NOT MATCHED THEN INSERT ROW
        """

        client.query(merge_sql).result()
        return len(rows)

    finally:
        # Clean up staging table
        client.delete_table(stg_table, not_found_ok=True)
