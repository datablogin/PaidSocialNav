#!/usr/bin/env python3
"""Test Meta app permissions using GOLF_* credentials from .env"""

import os
import sys
from pathlib import Path

import requests


def load_dotenv(path: str = ".env") -> None:
    """Load environment variables from .env file."""
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)


def test_permission(access_token: str, permission: str, endpoint: str, params: dict = None) -> dict:
    """Test a specific Meta API endpoint to verify permission."""
    if params is None:
        params = {}

    params["access_token"] = access_token

    try:
        response = requests.get(endpoint, params=params, timeout=10)

        if response.status_code == 200:
            return {
                "permission": permission,
                "status": "SUCCESS",
                "message": "Permission granted and working",
                "data_sample": str(response.json())[:200]
            }
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
            return {
                "permission": permission,
                "status": "FAILED",
                "message": f"HTTP {response.status_code}",
                "error": error_data
            }
    except Exception as e:
        return {
            "permission": permission,
            "status": "ERROR",
            "message": str(e)
        }


def main():
    # Load .env file from project root
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    load_dotenv(str(env_path))

    # Get GOLF credentials
    app_id = os.getenv("GOLF_META_APP_ID")
    access_token = os.getenv("GOLF_META_ACCESS_TOKEN")
    account_id = os.getenv("GOLF_META_ACCOUNT_PUTTERY")

    if not all([app_id, access_token, account_id]):
        print("Error: Missing GOLF_* credentials in .env")
        print(f"  GOLF_META_APP_ID: {'SET' if app_id else 'MISSING'}")
        print(f"  GOLF_META_ACCESS_TOKEN: {'SET' if access_token else 'MISSING'}")
        print(f"  GOLF_META_ACCOUNT_PUTTERY: {'SET' if account_id else 'MISSING'}")
        sys.exit(1)

    print("=" * 80)
    print("Meta App Permissions Test")
    print("=" * 80)
    print(f"App ID: {app_id}")
    print(f"Account ID: {account_id}")
    print(f"Access Token: {access_token[:20]}...")
    print("=" * 80)
    print()

    # Base URL for Meta Graph API
    base_url = "https://graph.facebook.com/v18.0"

    # Test each permission with appropriate endpoint
    tests = [
        {
            "permission": "ads_management",
            "description": "Ability to manage ad campaigns",
            "endpoint": f"{base_url}/{account_id}",
            "params": {"fields": "name,account_status,currency"}
        },
        {
            "permission": "ads_read",
            "description": "Read ad account data",
            "endpoint": f"{base_url}/{account_id}/campaigns",
            "params": {"fields": "id,name,status", "limit": "5"}
        },
        {
            "permission": "business_management",
            "description": "Manage business assets",
            "endpoint": f"{base_url}/me/businesses",
            "params": {"fields": "id,name"}
        },
        {
            "permission": "leads_retrieval",
            "description": "Retrieve lead forms data",
            "endpoint": f"{base_url}/me/accounts",
            "params": {"fields": "leadgen_forms{id,name}", "limit": "5"}
        },
        {
            "permission": "pages_read_engagement",
            "description": "Read Page engagement data",
            "endpoint": f"{base_url}/me/accounts",
            "params": {"fields": "id,name,access_token"}
        },
        {
            "permission": "pages_manage_ads",
            "description": "Manage ads for Pages",
            "endpoint": f"{base_url}/me/accounts",
            "params": {"fields": "id,name,access_token"}
        }
    ]

    results = []
    for test in tests:
        print(f"Testing: {test['permission']}")
        print(f"  Description: {test['description']}")
        print(f"  Endpoint: {test['endpoint']}")

        result = test_permission(
            access_token=access_token,
            permission=test['permission'],
            endpoint=test['endpoint'],
            params=test['params']
        )

        results.append(result)

        if result['status'] == 'SUCCESS':
            print(f"  Status: ✓ {result['status']}")
            print(f"  Message: {result['message']}")
        else:
            print(f"  Status: ✗ {result['status']}")
            print(f"  Message: {result['message']}")
            if 'error' in result:
                print(f"  Error: {result['error']}")

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    failed_count = sum(1 for r in results if r['status'] == 'FAILED')
    error_count = sum(1 for r in results if r['status'] == 'ERROR')

    print(f"Total permissions tested: {len(results)}")
    print(f"  ✓ Success: {success_count}")
    print(f"  ✗ Failed: {failed_count}")
    print(f"  ⚠ Error: {error_count}")
    print()

    if success_count == len(results):
        print("All permissions are working correctly!")
        return 0
    else:
        print("Some permissions are not working. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
