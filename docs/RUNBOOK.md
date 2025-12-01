# PaidSocialNav MCP Server Operational Runbook

**Version**: 0.1.0
**Last Updated**: 2025-11-24
**Service**: PaidSocialNav MCP Server
**Team**: Platform Engineering

---

## Table of Contents

1. [Service Overview](#service-overview)
2. [Health Checks](#health-checks)
3. [Common Issues](#common-issues)
4. [Deployment Procedures](#deployment-procedures)
5. [Rollback Procedures](#rollback-procedures)
6. [Monitoring](#monitoring)
7. [Alerts](#alerts)
8. [Useful Commands](#useful-commands)
9. [Emergency Contacts](#emergency-contacts)

---

## Service Overview

### What is the MCP Server?

The PaidSocialNav MCP Server is a FastMCP-based service that exposes paid social media advertising audit capabilities to AI assistants (Claude, etc.) via the Model Context Protocol. It runs on Google Cloud Run with OAuth authentication.

### Architecture

```
AI Clients (Claude)
    ↓ MCP Protocol
Cloud Run (paidsocialnav-mcp)
    ↓
FastMCP Server (mcp_server/server.py)
    ↓
PaidSocialNav Core (paid_social_nav/)
    ↓
BigQuery + Meta Graph API
```

### Key Components

- **Transport**: HTTP (Cloud Run) or STDIO (local development)
- **Authentication**: Google OAuth (production) or None (local)
- **Tools**: 4 core tools (meta_sync_insights, audit_workflow, get_tenant_config, load_benchmarks)
- **Resources**: 2 resources (tenant list, campaign insights)
- **Prompts**: 3 prompts (analyze_campaign_performance, audit_setup_wizard, data_sync_planner)

### Service Endpoints

- **Service URL**: `https://paidsocialnav-mcp-xxxxx-uc.a.run.app`
- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics`
- **MCP Endpoint**: `POST /mcp` (requires authentication)

---

## Health Checks

### Basic Health Check

```bash
# Check if service is responding
curl https://paidsocialnav-mcp-xxxxx-uc.a.run.app/health
# Expected: {"status":"healthy","service":"PaidSocialNav MCP Server"}
```

### Authenticated Health Check

```bash
# Via authenticated proxy
gcloud run services proxy paidsocialnav-mcp --region=us-central1 --port=8080
curl http://localhost:8080/health
```

### Metrics Check

```bash
# Check metrics endpoint
curl http://localhost:8080/metrics
# Expected: JSON with tool_calls, errors, latencies
```

### What to Look For

✅ **Healthy**:
- `/health` returns 200 status
- Response includes `"status":"healthy"`
- `/metrics` returns valid JSON

❌ **Unhealthy**:
- 503 Service Unavailable
- Timeout errors
- Empty or malformed responses

---

## Common Issues

### Issue 1: Service Returns 503 (Service Unavailable)

**Symptoms**: Claude or MCP clients receive 503 errors when calling tools

**Likely Causes**:
1. Service scaled to zero and cold start timeout
2. All instances crashed or unhealthy
3. Deployment in progress

**Resolution**:

```bash
# Check service status
gcloud run services describe paidsocialnav-mcp \
  --region=us-central1 \
  --format='value(status.conditions)'

# Check recent logs for errors
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=paidsocialnav-mcp" \
  --limit=50 \
  --format=json

# If service scaled to zero, trigger a request to wake it up
curl https://paidsocialnav-mcp-xxxxx-uc.a.run.app/health

# If instances crashed, check for recent deployment issues
gcloud run revisions list --service=paidsocialnav-mcp --region=us-central1
```

**Prevention**: Increase min instances if frequent cold starts are problematic

---

### Issue 2: Authentication Failures

**Symptoms**: "Authentication failed" errors, 401/403 responses

**Likely Causes**:
1. Invalid OAuth credentials
2. Expired access tokens
3. Missing GOOGLE_CLIENT_SECRET

**Resolution**:

```bash
# Check that secrets are properly mounted
gcloud run services describe paidsocialnav-mcp \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)'

# Verify secret values exist
gcloud secrets versions access latest --secret=MCP_GOOGLE_CLIENT_SECRET

# Update secret if needed
echo -n "new-secret-value" | gcloud secrets versions add MCP_GOOGLE_CLIENT_SECRET --data-file=-

# Redeploy to pick up new secret
bash scripts/deploy_cloud_run.sh
```

**Prevention**: Set up monitoring alerts for 401/403 error spikes

---

### Issue 3: BigQuery Errors

**Symptoms**: Tools return "external_service_error", timeouts

**Likely Causes**:
1. BigQuery query timeout (>60s)
2. Missing IAM permissions
3. Table not found

**Resolution**:

```bash
# Check service account permissions
gcloud projects get-iam-policy PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:paidsocialnav-sa@*"

# Verify table exists
bq ls --project_id=PROJECT_ID DATASET

# Check recent BigQuery jobs
bq ls --jobs --max_results=10 --project_id=PROJECT_ID

# Test query manually
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) FROM `PROJECT_ID.DATASET.fct_ad_insights_daily`'
```

**Prevention**: Optimize slow queries, add query result caching

---

### Issue 4: Rate Limiting

**Symptoms**: "Rate limit exceeded. Retry after X seconds"

**Likely Causes**:
1. Client making >60 requests/minute
2. Abuse or misconfigured automation

**Resolution**:

```bash
# Check metrics to see which tenant is rate limited
curl http://localhost:8080/metrics | jq '.errors'

# Review logs for specific tenant
gcloud logging read "resource.type=cloud_run_revision \
  AND jsonPayload.tenant_id=TENANT_ID" \
  --limit=100

# If legitimate traffic spike, consider increasing limit in mcp_server/rate_limiting.py
```

**Prevention**: Educate users on rate limits, implement backoff in clients

---

### Issue 5: High Memory Usage

**Symptoms**: Service restarts, OOMKilled in logs

**Likely Causes**:
1. Large query results not paginated
2. Memory leak in dependencies
3. Insufficient memory allocation

**Resolution**:

```bash
# Check current memory allocation
gcloud run services describe paidsocialnav-mcp \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].resources.limits.memory)'

# Increase memory if needed (currently 2Gi)
gcloud run services update paidsocialnav-mcp \
  --region=us-central1 \
  --memory=4Gi

# Check metrics for memory trends
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/container/memory/utilizations"'
```

**Prevention**: Implement pagination for large result sets, profile memory usage

---

## Deployment Procedures

### Standard Deployment

```bash
# 1. Ensure you're on the correct branch
git checkout main
git pull origin main

# 2. Run tests locally
pytest tests/ -v

# 3. Deploy to Cloud Run
bash scripts/deploy_cloud_run.sh

# 4. Verify deployment
gcloud run services describe paidsocialnav-mcp \
  --region=us-central1 \
  --format='value(status.latestReadyRevisionName)'

# 5. Test the new revision
gcloud run services proxy paidsocialnav-mcp --region=us-central1 --port=8080 &
curl http://localhost:8080/health
python scripts/test_remote_mcp.py
```

### Blue-Green Deployment

```bash
# 1. Deploy new revision with tag (no traffic)
gcloud run deploy paidsocialnav-mcp \
  --region=us-central1 \
  --image=gcr.io/PROJECT_ID/paidsocialnav-mcp:NEW_TAG \
  --no-traffic \
  --tag=blue

# 2. Test blue revision
gcloud run services proxy paidsocialnav-mcp --region=us-central1 --tag=blue --port=8081 &
curl http://localhost:8081/health

# 3. Gradually shift traffic
gcloud run services update-traffic paidsocialnav-mcp \
  --region=us-central1 \
  --to-revisions=blue=10

# 4. Monitor for 10 minutes, then shift 50%, then 100%
gcloud run services update-traffic paidsocialnav-mcp \
  --region=us-central1 \
  --to-latest
```

---

## Rollback Procedures

### Quick Rollback (Last Known Good)

```bash
# 1. List recent revisions
gcloud run revisions list --service=paidsocialnav-mcp --region=us-central1

# 2. Identify last known good revision (e.g., paidsocialnav-mcp-00042-abc)
GOOD_REVISION="paidsocialnav-mcp-00042-abc"

# 3. Rollback by sending 100% traffic to that revision
gcloud run services update-traffic paidsocialnav-mcp \
  --region=us-central1 \
  --to-revisions=$GOOD_REVISION=100

# 4. Verify rollback
curl https://paidsocialnav-mcp-xxxxx-uc.a.run.app/health
```

### Emergency Rollback (Delete Bad Revision)

```bash
# 1. Identify bad revision
BAD_REVISION="paidsocialnav-mcp-00043-xyz"

# 2. Shift traffic away first
gcloud run services update-traffic paidsocialnav-mcp \
  --region=us-central1 \
  --to-revisions=paidsocialnav-mcp-00042-abc=100

# 3. Delete bad revision
gcloud run revisions delete $BAD_REVISION --region=us-central1 --quiet

# 4. Investigate what went wrong
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.revision_name=$BAD_REVISION" \
  --limit=100
```

---

## Monitoring

### Key Metrics to Monitor

1. **Request Rate**: Requests per second to `/mcp` endpoint
2. **Error Rate**: Percentage of 5xx responses
3. **Latency**: p50, p95, p99 response times
4. **Tool Call Success Rate**: Success/failure ratio per tool
5. **Memory Usage**: Container memory utilization
6. **CPU Usage**: Container CPU utilization
7. **Instance Count**: Number of active instances

### Viewing Metrics

```bash
# Tool call metrics
curl http://localhost:8080/metrics | jq '.tool_calls'

# Cloud Run metrics dashboard
gcloud run services describe paidsocialnav-mcp \
  --region=us-central1 \
  --format='value(status.url)'
# Then visit: https://console.cloud.google.com/run/detail/us-central1/paidsocialnav-mcp/metrics

# Query specific metrics
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count"' \
  --format=json
```

### Log Queries

```bash
# All errors in last hour
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=paidsocialnav-mcp \
  AND severity>=ERROR \
  AND timestamp>=\"$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)\"" \
  --limit=100

# Slow requests (>5s)
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=paidsocialnav-mcp \
  AND httpRequest.latency>\"5s\"" \
  --limit=50

# Tool-specific errors
gcloud logging read "resource.type=cloud_run_revision \
  AND jsonPayload.tool=meta_sync_insights \
  AND severity>=ERROR" \
  --limit=50
```

---

## Alerts

### Recommended Alerts

1. **High Error Rate**: Error rate >5% for 5 minutes
2. **Service Down**: Health check failures for 2 consecutive checks
3. **High Latency**: p95 latency >10s for 5 minutes
4. **Memory Pressure**: Memory usage >80% for 10 minutes
5. **Tool Failures**: Tool call failure rate >10% for 5 minutes

### Creating Alerts (Example)

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="MCP Server High Error Rate" \
  --condition-display-name="Error rate >5%" \
  --condition-threshold-value=0.05 \
  --condition-threshold-duration=300s \
  --condition-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="paidsocialnav-mcp" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class="5xx"'
```

---

## Useful Commands

### Service Management

```bash
# Start service (if min instances = 0, will start on first request)
curl https://paidsocialnav-mcp-xxxxx-uc.a.run.app/health

# Stop service (delete service - use with caution!)
gcloud run services delete paidsocialnav-mcp --region=us-central1

# Scale instances
gcloud run services update paidsocialnav-mcp \
  --region=us-central1 \
  --min-instances=1 \
  --max-instances=10

# Update environment variables
gcloud run services update paidsocialnav-mcp \
  --region=us-central1 \
  --set-env-vars="MCP_TRANSPORT=http,NEW_VAR=value"
```

### Secret Management

```bash
# List secrets
gcloud secrets list

# Update secret
echo -n "new-value" | gcloud secrets versions add SECRET_NAME --data-file=-

# View secret access history
gcloud secrets versions list SECRET_NAME

# Grant service account access to secret
gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member=serviceAccount:paidsocialnav-sa@PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### Debugging

```bash
# SSH into a running container (if possible)
gcloud run services exec paidsocialnav-mcp --region=us-central1 -- /bin/bash

# Stream logs in real-time
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=paidsocialnav-mcp"

# Check service account permissions
gcloud iam service-accounts get-iam-policy paidsocialnav-sa@PROJECT_ID.iam.gserviceaccount.com

# Test tool locally via proxy
gcloud run services proxy paidsocialnav-mcp --region=us-central1 --port=8080 &
python scripts/test_remote_mcp.py
```

---

## Emergency Contacts

- **Primary On-Call**: Platform Engineering Team
- **Secondary**: DevOps Team
- **Escalation**: Engineering Manager

### Incident Response

1. **Assess Impact**: How many users affected? Is service completely down?
2. **Communicate**: Post in #incidents Slack channel
3. **Mitigate**: Follow rollback procedures if needed
4. **Investigate**: Check logs, metrics, recent deployments
5. **Resolve**: Deploy fix or rollback to last known good
6. **Post-Mortem**: Document incident, root cause, action items

---

## Change Log

- **2025-11-24**: Initial version (Phase 3 of MCP implementation)

---

## Related Documentation

- [MCP User Guide](MCP_USER_GUIDE.md)
- [MCP API Reference](MCP_API_REFERENCE.md)
- [Architecture Documentation](ARCHITECTURE.md)
- [Security Documentation](SECURITY.md)
