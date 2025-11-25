"""Customer Registry - Multi-tenant customer management with BigQuery backend.

This module provides dynamic customer onboarding and management capabilities,
allowing PaidSocialNav to work with multiple clients without code changes.

Architecture:
- Primary customer registry stored in BigQuery (central project)
- Falls back to tenants.yaml for backward compatibility
- Supports dynamic customer onboarding via MCP tools or CLI
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from google.api_core import exceptions as gcp_exceptions
from google.cloud import bigquery

from paid_social_nav.core.tenants import Tenant, get_tenant as get_tenant_from_yaml
from paid_social_nav.storage.bq import BQClient

logger = logging.getLogger(__name__)


@dataclass
class Customer:
    """Enhanced customer model with full registry data."""

    customer_id: str
    customer_name: str
    gcp_project_id: str
    bq_dataset: str
    meta_ad_account_ids: list[str] | None = None
    meta_access_token_secret: str | None = None
    default_level: str = "campaign"
    active_platforms: list[str] | None = None
    status: str = "active"
    onboarded_at: datetime | None = None
    updated_at: datetime | None = None
    usage_tier: str = "standard"
    primary_contact_email: str | None = None
    tags: list[str] | None = None
    notes: str | None = None

    def to_tenant(self) -> Tenant:
        """Convert Customer to legacy Tenant format for backward compatibility."""
        from paid_social_nav.core.enums import Entity

        level = Entity(self.default_level) if self.default_level else None
        return Tenant(
            id=self.customer_id,
            project_id=self.gcp_project_id,
            dataset=self.bq_dataset,
            default_level=level,
        )


class CustomerRegistry:
    """Customer registry with BigQuery backend and YAML fallback."""

    def __init__(self, registry_project_id: str | None = None):
        """
        Initialize customer registry.

        Args:
            registry_project_id: GCP project ID for central registry.
                               Defaults to env var REGISTRY_PROJECT_ID or GCP_PROJECT_ID.

        Raises:
            ValueError: If registry project ID cannot be determined.
        """
        self.registry_project_id = (
            registry_project_id
            or os.getenv("REGISTRY_PROJECT_ID")
            or os.getenv("GCP_PROJECT_ID")
        )

        if not self.registry_project_id:
            raise ValueError(
                "Registry project ID must be provided via parameter, "
                "REGISTRY_PROJECT_ID env var, or GCP_PROJECT_ID env var"
            )
        self.registry_dataset = "paidsocialnav_registry"
        self.customers_table = f"{self.registry_project_id}.{self.registry_dataset}.customers"
        # Cache BigQuery client for reuse across operations
        self._bq_client: BQClient | None = None

    def _get_bq_client(self) -> BQClient:
        """Get BigQuery client for registry (cached for reuse)."""
        if self._bq_client is None:
            self._bq_client = BQClient(project=self.registry_project_id)
        return self._bq_client

    def ensure_registry_exists(self) -> None:
        """Create registry dataset and tables if they don't exist.

        Note: Tables should be created via scripts/setup_registry_python.py
        This method only verifies the registry exists.
        """
        bq = self._get_bq_client()
        client = bq.client

        # Verify dataset exists
        dataset_id = f"{self.registry_project_id}.{self.registry_dataset}"

        try:
            client.get_dataset(dataset_id)
            print(f"✓ Registry dataset exists: {dataset_id}")
        except Exception:
            print(f"⚠ Registry dataset not found: {dataset_id}")
            print(f"  Run: python scripts/setup_registry_python.py --project={self.registry_project_id}")

    def get_customer(self, customer_id: str) -> Customer | None:
        """
        Get customer by ID from registry, with fallback to YAML.

        Args:
            customer_id: Customer identifier

        Returns:
            Customer object or None if not found
        """
        # Try BigQuery registry first
        try:
            bq = self._get_bq_client()
            query = f"""
            SELECT
                customer_id,
                customer_name,
                gcp_project_id,
                bq_dataset,
                meta_ad_account_ids,
                meta_access_token_secret,
                default_level,
                active_platforms,
                status,
                onboarded_at,
                updated_at,
                usage_tier,
                primary_contact_email,
                tags,
                notes
            FROM `{self.customers_table}`
            WHERE customer_id = @customer_id
              AND status = 'active'
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id)
                ]
            )

            rows = list(bq.client.query(query, job_config=job_config).result())

            if rows:
                row = rows[0]
                return Customer(
                    customer_id=row.customer_id,
                    customer_name=row.customer_name,
                    gcp_project_id=row.gcp_project_id,
                    bq_dataset=row.bq_dataset,
                    meta_ad_account_ids=row.meta_ad_account_ids,
                    meta_access_token_secret=row.meta_access_token_secret,
                    default_level=row.default_level,
                    active_platforms=row.active_platforms,
                    status=row.status,
                    onboarded_at=row.onboarded_at,
                    updated_at=row.updated_at,
                    usage_tier=row.usage_tier,
                    primary_contact_email=row.primary_contact_email,
                    tags=row.tags,
                    notes=row.notes,
                )
        except gcp_exceptions.NotFound:
            logger.error(f"Registry table not found: {self.customers_table}")
        except gcp_exceptions.Forbidden:
            logger.error(f"Access denied to registry: {self.customers_table}")
        except gcp_exceptions.DeadlineExceeded:
            logger.error("BigQuery query timeout while fetching customer")
        except Exception:
            logger.exception("Unexpected error querying customer registry")

        # Fallback to YAML
        tenant = get_tenant_from_yaml(customer_id)
        if tenant:
            return Customer(
                customer_id=tenant.id,
                customer_name=tenant.id.title(),
                gcp_project_id=tenant.project_id,
                bq_dataset=tenant.dataset,
                default_level=tenant.default_level.value
                if tenant.default_level
                else "campaign",
                status="active",
            )

        return None

    def list_customers(
        self, status: str | None = "active", limit: int = 100
    ) -> list[Customer]:
        """
        List all customers from registry.

        Args:
            status: Filter by status ('active', 'paused', 'churned', None for all)
            limit: Maximum number of customers to return

        Returns:
            List of Customer objects
        """
        try:
            bq = self._get_bq_client()

            # Use parameterized query to prevent SQL injection
            query_parameters = []
            where_clause = ""
            if status:
                where_clause = "WHERE status = @status"
                query_parameters.append(
                    bigquery.ScalarQueryParameter("status", "STRING", status)
                )

            query = f"""
            SELECT
                customer_id,
                customer_name,
                gcp_project_id,
                bq_dataset,
                meta_ad_account_ids,
                meta_access_token_secret,
                default_level,
                active_platforms,
                status,
                onboarded_at,
                updated_at,
                usage_tier,
                primary_contact_email,
                tags,
                notes
            FROM `{self.customers_table}`
            {where_clause}
            ORDER BY onboarded_at DESC
            LIMIT @limit
            """

            query_parameters.append(
                bigquery.ScalarQueryParameter("limit", "INT64", limit)
            )

            job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
            rows = bq.client.query(query, job_config=job_config).result()

            return [
                Customer(
                    customer_id=row.customer_id,
                    customer_name=row.customer_name,
                    gcp_project_id=row.gcp_project_id,
                    bq_dataset=row.bq_dataset,
                    meta_ad_account_ids=row.meta_ad_account_ids,
                    meta_access_token_secret=row.meta_access_token_secret,
                    default_level=row.default_level,
                    active_platforms=row.active_platforms,
                    status=row.status,
                    onboarded_at=row.onboarded_at,
                    updated_at=row.updated_at,
                    usage_tier=row.usage_tier,
                    primary_contact_email=row.primary_contact_email,
                    tags=row.tags,
                    notes=row.notes,
                )
                for row in rows
            ]
        except gcp_exceptions.NotFound:
            logger.error(f"Registry table not found: {self.customers_table}")
            return []
        except gcp_exceptions.Forbidden:
            logger.error(f"Access denied to registry: {self.customers_table}")
            return []
        except gcp_exceptions.DeadlineExceeded:
            logger.error("BigQuery query timeout while listing customers")
            return []
        except Exception:
            logger.exception("Unexpected error listing customers from BigQuery")
            return []

    def add_customer(
        self,
        customer_id: str,
        customer_name: str,
        gcp_project_id: str,
        bq_dataset: str = "paid_social",
        meta_ad_account_ids: list[str] | None = None,
        default_level: str = "campaign",
        primary_contact_email: str | None = None,
        tags: list[str] | None = None,
        created_by: str | None = None,
        **kwargs: Any,
    ) -> Customer:
        """
        Add a new customer to the registry.

        Args:
            customer_id: Unique identifier (e.g., 'newclient')
            customer_name: Display name (e.g., 'New Client Inc.')
            gcp_project_id: Customer's GCP project ID
            bq_dataset: BigQuery dataset name
            meta_ad_account_ids: List of Meta ad account IDs
            default_level: Default aggregation level
            primary_contact_email: Primary contact email
            tags: Tags for organization
            created_by: User creating this customer
            **kwargs: Additional fields (usage_tier, notes, etc.)

        Returns:
            Created Customer object
        """
        bq = self._get_bq_client()

        # Prepare insert data
        row = {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "gcp_project_id": gcp_project_id,
            "bq_dataset": bq_dataset,
            "meta_ad_account_ids": meta_ad_account_ids or [],
            "default_level": default_level,
            "active_platforms": ["meta"],
            "status": "active",
            "onboarded_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "primary_contact_email": primary_contact_email,
            "tags": tags or [],
            "created_by": created_by or "system",
        }

        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in row:
                row[key] = value

        # Insert into BigQuery
        errors = bq.client.insert_rows_json(self.customers_table, [row])

        if errors:
            raise ValueError(f"Failed to add customer: {errors}")

        print(f"✓ Customer '{customer_id}' added to registry")

        # Return customer object directly from row data to avoid eventual consistency issues
        # BigQuery streaming inserts have eventual consistency, so get_customer() might not
        # immediately find the newly inserted row
        customer = Customer(
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            gcp_project_id=row["gcp_project_id"],
            bq_dataset=row["bq_dataset"],
            meta_ad_account_ids=row.get("meta_ad_account_ids"),
            default_level=row.get("default_level", "campaign"),
            active_platforms=row.get("active_platforms"),
            status=row.get("status", "active"),
            onboarded_at=datetime.fromisoformat(row["onboarded_at"])
            if isinstance(row["onboarded_at"], str)
            else row["onboarded_at"],
            updated_at=datetime.fromisoformat(row["updated_at"])
            if isinstance(row["updated_at"], str)
            else row["updated_at"],
            usage_tier=row.get("usage_tier", "standard"),
            primary_contact_email=row.get("primary_contact_email"),
            tags=row.get("tags"),
            notes=row.get("notes"),
        )
        return customer

    def _infer_bq_type(self, value: Any) -> str:
        """Infer BigQuery type from Python value."""
        if isinstance(value, bool):
            return "BOOL"
        elif isinstance(value, int):
            return "INT64"
        elif isinstance(value, float):
            return "FLOAT64"
        elif isinstance(value, str):
            return "STRING"
        elif isinstance(value, list):
            return "JSON"
        elif isinstance(value, dict):
            return "JSON"
        else:
            return "STRING"

    def update_customer(
        self, customer_id: str, **updates: Any
    ) -> Customer | None:
        """
        Update customer fields using parameterized queries.

        Args:
            customer_id: Customer to update
            **updates: Fields to update (e.g., status='paused', tags=['new-tag'])

        Returns:
            Updated Customer object
        """
        bq = self._get_bq_client()

        # Build parameterized UPDATE query
        set_clauses = [f"{key} = @{key}" for key in updates.keys()]
        set_clauses.append("updated_at = CURRENT_TIMESTAMP()")

        query = f"""
        UPDATE `{self.customers_table}`
        SET {', '.join(set_clauses)}
        WHERE customer_id = @customer_id
        """

        # Prepare parameters - handle JSON types specially
        import json
        query_parameters = [
            bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id)
        ]

        for key, value in updates.items():
            if isinstance(value, list | dict):
                # Convert to JSON string
                query_parameters.append(
                    bigquery.ScalarQueryParameter(key, "JSON", json.dumps(value))
                )
            else:
                query_parameters.append(
                    bigquery.ScalarQueryParameter(key, self._infer_bq_type(value), value)
                )

        # Create job config with parameters
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)

        bq.client.query(query, job_config=job_config).result()
        print(f"✓ Customer '{customer_id}' updated")

        return self.get_customer(customer_id)


# Global registry instance
_registry: CustomerRegistry | None = None


def get_registry() -> CustomerRegistry:
    """Get the global customer registry instance."""
    global _registry
    if _registry is None:
        _registry = CustomerRegistry()
    return _registry


def get_customer(customer_id: str) -> Customer | None:
    """Convenience function to get customer from registry."""
    return get_registry().get_customer(customer_id)
