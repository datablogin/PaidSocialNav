#!/usr/bin/env python
"""Setup customer registry using Python BigQuery client."""

from __future__ import annotations

import argparse
from google.cloud import bigquery


def setup_registry(project_id: str = "topgolf-460202") -> None:
    """Create customer registry dataset and tables."""
    print("🏗️  Setting up PaidSocialNav Customer Registry")
    print("=" * 60)
    print(f"Registry Project: {project_id}")

    client = bigquery.Client(project=project_id)
    dataset_id = f"{project_id}.paidsocialnav_registry"

    # Create dataset
    print("\n📦 Creating BigQuery dataset...")
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"
    dataset.description = "PaidSocialNav customer registry and usage tracking"

    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"✓ Dataset created: {dataset_id}")
    except Exception as e:
        print(f"✗ Failed to create dataset: {e}")
        return

    # Create customers table
    print("\n📋 Creating customers table...")
    customers_table_id = f"{dataset_id}.customers"
    customers_schema = [
        bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("customer_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("gcp_project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("bq_dataset", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("meta_ad_account_ids", "STRING", mode="REPEATED"),
        bigquery.SchemaField("meta_access_token_secret", "STRING"),
        bigquery.SchemaField("default_level", "STRING"),
        bigquery.SchemaField("active_platforms", "STRING", mode="REPEATED"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("onboarded_at", "TIMESTAMP"),
        bigquery.SchemaField("updated_at", "TIMESTAMP"),
        bigquery.SchemaField("created_by", "STRING"),
        bigquery.SchemaField("monthly_spend_limit", "FLOAT64"),
        bigquery.SchemaField("usage_tier", "STRING"),
        bigquery.SchemaField("primary_contact_email", "STRING"),
        bigquery.SchemaField("primary_contact_name", "STRING"),
        bigquery.SchemaField("audit_schedule", "STRING"),
        bigquery.SchemaField("alert_thresholds", "JSON"),
        bigquery.SchemaField("tags", "STRING", mode="REPEATED"),
        bigquery.SchemaField("notes", "STRING"),
    ]

    customers_table = bigquery.Table(customers_table_id, schema=customers_schema)
    customers_table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="onboarded_at",
    )
    customers_table.clustering_fields = ["customer_id", "status", "usage_tier"]

    try:
        customers_table = client.create_table(customers_table, exists_ok=True)
        print(f"✓ Table created: {customers_table_id}")
    except Exception as e:
        print(f"✗ Failed to create customers table: {e}")

    # Create active_customers view
    print("\n📊 Creating active_customers view...")
    view_id = f"{dataset_id}.active_customers"
    view_query = f"""
    SELECT
      customer_id,
      customer_name,
      gcp_project_id,
      bq_dataset,
      meta_ad_account_ids,
      default_level,
      active_platforms,
      onboarded_at,
      usage_tier,
      primary_contact_email
    FROM `{customers_table_id}`
    WHERE status = 'active'
    """

    view = bigquery.Table(view_id)
    view.view_query = view_query

    try:
        view = client.create_table(view, exists_ok=True)
        print(f"✓ View created: {view_id}")
    except Exception as e:
        print(f"✗ Failed to create view: {e}")

    # Create customer_usage table
    print("\n📈 Creating customer_usage table...")
    usage_table_id = f"{dataset_id}.customer_usage"
    usage_schema = [
        bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("usage_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("meta_api_calls", "INT64"),
        bigquery.SchemaField("bigquery_bytes_processed", "INT64"),
        bigquery.SchemaField("audits_run", "INT64"),
        bigquery.SchemaField("reports_generated", "INT64"),
        bigquery.SchemaField("anthropic_input_tokens", "INT64"),
        bigquery.SchemaField("anthropic_output_tokens", "INT64"),
        bigquery.SchemaField("estimated_cost_usd", "FLOAT64"),
        bigquery.SchemaField("recorded_at", "TIMESTAMP"),
    ]

    usage_table = bigquery.Table(usage_table_id, schema=usage_schema)
    usage_table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="usage_date",
    )
    usage_table.clustering_fields = ["customer_id", "usage_date"]

    try:
        usage_table = client.create_table(usage_table, exists_ok=True)
        print(f"✓ Table created: {usage_table_id}")
    except Exception as e:
        print(f"✗ Failed to create usage table: {e}")

    # Create audit_history table
    print("\n📝 Creating audit_history table...")
    audit_table_id = f"{dataset_id}.audit_history"
    audit_schema = [
        bigquery.SchemaField("audit_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("audit_level", "STRING"),
        bigquery.SchemaField("audit_window", "STRING"),
        bigquery.SchemaField("audit_config_path", "STRING"),
        bigquery.SchemaField("overall_score", "FLOAT64"),
        bigquery.SchemaField("total_issues", "INT64"),
        bigquery.SchemaField("critical_issues", "INT64"),
        bigquery.SchemaField("warnings", "INT64"),
        bigquery.SchemaField("execution_time_seconds", "FLOAT64"),
        bigquery.SchemaField("rows_analyzed", "INT64"),
        bigquery.SchemaField("report_formats", "STRING", mode="REPEATED"),
        bigquery.SchemaField("sheets_url", "STRING"),
        bigquery.SchemaField("executed_at", "TIMESTAMP"),
        bigquery.SchemaField("executed_by", "STRING"),
        bigquery.SchemaField("execution_mode", "STRING"),
    ]

    audit_table = bigquery.Table(audit_table_id, schema=audit_schema)
    audit_table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="executed_at",
    )
    audit_table.clustering_fields = ["customer_id", "audit_level"]

    try:
        audit_table = client.create_table(audit_table, exists_ok=True)
        print(f"✓ Table created: {audit_table_id}")
    except Exception as e:
        print(f"✗ Failed to create audit table: {e}")

    print("\n" + "=" * 60)
    print("✅ Registry setup complete!")
    print("\nNext steps:")
    print("1. Migrate existing tenants:")
    print("   python scripts/migrate_tenants_to_registry.py")
    print("2. List customers:")
    print("   python scripts/list_customers.py")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Setup customer registry")
    parser.add_argument(
        "--project",
        default="topgolf-460202",
        help="Registry project ID (default: topgolf-460202)",
    )

    args = parser.parse_args()
    setup_registry(project_id=args.project)


if __name__ == "__main__":
    main()
