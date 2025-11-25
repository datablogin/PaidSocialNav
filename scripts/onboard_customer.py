#!/usr/bin/env python
"""Customer onboarding script for PaidSocialNav.

This script helps onboard new customers by:
1. Creating customer record in BigQuery registry
2. Setting up GCP project infrastructure
3. Creating necessary BigQuery datasets and tables
4. Storing Meta API credentials in Secret Manager
5. Running initial data sync
"""

from __future__ import annotations

import argparse
import sys

from google.cloud import bigquery, secretmanager
from paid_social_nav.core.customer_registry import CustomerRegistry


def create_customer_infrastructure(
    customer_id: str,
    gcp_project_id: str,
    bq_dataset: str = "paid_social",
) -> None:
    """Create BigQuery dataset and tables for customer."""
    print(f"\n📦 Creating infrastructure for {customer_id}...")

    client = bigquery.Client(project=gcp_project_id)

    # Create dataset
    dataset_id = f"{gcp_project_id}.{bq_dataset}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"
    dataset.description = f"Paid social advertising data for {customer_id}"

    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"✓ Dataset created: {dataset_id}")
    except Exception as e:
        print(f"✗ Failed to create dataset: {e}")
        return

    # Create fct_ad_insights_daily table
    table_id = f"{dataset_id}.fct_ad_insights_daily"
    schema = [
        bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("account_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("campaign_id", "STRING"),
        bigquery.SchemaField("campaign_name", "STRING"),
        bigquery.SchemaField("adset_id", "STRING"),
        bigquery.SchemaField("adset_name", "STRING"),
        bigquery.SchemaField("ad_id", "STRING"),
        bigquery.SchemaField("ad_name", "STRING"),
        bigquery.SchemaField("level", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("impressions", "INTEGER"),
        bigquery.SchemaField("clicks", "INTEGER"),
        bigquery.SchemaField("spend", "FLOAT"),
        bigquery.SchemaField("conversions", "INTEGER"),
        bigquery.SchemaField("ctr", "FLOAT"),
        bigquery.SchemaField("cpc", "FLOAT"),
        bigquery.SchemaField("cpm", "FLOAT"),
        bigquery.SchemaField("frequency", "FLOAT"),
        bigquery.SchemaField("reach", "INTEGER"),
        bigquery.SchemaField("campaign_global_id", "STRING"),
        bigquery.SchemaField("adset_global_id", "STRING"),
        bigquery.SchemaField("ad_global_id", "STRING"),
        bigquery.SchemaField("loaded_at", "TIMESTAMP"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="date",
    )
    table.clustering_fields = ["level", "campaign_id", "adset_id"]

    try:
        table = client.create_table(table, exists_ok=True)
        print(f"✓ Table created: {table_id}")
    except Exception as e:
        print(f"✗ Failed to create table: {e}")

    print(f"✓ Infrastructure setup complete for {customer_id}")


def store_meta_credentials(
    customer_id: str,
    registry_project_id: str,
    meta_access_token: str,
) -> str:
    """Store Meta API credentials in Secret Manager."""
    print(f"\n🔐 Storing Meta credentials for {customer_id}...")

    secret_client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{registry_project_id}"
    secret_id = f"{customer_id.upper()}_META_ACCESS_TOKEN"

    # Create secret
    try:
        secret_client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {
                    "replication": {"automatic": {}},
                    "labels": {"customer": customer_id, "platform": "meta"},
                },
            }
        )
        print(f"✓ Secret created: {secret_id}")
    except Exception as e:
        if "already exists" in str(e):
            print(f"✓ Secret already exists: {secret_id}")
        else:
            print(f"✗ Failed to create secret: {e}")
            return ""

    # Add version with actual token
    try:
        secret_client.add_secret_version(
            request={
                "parent": f"{parent}/secrets/{secret_id}",
                "payload": {"data": meta_access_token.encode("UTF-8")},
            }
        )
        print("✓ Secret version added")
    except Exception as e:
        print(f"✗ Failed to add secret version: {e}")
        return ""

    secret_ref = f"projects/{registry_project_id}/secrets/{secret_id}"
    return secret_ref


def onboard_customer(
    customer_id: str,
    customer_name: str,
    gcp_project_id: str,
    meta_ad_account_ids: list[str],
    meta_access_token: str,
    registry_project_id: str,
    primary_contact_email: str | None = None,
    tags: list[str] | None = None,
    created_by: str | None = None,
    setup_infrastructure: bool = True,
) -> None:
    """
    Complete customer onboarding workflow.

    Args:
        customer_id: Unique identifier (e.g., 'newclient')
        customer_name: Display name (e.g., 'New Client Inc.')
        gcp_project_id: Customer's GCP project ID
        meta_ad_account_ids: List of Meta ad account IDs
        meta_access_token: Meta API access token
        registry_project_id: Registry project ID
        primary_contact_email: Contact email
        tags: Organization tags
        created_by: User onboarding this customer
        setup_infrastructure: Whether to create BQ infrastructure
    """
    print(f"\n{'='*60}")
    print(f"🚀 Onboarding Customer: {customer_name}")
    print(f"{'='*60}")
    print(f"Customer ID: {customer_id}")
    print(f"GCP Project: {gcp_project_id}")
    print(f"Meta Accounts: {', '.join(meta_ad_account_ids)}")
    print(f"Registry Project: {registry_project_id}")
    print()

    # Initialize registry
    registry = CustomerRegistry(registry_project_id=registry_project_id)

    # Ensure registry exists
    print("📋 Setting up customer registry...")
    registry.ensure_registry_exists()

    # Store credentials
    if meta_access_token:
        meta_secret_ref = store_meta_credentials(
            customer_id, registry_project_id, meta_access_token
        )
    else:
        meta_secret_ref = None
        print("⚠ No Meta access token provided")

    # Create infrastructure
    if setup_infrastructure:
        create_customer_infrastructure(customer_id, gcp_project_id)

    # Add to registry
    print(f"\n✍️  Adding {customer_id} to customer registry...")
    try:
        registry.add_customer(
            customer_id=customer_id,
            customer_name=customer_name,
            gcp_project_id=gcp_project_id,
            bq_dataset="paid_social",
            meta_ad_account_ids=meta_ad_account_ids,
            meta_access_token_secret=meta_secret_ref,
            default_level="campaign",
            primary_contact_email=primary_contact_email,
            tags=tags or [],
            created_by=created_by or "onboarding_script",
        )
        print("✓ Customer added to registry")
    except Exception as e:
        print(f"✗ Failed to add customer to registry: {e}")
        return

    print(f"\n{'='*60}")
    print("✅ Customer onboarding complete!")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("1. Run initial data sync:")
    print(
        f"   python -m paid_social_nav.cli.main sync-meta {meta_ad_account_ids[0]} --tenant={customer_id}"
    )
    print("2. Run audit:")
    print(
        f"   python -m paid_social_nav.cli.main audit --tenant={customer_id} --config=configs/audit_config.yaml"
    )
    print("3. View customer in registry:")
    print("   python scripts/list_customers.py")
    print()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Onboard a new customer to PaidSocialNav"
    )
    parser.add_argument("customer_id", help="Unique customer identifier (e.g., 'newclient')")
    parser.add_argument("customer_name", help="Customer display name (e.g., 'New Client Inc.')")
    parser.add_argument("gcp_project_id", help="Customer's GCP project ID")
    parser.add_argument(
        "--meta-accounts",
        required=True,
        help="Comma-separated Meta ad account IDs",
    )
    parser.add_argument(
        "--meta-token-file",
        help="Path to file containing Meta API access token (more secure than --meta-token)",
    )
    parser.add_argument(
        "--meta-token",
        help="Meta API access token (DEPRECATED: use --meta-token-file or stdin for security)",
    )
    parser.add_argument(
        "--registry-project",
        default="topgolf-460202",
        help="Registry project ID (default: topgolf-460202)",
    )
    parser.add_argument("--email", help="Primary contact email")
    parser.add_argument("--tags", help="Comma-separated tags (e.g., 'golf,franchise')")
    parser.add_argument("--created-by", help="User creating this customer")
    parser.add_argument(
        "--no-infrastructure",
        action="store_true",
        help="Skip creating BigQuery infrastructure",
    )

    args = parser.parse_args()

    # Parse lists
    meta_accounts = [acc.strip() for acc in args.meta_accounts.split(",")]
    tags = [tag.strip() for tag in args.tags.split(",")] if args.tags else None

    # Get Meta token securely
    meta_token = None
    if args.meta_token_file:
        # Read from file (more secure)
        with open(args.meta_token_file) as f:
            meta_token = f.read().strip()
    elif args.meta_token:
        # Direct argument (less secure, show warning)
        meta_token = args.meta_token
        print(
            "⚠️  WARNING: Passing tokens via --meta-token is insecure. "
            "Use --meta-token-file instead."
        )
    else:
        # Prompt securely if not provided
        import getpass

        meta_token = getpass.getpass("Enter Meta access token (or press Enter to skip): ")
        if not meta_token:
            meta_token = None

    # Confirm
    print(f"\n⚠️  You are about to onboard customer: {args.customer_name}")
    print(f"   Customer ID: {args.customer_id}")
    print(f"   GCP Project: {args.gcp_project_id}")
    print(f"   Meta Accounts: {', '.join(meta_accounts)}")
    print(f"   Registry: {args.registry_project}")
    response = input("\nProceed with onboarding? [y/N]: ")

    if response.lower() != "y":
        print("❌ Onboarding cancelled")
        sys.exit(0)

    onboard_customer(
        customer_id=args.customer_id,
        customer_name=args.customer_name,
        gcp_project_id=args.gcp_project_id,
        meta_ad_account_ids=meta_accounts,
        meta_access_token=meta_token or "",
        registry_project_id=args.registry_project,
        primary_contact_email=args.email,
        tags=tags,
        created_by=args.created_by,
        setup_infrastructure=not args.no_infrastructure,
    )


if __name__ == "__main__":
    main()
