#!/usr/bin/env python
"""Migrate existing tenants from tenants.yaml to BigQuery customer registry."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from paid_social_nav.core.customer_registry import CustomerRegistry


def migrate_tenants(
    registry_project_id: str = "topgolf-460202",
    dry_run: bool = False,
) -> None:
    """
    Migrate tenants from tenants.yaml to BigQuery registry.

    Args:
        registry_project_id: Registry project ID
        dry_run: If True, only show what would be done
    """
    print("🔄 Migrating tenants from tenants.yaml to BigQuery registry")
    print("=" * 60)

    # Load tenants.yaml
    tenants_path = Path("configs/tenants.yaml")
    if not tenants_path.exists():
        print("❌ tenants.yaml not found at configs/tenants.yaml")
        return

    with tenants_path.open("r") as f:
        data = yaml.safe_load(f)

    tenants = data.get("tenants", {})

    if not tenants:
        print("⚠️  No tenants found in tenants.yaml")
        return

    print(f"Found {len(tenants)} tenant(s) in tenants.yaml")
    print()

    # Initialize registry
    registry = CustomerRegistry(registry_project_id=registry_project_id)

    # Ensure registry exists
    if not dry_run:
        registry.ensure_registry_exists()

    # Migrate each tenant
    for tenant_id, config in tenants.items():
        print(f"\n{'─' * 60}")
        print(f"Tenant: {tenant_id}")
        print(f"{'─' * 60}")

        customer_name = tenant_id.replace("_", " ").replace("-", " ").title()
        gcp_project_id = config.get("project_id")
        bq_dataset = config.get("dataset", "paid_social")
        default_level = config.get("default_level", "campaign")

        print(f"  Name: {customer_name}")
        print(f"  GCP Project: {gcp_project_id}")
        print(f"  Dataset: {bq_dataset}")
        print(f"  Default Level: {default_level}")

        if dry_run:
            print(f"  [DRY RUN] Would add to registry")
            continue

        # Check if already exists
        existing = registry.get_customer(tenant_id)
        if existing:
            print(f"  ℹ️  Customer already exists in registry, skipping")
            continue

        # Add to registry
        try:
            registry.add_customer(
                customer_id=tenant_id,
                customer_name=customer_name,
                gcp_project_id=gcp_project_id,
                bq_dataset=bq_dataset,
                default_level=default_level,
                tags=["migrated_from_yaml"],
                created_by="migration_script",
            )
            print(f"  ✅ Added to registry")
        except Exception as e:
            print(f"  ❌ Failed to add: {e}")

    print(f"\n{'=' * 60}")
    print("✅ Migration complete!")
    print()
    print("To verify:")
    print("  python scripts/list_customers.py")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate tenants from YAML to BigQuery registry"
    )
    parser.add_argument(
        "--registry-project",
        default="topgolf-460202",
        help="Registry project ID (default: topgolf-460202)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )

    args = parser.parse_args()

    migrate_tenants(
        registry_project_id=args.registry_project,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
