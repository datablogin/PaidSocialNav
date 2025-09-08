from __future__ import annotations

from pathlib import Path

import typer

from .. import __version__
from ..audit.engine import run_audit
from ..core.config import get_settings
from ..core.enums import DatePreset, Entity
from ..core.sync import sync_meta_insights
from ..render.renderer import render_markdown, write_text

app = typer.Typer(help="PaidSocialNav CLI")
meta_app = typer.Typer(help="Meta platform commands")
audit_app = typer.Typer(help="Audit and reporting commands")


@app.command()
def version() -> None:
    """Print version."""
    typer.echo(__version__)


@meta_app.command("sync-insights")
def meta_sync_insights(
    account_id: str = typer.Option(..., help="Meta ad account id (act_* or numeric)"),  # noqa: B008
    level: Entity = typer.Option(Entity.AD, case_sensitive=False, help="Insights level: ad|adset|campaign"),  # noqa: B008
    date_preset: DatePreset | None = typer.Option(None, case_sensitive=False, help="Named date window (e.g., yesterday, last_7d). Mutually exclusive with --since/--until"),  # noqa: B008
    since: str | None = typer.Option(None, help="Start date YYYY-MM-DD"),  # noqa: B008
    until: str | None = typer.Option(None, help="End date YYYY-MM-DD"),  # noqa: B008
    tenant: str = typer.Option(None, help="Tenant ID from configs/tenants.yaml to route data to the correct project/dataset"),  # noqa: B008
    use_secret: bool = typer.Option(False, help="Fetch META_ACCESS_TOKEN from the tenant project's Secret Manager"),  # noqa: B008
    secret_name: str = typer.Option("META_ACCESS_TOKEN", help="Secret name to read when --use_secret is set"),  # noqa: B008
    secret_version: str = typer.Option("latest", help="Secret version (default: latest)"),  # noqa: B008
) -> None:
    """Fetch Meta insights via Graph API and load into BigQuery."""
    from ..core.tenants import get_tenant
    settings = get_settings()

    project_id = settings.gcp_project_id
    dataset = settings.bq_dataset

    if tenant:
        t = get_tenant(tenant)
        if not t:
            typer.secho(f"Tenant '{tenant}' not found in configs/tenants.yaml", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        project_id = t.project_id
        dataset = t.dataset

    if not project_id or not dataset:
        typer.secho("Missing GCP project/dataset configuration.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    access_token = settings.meta_access_token
    if use_secret:
        try:
            from ..storage.secrets import access_secret
            access_token = access_secret(project_id=project_id, secret_id=secret_name, version=secret_version)
        except Exception as e:
            typer.secho(f"Failed to read secret '{secret_name}' from project '{project_id}': {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

    if not access_token:
        typer.secho("No Meta access token provided. Set META_ACCESS_TOKEN or use --use-secret.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Validate mutual exclusivity
    if date_preset is not None and (since or until):
        typer.secho("--date-preset cannot be used together with --since/--until", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        summary = sync_meta_insights(
            account_id=account_id,
            project_id=project_id,
            dataset=dataset,
            access_token=access_token,
            level=level,
            date_preset=date_preset,
            since=since,
            until=until,
        )
    except Exception as e:
        typer.secho(f"Sync failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e

    typer.secho(
        f"Loaded {summary['rows']} rows into {project_id}.{dataset}.fct_ad_insights_daily",
        fg=typer.colors.GREEN,
    )


@audit_app.command("run")
def audit_run(
    config: str = typer.Option("configs/sample_audit.yaml", help="Path to audit config YAML"),
    output: str | None = typer.Option(None, help="Optional output path for Markdown report"),
) -> None:
    """Run audit and optionally render a Markdown report (scaffold)."""
    result = run_audit(config)

    # Minimal data mapping for the template
    data = {
        "client": "ACME Retail",
        "period": "Q2 2025",
        "auditor": "PaidSocialNav",
        "overall_score": result.overall_score,
        "strengths": "Strong Instagram engagement; robust retargeting.",
        "weaknesses": "Signal quality; over-skewed to retargeting; limited creative diversity.",
        "opportunities": "Improve CAPI, rebalance spend, refresh creative, test TikTok.",
        "profiles_audited": ["Meta (FB+IG)"],
        "actions": {
            "account_access": "Standardize naming; clean up users.",
            "organic": "Align paid audiences.",
            "structure": "Reallocate to 60/40 and add awareness.",
            "creative": "Increase video share; rotate bi-weekly.",
            "audience": "Add 1–2% LALs; refine exclusions.",
            "tracking": "Implement CAPI; configure full-funnel events.",
            "performance": "Scale winners; pause underperformers.",
            "compliance": "Update consent; set rejection alerts.",
        },
        "roadmap": {
            "quick_wins": "- Fix EMQ with CAPI\n- Standardize naming & access\n- Launch video tests",
            "medium_term": "- Rebalance to 60/40\n- Deploy LAL audiences\n- Refresh creative bi-weekly",
            "long_term": "- Test TikTok prospecting\n- Integrate CRM\n- Automate reporting",
        },
    }

    tmpl_dir = Path(__file__).resolve().parent.parent / "render" / "templates"
    md = render_markdown(tmpl_dir, data)

    if output:
        write_text(output, md)
        typer.echo(f"Report written to {output}")
    else:
        typer.echo(md)


app.add_typer(meta_app, name="meta")
app.add_typer(audit_app, name="audit")

