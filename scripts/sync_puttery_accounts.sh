#!/bin/bash
# Sync Meta insights data for all Puttery ad accounts
# Run with: bash scripts/sync_puttery_accounts.sh

set -e  # Exit on error

# Use the correct psn command
PSN="/Library/Frameworks/Python.framework/Versions/3.12/bin/psn"

# Configuration
TENANT="puttery"
LEVEL="campaign"
DATE_PRESET="last_28d"  # Adjust as needed: yesterday, last_7d, last_14d, last_28d, lifetime

# Puttery ad accounts
ACCOUNTS=(
  "310780304833753"
  "1015958239658171"
  "701821668726593"
  "216607011505526"
)

echo "==================================="
echo "Syncing Puttery Meta Ad Accounts"
echo "==================================="
echo "Tenant: $TENANT"
echo "Level: $LEVEL"
echo "Date Preset: $DATE_PRESET"
echo "Accounts: ${#ACCOUNTS[@]}"
echo ""

# Sync each account
for ACCOUNT_ID in "${ACCOUNTS[@]}"; do
  echo "-----------------------------------"
  echo "Syncing account: $ACCOUNT_ID"
  echo "-----------------------------------"

  "$PSN" meta sync-insights \
    --account-id "$ACCOUNT_ID" \
    --tenant "$TENANT" \
    --level "$LEVEL" \
    --date-preset "$DATE_PRESET" \
    --retries 3 \
    --retry-backoff-seconds 2.0 \
    --page-size 500

  if [ $? -eq 0 ]; then
    echo "✓ Account $ACCOUNT_ID synced successfully"
  else
    echo "✗ Account $ACCOUNT_ID failed to sync"
  fi

  echo ""
done

echo "==================================="
echo "Sync Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Run audit: $PSN skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml"
echo "2. View reports in the reports/ directory"
