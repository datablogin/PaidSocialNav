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
        client.get_dataset(ds_ref)
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
        bigquery.SchemaField("media_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ad_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("creative_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
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

    Uses atomic staging table approach to prevent data loss if load fails.

    Args:
        project_id: GCP project ID (validated against SQL injection)
        dataset: BigQuery dataset name (validated against SQL injection)
        csv_path: Path to CSV file (can be absolute or relative to CWD)

    Returns:
        Number of rows loaded

    Raises:
        ValueError: If project_id or dataset contains invalid characters
        FileNotFoundError: If CSV file doesn't exist
        RuntimeError: If load fails
    """
    import csv
    import re
    import uuid
    from io import BytesIO
    from pathlib import Path

    # Validate inputs to prevent SQL injection
    if not re.match(r"^[A-Za-z0-9_\-]+$", project_id):
        raise ValueError(f"Invalid project_id: must contain only alphanumeric, underscore, or hyphen characters")
    if not re.match(r"^[A-Za-z0-9_]+$", dataset):
        raise ValueError(f"Invalid dataset: must contain only alphanumeric or underscore characters")

    client = bigquery.Client(project=project_id)

    # Ensure main table exists
    ensure_benchmarks_table(project_id, dataset)

    table_id = f"{project_id}.{dataset}.benchmarks_performance"

    # Read CSV and validate
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"Benchmarks CSV not found: {csv_path}")

    rows = []
    required_cols = {"industry", "region", "spend_band", "metric_name", "p25", "p50", "p75", "p90"}

    with csv_file.open("r") as f:
        reader = csv.DictReader(f)

        # Validate CSV schema
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no header")
        if not required_cols.issubset(set(reader.fieldnames)):
            missing = required_cols - set(reader.fieldnames)
            raise ValueError(f"CSV missing required columns: {missing}")

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
            # Safely convert percentile values
            p25 = _safe_float(row.get("p25"))
            p50 = _safe_float(row.get("p50"))
            p75 = _safe_float(row.get("p75"))
            p90 = _safe_float(row.get("p90"))

            # Validate percentile ordering (if all present)
            if all(v is not None for v in [p25, p50, p75, p90]):
                if not (p25 <= p50 <= p75 <= p90):
                    raise ValueError(
                        f"Invalid percentile ordering in row {row_num}: "
                        f"p25={p25}, p50={p50}, p75={p75}, p90={p90}. "
                        f"Expected p25 <= p50 <= p75 <= p90"
                    )

            benchmark_row = {
                "industry": row["industry"],
                "region": row["region"],
                "spend_band": row["spend_band"],
                "metric_name": row["metric_name"],
                "p25": p25,
                "p50": p50,
                "p75": p75,
                "p90": p90,
            }
            rows.append(benchmark_row)

    if not rows:
        return 0

    # Use atomic staging table approach (like load_json_rows)
    unique_id = uuid.uuid4().hex[:8]
    stg_table = f"{project_id}.{dataset}.__stg_benchmarks_{unique_id}"

    try:
        # Create staging table with same schema
        stg_schema = [
            bigquery.SchemaField("industry", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("region", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("spend_band", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("metric_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("p25", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("p50", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("p75", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("p90", "FLOAT64", mode="NULLABLE"),
        ]
        stg_table_obj = bigquery.Table(stg_table, schema=stg_schema)
        client.create_table(stg_table_obj)

        # Load to staging using batch load (more efficient than streaming)
        job_config = bigquery.LoadJobConfig()
        job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON

        buf = BytesIO()
        for r in rows:
            buf.write((json.dumps(r) + "\n").encode("utf-8"))
        buf.seek(0)

        load_job = client.load_table_from_file(buf, stg_table, job_config=job_config)
        load_job.result()  # Wait for load to complete

        # Atomically replace main table data with staging data
        # Using MERGE with DELETE + INSERT pattern for full refresh
        merge_sql = f"""
        MERGE `{table_id}` T
        USING `{stg_table}` S
        ON FALSE  -- Never match, always insert
        WHEN NOT MATCHED BY SOURCE THEN DELETE
        WHEN NOT MATCHED BY TARGET THEN INSERT ROW
        """
        client.query(merge_sql).result()

        return len(rows)

    finally:
        # Clean up staging table
        client.delete_table(stg_table, not_found_ok=True)
