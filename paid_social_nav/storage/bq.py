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


def _staging_table(project_id: str, dataset: str) -> str:
    return f"{project_id}.{dataset}.__stg_{INSIGHTS_TABLE}"


def _ensure_staging_table(project_id: str, dataset: str) -> None:
    client = bigquery.Client(project=project_id)
    table_id = _staging_table(project_id, dataset)
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
    client = bigquery.Client(project=project_id)

    ensure_insights_table(project_id, dataset)
    _ensure_staging_table(project_id, dataset)

    # Load to staging
    job_config = bigquery.LoadJobConfig()
    job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    stg_table = _staging_table(project_id, dataset)
    # Use a temporary in-memory file by converting to newline-delimited JSON strings
    import json
    from io import BytesIO

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

    # Clean staging (optional: truncate)
    client.query(f"TRUNCATE TABLE `{stg_table}`").result()
