"""Manual script to populate dim_ad table with media_type classifications.

Usage:
    python scripts/populate_dim_ad.py --project fleming-424413 --dataset paid_social --csv data/ad_metadata.csv

CSV Format:
    ad_global_id,media_type,ad_name,creative_id
    meta:ad:123456,video,Summer Campaign Video,cr_789
    meta:ad:123457,image,Fall Banner Ad,cr_790
"""

import argparse
import csv
from datetime import UTC, datetime

from google.cloud import bigquery


def load_dim_ad_from_csv(project_id: str, dataset: str, csv_path: str) -> None:
    """Load ad metadata from CSV file into dim_ad table."""
    import json
    from io import BytesIO

    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.dim_ad"
    stg_table_id = f"{project_id}.{dataset}.__stg_dim_ad"

    # Ensure dim_ad table exists
    from paid_social_nav.storage.bq import ensure_dim_ad_table

    ensure_dim_ad_table(project_id, dataset)

    # Ensure staging table exists
    schema = [
        bigquery.SchemaField("ad_global_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("media_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ad_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("creative_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
    ]
    stg_table = bigquery.Table(stg_table_id, schema=schema)
    client.create_table(stg_table, exists_ok=True)

    # Read CSV and prepare rows
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "ad_global_id": row["ad_global_id"],
                    "media_type": row.get("media_type"),
                    "ad_name": row.get("ad_name"),
                    "creative_id": row.get("creative_id"),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )

    # Load to staging table
    job_config = bigquery.LoadJobConfig()
    job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    buf = BytesIO()
    for r in rows:
        buf.write((json.dumps(r) + "\n").encode("utf-8"))
    buf.seek(0)

    load_job = client.load_table_from_file(buf, stg_table_id, job_config=job_config)
    load_job.result()

    # Merge into destination using MERGE statement
    merge_sql = f"""
    MERGE `{table_id}` T
    USING `{stg_table_id}` S
    ON T.ad_global_id = S.ad_global_id
    WHEN MATCHED THEN UPDATE SET
      media_type = S.media_type,
      ad_name = S.ad_name,
      creative_id = S.creative_id,
      updated_at = S.updated_at
    WHEN NOT MATCHED THEN INSERT ROW
    """
    client.query(merge_sql).result()

    # Clean up staging table
    client.query(f"TRUNCATE TABLE `{stg_table_id}`").result()

    print(f"Loaded {len(rows)} rows into {table_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate dim_ad table")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--csv", required=True)

    args = parser.parse_args()
    load_dim_ad_from_csv(args.project, args.dataset, args.csv)
