#!/usr/bin/env python3
"""
Test script for Phase 4: Real audit with Claude API insights
Run with: python3 test_phase4_real.py
"""
import os
import time
from paid_social_nav.skills.audit_workflow import AuditWorkflowSkill

# Set API key from environment
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("⚠️  ANTHROPIC_API_KEY not set - insights will be empty")
else:
    print(f"✓ ANTHROPIC_API_KEY is set (length: {len(api_key)})")

# Configure the audit
context = {
    "tenant_id": "puttery",
    "audit_config": "configs/audit_puttery_18mo.yaml",
    "output_dir": "reports/puttery_18mo_real"
}

print("\n" + "="*60)
print("Phase 4 Real Audit Test - 18 Months Puttery Data")
print("="*60)
print("\nConfiguration:")
print(f"  Tenant: {context['tenant_id']}")
print(f"  Config: {context['audit_config']}")
print(f"  Output: {context['output_dir']}")
print(f"  Claude API: {'Enabled' if api_key else 'Disabled'}")
print("\nStarting audit...")

# Run the audit
skill = AuditWorkflowSkill()
start = time.time()

try:
    result = skill.execute(context)
    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"Audit completed in {elapsed:.2f} seconds")
    print(f"{'='*60}")

    if result.success:
        print(f"\n✅ Success: {result.message}")
        print("\nReports generated:")
        print(f"  📄 Markdown: {result.data.get('markdown_report')}")
        print(f"  🌐 HTML: {result.data.get('html_report')}")
        print(f"\nYou can now review the reports in {context['output_dir']}/")
    else:
        print(f"\n❌ Failed: {result.message}")
        exit(1)

except Exception as e:
    elapsed = time.time() - start
    print(f"\n❌ Error after {elapsed:.2f} seconds: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
