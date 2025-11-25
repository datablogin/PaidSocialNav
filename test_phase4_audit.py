#!/usr/bin/env python3
"""Test script for Phase 4 audit with Claude API."""
import os
import sys

from paid_social_nav.skills.audit_workflow import AuditWorkflowSkill

# API key should be set via environment variable ANTHROPIC_API_KEY
# Example: export ANTHROPIC_API_KEY="your-key-here"
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("Error: ANTHROPIC_API_KEY environment variable not set")
    print("Usage: export ANTHROPIC_API_KEY='your-key' && python test_phase4_audit.py")
    sys.exit(1)

print("Testing Phase 4 audit workflow with Claude API...")
print(f"API key set: {os.environ.get('ANTHROPIC_API_KEY')[:10]}...")

# Create skill instance
skill = AuditWorkflowSkill()

# Execute audit
context = {
    "tenant_id": "puttery",
    "audit_config": "configs/audit_puttery_18mo.yaml",
    "output_dir": "reports/phase4_final_test"
}

print("\nExecuting audit with context:")
print(f"  Tenant: {context['tenant_id']}")
print(f"  Config: {context['audit_config']}")
print(f"  Output: {context['output_dir']}")

result = skill.execute(context)

print(f"\n{'='*60}")
if result.success:
    print(f"✅ {result.message}")
    print("\nGenerated reports:")
    print(f"  Markdown: {result.data.get('markdown_report')}")
    print(f"  HTML: {result.data.get('html_report')}")
    print(f"  Audit Score: {result.data.get('audit_score')}/100")
    sys.exit(0)
else:
    print(f"❌ {result.message}")
    sys.exit(1)
