#!/usr/bin/env python
"""List all customers in the PaidSocialNav registry."""

from __future__ import annotations

import argparse

from paid_social_nav.core.customer_registry import CustomerRegistry

try:
    from tabulate import tabulate

    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False


def list_customers(
    status: str | None = "active",
    registry_project_id: str = "topgolf-460202",
    format: str = "table",
) -> None:
    """
    List all customers from the registry.

    Args:
        status: Filter by status ('active', 'paused', 'churned', None for all)
        registry_project_id: Registry project ID
        format: Output format ('table', 'json', 'csv')
    """
    registry = CustomerRegistry(registry_project_id=registry_project_id)
    customers = registry.list_customers(status=status)

    if not customers:
        print(f"No {status or 'any'} customers found in registry.")
        return

    if format == "json":
        import json
        print(json.dumps([vars(c) for c in customers], indent=2, default=str))
        return

    # Prepare table data
    headers = [
        "Customer ID",
        "Name",
        "GCP Project",
        "Meta Accounts",
        "Status",
        "Onboarded",
        "Tier",
    ]

    rows = []
    for customer in customers:
        rows.append(
            [
                customer.customer_id,
                customer.customer_name,
                customer.gcp_project_id,
                len(customer.meta_ad_account_ids or []),
                customer.status,
                customer.onboarded_at.strftime("%Y-%m-%d")
                if customer.onboarded_at
                else "N/A",
                customer.usage_tier,
            ]
        )

    if format == "csv":
        import csv
        import sys

        writer = csv.writer(sys.stdout)
        writer.writerow(headers)
        writer.writerows(rows)
    else:
        print(f"\n📊 PaidSocialNav Customers ({status or 'all'} status)\n")
        if HAS_TABULATE:
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            # Fallback to simple formatting
            print(" | ".join(headers))
            print("-" * 80)
            for row in rows:
                print(" | ".join(str(v) for v in row))
        print(f"\nTotal: {len(customers)} customer(s)")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="List PaidSocialNav customers")
    parser.add_argument(
        "--status",
        choices=["active", "paused", "churned", "all"],
        default="active",
        help="Filter by status (default: active)",
    )
    parser.add_argument(
        "--registry-project",
        default="topgolf-460202",
        help="Registry project ID (default: topgolf-460202)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )

    args = parser.parse_args()

    status = None if args.status == "all" else args.status

    list_customers(
        status=status,
        registry_project_id=args.registry_project,
        format=args.format,
    )


if __name__ == "__main__":
    main()
