from __future__ import annotations

from pathlib import Path

import typer

from .. import __version__
from ..audit.engine import run_audit
from ..core.config import get_settings
from ..core.enums import DatePreset, Entity
from ..core.logging_config import get_logger, setup_logging
from ..core.sync import sync_meta_insights
from ..render.renderer import write_text
from ..skills.audit_workflow import AuditWorkflowSkill
from . import output as cli_output

app = typer.Typer(help="PaidSocialNav CLI")
meta_app = typer.Typer(help="Meta platform commands")
audit_app = typer.Typer(help="Audit and reporting commands")
skills_app = typer.Typer(help="Claude skills automation workflows")

logger = get_logger(__name__)


@app.callback()
def callback(
    json_logs: bool = typer.Option(False, "--json-logs", help="Output logs in JSON format"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
) -> None:
    """Configure global CLI options."""
    setup_logging(json_output=json_logs, log_level=log_level)
    logger.debug("CLI initialized", extra={"json_logs": json_logs, "log_level": log_level})


@app.command()
def version() -> None:
    """Print version."""
    typer.echo(__version__)


@meta_app.command("sync-insights")
def meta_sync_insights(
    account_id: str = typer.Option(..., help="Meta ad account id (act_* or numeric)"),  # noqa: B008
    level: Entity | None = typer.Option(  # noqa: B008
        None,
        case_sensitive=False,
        help="Insights level: ad|adset|campaign (overrides tenant default)",
    ),
    levels: str | None = typer.Option(
        None,
        help=(
            "Comma-separated list of levels to run sequentially (e.g., 'ad,adset,campaign'). "
            "Overrides --level and disables fallback between levels."
        ),
    ),  # noqa: B008
    fallback_levels: bool = typer.Option(
        True,
        help="When a level returns 0 rows, fallback to the next in the order ad→adset→campaign",
    ),  # noqa: B008
    date_preset: DatePreset | None = typer.Option(  # noqa: B008
        None,
        case_sensitive=False,
        help=(
            "Named date window (e.g., yesterday, last_7d, lifetime). If used with --since/--until, "
            "explicit dates take precedence and a warning is shown."
        ),
    ),
    since: str | None = typer.Option(None, help="Start date YYYY-MM-DD"),  # noqa: B008
    until: str | None = typer.Option(None, help="End date YYYY-MM-DD"),  # noqa: B008
    chunk_days: int = typer.Option(
        30, min=1, help="Chunk size in days when total range > 60 days"
    ),  # noqa: B008
    retries: int = typer.Option(
        3, min=0, help="Retry attempts for API/page fetch failures"
    ),  # noqa: B008
    retry_backoff_seconds: float = typer.Option(
        2.0, min=0.0, help="Backoff between retries in seconds"
    ),  # noqa: B008
    rate_limit_rps: float = typer.Option(
        0.0, min=0.0, help="Requests per second rate limit (0 disables)"
    ),  # noqa: B008
    page_size: int = typer.Option(
        500, min=1, max=1000, help="Page size for Meta insights API (default: 500)"
    ),  # noqa: B008
    tenant: str = typer.Option(
        None,
        help=(
            "Tenant ID from configs/tenants.yaml to route data to the correct project/dataset. "
            "Overrides default GCP project/dataset from settings."
        ),
    ),  # noqa: B008
    use_secret: bool = typer.Option(
        False, help="Fetch META_ACCESS_TOKEN from the tenant project's Secret Manager"
    ),  # noqa: B008
    secret_name: str = typer.Option(
        "META_ACCESS_TOKEN", help="Secret name to read when --use_secret is set"
    ),  # noqa: B008
    secret_version: str = typer.Option(
        "latest", help="Secret version (default: latest)"
    ),  # noqa: B008
    breakdowns: str | None = typer.Option(
        None,
        help=(
            "Comma-separated demographic/geographic breakdowns (e.g., 'age,gender' or 'region'). "
            "Supported: age, gender, region, country, publisher_platform, device_platform, placement"
        ),
    ),  # noqa: B008
) -> None:
    """Fetch Meta insights via Graph API and load into BigQuery.

    Validates date formats when provided and supports named date presets. Use --tenant to select a configured
    GCP project/dataset; otherwise, defaults from environment settings are used (see README Configuration section).
    """
    from ..core.tenants import get_tenant

    settings = get_settings()

    project_id = settings.gcp_project_id
    dataset = settings.bq_dataset
    tenant_default_level = None

    if tenant:
        t = get_tenant(tenant)
        if not t:
            cli_output.error(f"Tenant '{tenant}' not found in configs/tenants.yaml")
            raise typer.Exit(code=1)
        project_id = t.project_id
        dataset = t.dataset
        tenant_default_level = t.default_level

    if not project_id or not dataset:
        cli_output.error(
            "Missing GCP project/dataset configuration. Set env vars GCP_PROJECT_ID and BQ_DATASET, "
            "or specify a valid --tenant from configs/tenants.yaml."
        )
        raise typer.Exit(code=1)

    access_token = settings.meta_access_token
    if use_secret:
        try:
            from ..storage.secrets import access_secret

            access_token = access_secret(
                project_id=project_id, secret_id=secret_name, version=secret_version
            )
        except Exception as e:
            logger.exception("Secret access failed", extra={
                "secret_name": secret_name,
                "project_id": project_id,
            })
            cli_output.error(f"Failed to read secret '{secret_name}' from project '{project_id}': {e}")
            raise typer.Exit(code=1) from e

    if not access_token:
        cli_output.error("No Meta access token provided. Set META_ACCESS_TOKEN or use --use-secret.")
        raise typer.Exit(code=1)

    # Date precedence: allow both, prefer explicit since/until with a warning
    if date_preset is not None and (since or until):
        cli_output.warning("--date-preset provided together with --since/--until; explicit dates will be used.")
        date_preset = None

    # Validate date formats if provided
    def _valid_date(d: str) -> bool:
        try:
            from datetime import date as _date

            _date.fromisoformat(d)
            return True
        except Exception:
            return False

    if since and not _valid_date(since):
        cli_output.error("--since must be in YYYY-MM-DD format.")
        raise typer.Exit(code=1)
    if until and not _valid_date(until):
        cli_output.error("--until must be in YYYY-MM-DD format.")
        raise typer.Exit(code=1)

    if since and until and since > until:
        cli_output.error("--since cannot be after --until.")
        raise typer.Exit(code=1)

    # Resolve levels: explicit --levels overrides --level and disables fallback
    parsed_levels: list[Entity] | None = None
    if levels:
        try:
            parts = [p.strip().lower() for p in levels.split(",") if p.strip()]
            parsed_levels = [Entity(p) for p in parts]
        except Exception:
            cli_output.error("Invalid --levels value. Use a comma-separated list of: ad, adset, campaign.")
            raise typer.Exit(code=1) from None

    # Determine effective single-level if --levels not provided
    effective_level = level or tenant_default_level or Entity.AD

    # Parse breakdowns if provided
    breakdown_list = None
    if breakdowns:
        breakdown_list = [b.strip() for b in breakdowns.split(",")]
        cli_output.info(f"Requesting demographic breakdowns: {', '.join(breakdown_list)}")

    try:
        summary = sync_meta_insights(
            account_id=account_id,
            project_id=project_id,
            dataset=dataset,
            access_token=access_token,
            level=effective_level,
            levels=parsed_levels,
            fallback_levels=fallback_levels,
            date_preset=date_preset,
            since=since,
            until=until,
            chunk_days=chunk_days,
            retries=retries,
            retry_backoff=retry_backoff_seconds,
            rate_limit_rps=rate_limit_rps,
            page_size=page_size,
        )
    except Exception as e:
        logger.exception("Meta insights sync failed", extra={
            "account_id": account_id,
            "project_id": project_id,
            "dataset": dataset,
        })
        cli_output.error(f"Sync failed: {e}")
        raise typer.Exit(code=1) from e

    cli_output.success(f"Loaded {summary['rows']} rows into {project_id}.{dataset}.fct_ad_insights_daily")


@meta_app.command("sync-dimensions")
def meta_sync_dimensions(
    account_id: str = typer.Option(..., help="Meta ad account id (act_* or numeric)"),  # noqa: B008
    tenant: str = typer.Option(
        None,
        help=(
            "Tenant ID from configs/tenants.yaml to route data to the correct project/dataset. "
            "Overrides default GCP project/dataset from settings."
        ),
    ),  # noqa: B008
    use_secret: bool = typer.Option(
        False, help="Fetch META_ACCESS_TOKEN from the tenant project's Secret Manager"
    ),  # noqa: B008
    secret_name: str = typer.Option(
        "META_ACCESS_TOKEN", help="Secret name to read when --use_secret is set"
    ),  # noqa: B008
    secret_version: str = typer.Option(
        "latest", help="Secret version (default: latest)"
    ),  # noqa: B008
    page_size: int = typer.Option(
        500, min=1, max=1000, help="Page size for Meta API requests (default: 500)"
    ),  # noqa: B008
    retries: int = typer.Option(
        3, min=0, help="Retry attempts for API failures"
    ),  # noqa: B008
    retry_backoff_seconds: float = typer.Option(
        2.0, min=0.0, help="Backoff between retries in seconds"
    ),  # noqa: B008
) -> None:
    """Fetch Meta dimension data (account/campaign/adset/ad/creative) and load into BigQuery.

    This command pulls dimension data from Meta Graph API and upserts it into BigQuery dimension tables.
    Use --tenant to select a configured GCP project/dataset; otherwise, defaults from environment settings are used.

    Example:
        psn meta sync-dimensions --tenant fleming --use-secret --account-id act_123456789
    """
    from ..core.tenants import get_tenant
    from ..adapters.meta.dimensions import sync_all_dimensions

    settings = get_settings()

    project_id = settings.gcp_project_id
    dataset = settings.bq_dataset

    if tenant:
        t = get_tenant(tenant)
        if not t:
            cli_output.error(f"Tenant '{tenant}' not found in configs/tenants.yaml")
            raise typer.Exit(code=1)
        project_id = t.project_id
        dataset = t.dataset

    if not project_id or not dataset:
        cli_output.error(
            "Missing GCP project/dataset configuration. Set env vars GCP_PROJECT_ID and BQ_DATASET, "
            "or specify a valid --tenant from configs/tenants.yaml."
        )
        raise typer.Exit(code=1)

    access_token = settings.meta_access_token
    if use_secret:
        try:
            from ..storage.secrets import access_secret

            access_token = access_secret(
                project_id=project_id, secret_id=secret_name, version=secret_version
            )
        except Exception as e:
            logger.exception("Secret access failed", extra={
                "secret_name": secret_name,
                "project_id": project_id,
            })
            cli_output.error(f"Failed to read secret '{secret_name}' from project '{project_id}': {e}")
            raise typer.Exit(code=1) from e

    if not access_token:
        cli_output.error("No Meta access token provided. Set META_ACCESS_TOKEN or use --use-secret.")
        raise typer.Exit(code=1)

    try:
        counts = sync_all_dimensions(
            account_id=account_id,
            project_id=project_id,
            dataset=dataset,
            access_token=access_token,
            page_size=page_size,
            retries=retries,
            retry_backoff=retry_backoff_seconds,
        )
    except Exception as e:
        logger.exception("Dimension sync failed", extra={
            "account_id": account_id,
            "project_id": project_id,
            "dataset": dataset,
        })
        cli_output.error(f"Dimension sync failed: {e}")
        raise typer.Exit(code=1) from e

    cli_output.success("Dimension sync completed successfully!")
    cli_output.info(f"Records synced to {project_id}.{dataset}:")
    cli_output.plain(f"  - Accounts: {counts['account']}")
    cli_output.plain(f"  - Campaigns: {counts['campaigns']}")
    cli_output.plain(f"  - Ad Sets: {counts['adsets']}")
    cli_output.plain(f"  - Ads: {counts['ads']}")
    cli_output.plain(f"  - Creatives: {counts['creatives']}")


@audit_app.command("run")
def audit_run(
    config: str = typer.Option(
        "configs/sample_audit.yaml", help="Path to audit config YAML"
    ),
    output: str | None = typer.Option(
        None, help="Optional output path for Markdown report"
    ),
    html_output: str | None = typer.Option(
        None, help="Optional output path for HTML report"
    ),
    pdf_output: str | None = typer.Option(
        None, help="Optional output path for PDF report"
    ),
    format: str = typer.Option(
        "md",
        help="Output format(s): md, html, pdf, or comma-separated (e.g., 'md,pdf')",
    ),
    upload: str | None = typer.Option(
        None, help="Optional GCS upload URI (e.g., 'gs://bucket/prefix/report.pdf')"
    ),
    assets_dir: str | None = typer.Option(
        None,
        help="Optional directory to save chart images (e.g., 'reports/assets' or 'gs://bucket/prefix')",
    ),
) -> None:
    """Run audit and optionally render Markdown, HTML, and/or PDF reports with optional visuals."""
    from datetime import datetime

    import yaml

    from ..render.renderer import ReportRenderer
    from ..render.pdf import write_pdf
    from ..storage.gcs import upload_file_to_gcs

    # Load tenant name and windows from config first
    try:
        cfg = yaml.safe_load(Path(config).read_text())
    except FileNotFoundError:
        cli_output.error(f"Config file not found: {config}")
        raise typer.Exit(code=1) from None
    except yaml.YAMLError as e:
        cli_output.error(f"Invalid YAML in config: {e}")
        raise typer.Exit(code=1) from None

    tenant_name = cfg.get("tenant", "Client")
    windows = cfg.get("windows", [])

    # Calculate period from windows
    if windows and isinstance(windows, list) and len(windows) > 0:
        # Filter out any None or empty string values
        valid_windows = [w for w in windows if w]
        if valid_windows:
            period = ", ".join(str(w) for w in valid_windows)
        else:
            period = datetime.now().strftime("%Y")
    else:
        period = datetime.now().strftime("%Y")

    # 1. Log start of audit
    logger.info("Starting audit", extra={
        "tenant": tenant_name,
        "config": config,
        "output": output,
    })

    # 2. Log after config load
    logger.info("Audit config loaded", extra={
        "tenant": tenant_name,
        "windows": windows,
        "period": period,
    })

    # 3. Log before audit execution
    logger.info("Executing audit", extra={
        "tenant": tenant_name,
    })

    # Run audit with error handling
    try:
        result = run_audit(config)
    except RuntimeError as e:
        # BigQuery or other runtime errors
        cli_output.error(f"Audit failed: {e}")
        raise typer.Exit(code=1) from None
    except Exception as e:
        # Unexpected errors
        logger.exception("Unexpected error during audit", extra={
            "config": config,
        })
        cli_output.error(f"Unexpected error during audit: {e}")
        raise typer.Exit(code=1) from None

    # 4. Log after audit completion
    logger.info("Audit completed", extra={
        "tenant": tenant_name,
        "score": result.overall_score,
        "rules_count": len(result.rules),
    })

    # Prepare data for template
    data = {
        "tenant_name": tenant_name,
        "period": period,
        "audit_date": datetime.now().strftime("%Y-%m-%d"),
        "overall_score": result.overall_score,
        "rules": result.rules,
        "recommendations": [],  # Phase 4 will populate with AI insights
    }

    # Initialize renderer with assets directory if provided
    assets_path = Path(assets_dir) if assets_dir else None
    renderer = ReportRenderer(assets_dir=assets_path)

    # Parse format string
    formats = [f.strip().lower() for f in format.split(",")]

    # Generate Markdown if requested (via --output or --format)
    if output or "md" in formats:
        md = renderer.render_markdown(data)
        if output:
            write_text(output, md)
            cli_output.success(f"Report written to {output}")
            # 5a. Log Markdown report generation
            logger.info("Markdown report generated", extra={
                "tenant": tenant_name,
                "markdown_path": output,
            })
        elif "md" in formats and not html_output and not pdf_output:
            # Output to console if --format md but no explicit output path
            typer.echo(md)
        if assets_dir and output:
            cli_output.info(f"Chart images saved to {assets_dir}")

    # Generate HTML if requested (via --html-output or --format)
    if html_output or "html" in formats:
        html = renderer.render_html(data)
        html_path = html_output or f"{tenant_name}_audit_{datetime.now().strftime('%Y%m%d')}.html"
        write_text(html_path, html)
        cli_output.success(f"Report written to {html_path}")
        # 5b. Log HTML report generation
        logger.info("HTML report generated", extra={
            "tenant": tenant_name,
            "html_path": html_path,
        })
        if assets_dir:
            cli_output.info(f"Chart images saved to {assets_dir}")

    # Generate PDF if requested (via --pdf-output or --format)
    if pdf_output or "pdf" in formats:
        try:
            pdf_bytes = renderer.render_pdf(data)
            pdf_path = pdf_output or f"{tenant_name}_audit_{datetime.now().strftime('%Y%m%d')}.pdf"
            write_pdf(pdf_path, pdf_bytes)
            cli_output.success(f"Report written to {pdf_path}")
            # 5c. Log PDF report generation
            logger.info("PDF report generated", extra={
                "tenant": tenant_name,
                "pdf_path": pdf_path,
            })

            # Upload to GCS if requested
            if upload:
                try:
                    gcs_url = upload_file_to_gcs(
                        gcs_uri=upload,
                        content_bytes=pdf_bytes,
                        content_type="application/pdf",
                        make_public=False,
                    )
                    cli_output.success(f"PDF uploaded to: {gcs_url}")
                    # 5d. Log GCS upload
                    logger.info("PDF uploaded to GCS", extra={
                        "tenant": tenant_name,
                        "gcs_url": gcs_url,
                    })
                except (ValueError, RuntimeError) as e:
                    cli_output.error(f"Failed to upload to GCS: {e}")
                    raise typer.Exit(code=1) from None

        except RuntimeError as e:
            cli_output.error(f"PDF generation failed: {e}")
            cli_output.warning("Ensure WeasyPrint is properly installed. See docs/pdf-export.md for instructions.")
            raise typer.Exit(code=1) from None

    # If no outputs specified, output Markdown to console
    if not output and not html_output and not pdf_output and not formats:
        renderer_console = ReportRenderer(assets_dir=None)
        md = renderer_console.render_markdown(data)
        typer.echo(md)


@skills_app.command("audit")
def run_audit_skill(
    tenant_id: str = typer.Option(..., help="Tenant identifier from configs/tenants.yaml"),
    audit_config: str = typer.Option(..., help="Path to audit YAML config"),
    output_dir: str = typer.Option("reports/", help="Output directory for reports"),
    format: str = typer.Option(
        "md,html",
        help="Output format(s): md, html, pdf, or comma-separated (e.g., 'md,html,pdf')",
    ),
    upload: str | None = typer.Option(
        None, help="Optional GCS upload URI for PDF (e.g., 'gs://bucket/prefix/report.pdf')"
    ),
    assets_dir: str | None = typer.Option(
        None,
        help="Optional directory to save chart images (e.g., 'reports/assets')",
    ),
    sheets_output: bool = typer.Option(
        False,
        "--sheets-output",
        help="Export audit data to Google Sheets (requires GOOGLE_APPLICATION_CREDENTIALS)",
    ),
) -> None:
    """Run complete audit workflow using Claude skills orchestration.

    This command orchestrates the entire audit process:
    - Validates tenant configuration
    - Runs audit analysis with weighted scoring
    - Generates professional Markdown, HTML, and/or PDF reports with visuals and evidence appendix
    - Optionally exports data to Google Sheets for drill-down analysis
    - Optionally uploads PDF to Google Cloud Storage
    - Saves all outputs to the specified directory

    Examples:
        psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml
        psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml --format md,html,pdf
        psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml --format pdf --upload gs://bucket/audits/report.pdf
    """
    skill = AuditWorkflowSkill()

    # Parse formats
    formats = [f.strip().lower() for f in format.split(",")]

    context = {
        "tenant_id": tenant_id,
        "audit_config": audit_config,
        "output_dir": output_dir,
        "formats": formats,
        "sheets_output": sheets_output,
    }

    if assets_dir:
        context["assets_dir"] = assets_dir

    if upload:
        context["gcs_upload_uri"] = upload

    result = skill.execute(context)

    if result.success:
        cli_output.success(result.message)
        cli_output.plain("\nReports generated:")
        cli_output.plain(f"  Markdown: {result.data['markdown_report']}")
        cli_output.plain(f"  HTML: {result.data['html_report']}")

        if "pdf_report" in result.data:
            cli_output.plain(f"  PDF: {result.data['pdf_report']}")

        if "pdf_gcs_url" in result.data:
            cli_output.plain(f"  PDF (GCS): {result.data['pdf_gcs_url']}")

        if result.data.get("sheet_url"):
            typer.echo("")  # Blank line
            cli_output.data("Google Sheets:")
            cli_output.plain(f"  {result.data['sheet_url']}")
    else:
        cli_output.error(result.message)
        raise typer.Exit(code=1)


app.add_typer(meta_app, name="meta")
app.add_typer(audit_app, name="audit")
app.add_typer(skills_app, name="skills")
