import os
import re
import subprocess

import pytest
from typer.testing import CliRunner

from paid_social_nav.cli.main import app

INTEGRATION = os.getenv("PSN_INTEGRATION") == "1"
PROJECT = os.getenv("GCP_PROJECT_ID", "fleming-424413")
DATASET = os.getenv("BQ_DATASET", "paid_social")
META_ACCOUNT_ID = os.getenv("META_ACCOUNT_ID")

pytestmark = pytest.mark.skipif(
    not INTEGRATION or not META_ACCOUNT_ID,
    reason="Integration test requires PSN_INTEGRATION=1 and META_ACCOUNT_ID set",
)


def _norm_act(account_id: str) -> str:
    return account_id if account_id.startswith("act_") else f"act_{account_id}"


def test_meta_insights_e2e_loads_rows(monkeypatch):
    # Ensure META_ACCESS_TOKEN is available to CLI via settings
    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        pytest.skip("META_ACCESS_TOKEN not set")

    account_id = _norm_act(META_ACCOUNT_ID)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "meta",
            "sync-insights",
            "--account-id",
            account_id,
            "--level",
            "ad",
            "--since",
            "2025-04-29",
            "--until",
            "2025-05-31",
            "--tenant",
            "fleming",
            "--page-size",
            "200",
        ],
        env={
            **os.environ,
            # surface token to settings
            "META_ACCESS_TOKEN": token,
        },
    )

    assert result.exit_code == 0
    m = re.search(r"Loaded\s+(\d+)\s+rows\s+into\s+", result.stdout)
    assert m, f"No load summary found in output: {result.stdout}"
    rows = int(m.group(1))
    assert rows > 0, f"Expected >0 rows loaded, got {rows}. Output: {result.stdout}"

    # Validate presence in BigQuery using bq CLI
    sql = (
        f"SELECT COUNT(*) FROM `{PROJECT}.{DATASET}.fct_ad_insights_daily` "
        f"WHERE date BETWEEN '2025-04-29' AND '2025-05-31' "
        f"AND account_global_id='meta:account:{account_id}'"
    )
    out = subprocess.check_output(
        [
            "bq",
            "query",
            f"--project_id={PROJECT}",
            "--use_legacy_sql=false",
            "--format=csv",
            sql,
        ],
        text=True,
    )
    lines = out.strip().splitlines()
    assert len(lines) >= 2
    assert int(lines[1]) > 0

