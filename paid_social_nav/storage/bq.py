from __future__ import annotations

from typing import Any

from google.cloud import bigquery


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

