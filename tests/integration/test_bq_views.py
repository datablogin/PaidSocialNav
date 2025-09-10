import json
import os

import pytest

INTEGRATION = os.getenv("PSN_INTEGRATION") == "1"
PROJECT = os.getenv("GCP_PROJECT_ID", "fleming-424413")
DATASET = os.getenv("BQ_DATASET", "paid_social")

pytestmark = pytest.mark.skipif(
    not INTEGRATION, reason="Integration tests require PSN_INTEGRATION=1 and GCP creds"
)


def test_rollups_q2_has_rows():
    import subprocess

    sql = f"SELECT COUNT(*) FROM `{PROJECT}.{DATASET}.insights_rollups` WHERE `window`='Q2'"
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


def test_creative_mix_has_values_or_nulls():
    import subprocess

    sql = f"SELECT `window`, `level`, video_share, image_share FROM `{PROJECT}.{DATASET}.v_creative_mix` WHERE `window`='Q2' LIMIT 5"
    out = subprocess.check_output(
        [
            "bq",
            "query",
            f"--project_id={PROJECT}",
            "--use_legacy_sql=false",
            "--format=prettyjson",
            sql,
        ],
        text=True,
    )
    data = json.loads(out)
    assert isinstance(data, list)
    # OK for shares to be 0..1 or null if media mapping missing for some ads
    assert len(data) >= 1
