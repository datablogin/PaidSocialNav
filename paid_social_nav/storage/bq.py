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
    ) -> list[dict[str, Any]]:
        job_config = bigquery.QueryJobConfig()
        if params:
            job_config.query_parameters = [
                self._to_bq_param(k, v) for k, v in params.items()
            ]

        job = self.client.query(sql, job_config=job_config, location=location)
        result = job.result()
        rows: list[dict[str, Any]] = []
        for row in result:
            rows.append(dict(row.items()))
        return rows

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

