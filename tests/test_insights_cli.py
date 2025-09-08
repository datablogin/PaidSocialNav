from typer.testing import CliRunner

from paid_social_nav.cli.main import app

runner = CliRunner()


class DummySettings:
    gcp_project_id = "p"
    bq_dataset = "d"
    meta_access_token = "tkn"


def test_meta_sync_insights_conflicting_flags(monkeypatch):
    # Patch settings resolver used by CLI module
    from paid_social_nav import cli as psn_cli

    monkeypatch.setattr(psn_cli.main, "get_settings", lambda: DummySettings())

    # date_preset plus since/until should error at CLI validation
    result = runner.invoke(
        app,
        [
            "meta",
            "sync-insights",
            "--account-id",
            "act_123",
            "--date-preset",
            "yesterday",
            "--since",
            "2025-09-01",
            "--until",
            "2025-09-02",
        ],
    )
    assert result.exit_code != 0
    assert "cannot be used together" in result.stdout


def test_meta_sync_insights_defaults_to_yesterday_when_no_dates(monkeypatch):
    # Patch settings resolver used by CLI module
    from paid_social_nav import cli as psn_cli

    monkeypatch.setattr(psn_cli.main, "get_settings", lambda: DummySettings())

    # Also monkeypatch sync to avoid performing real work and assert parameters
    called = {}

    def fake_sync(**kwargs):
        called.update(kwargs)
        return {"rows": 0}

    from paid_social_nav import cli as psn_cli

    # Patch the function as imported into the CLI module
    monkeypatch.setattr(psn_cli.main, "sync_meta_insights", fake_sync)

    result = runner.invoke(
        app,
        [
            "meta",
            "sync-insights",
            "--account-id",
            "123",
            "--level",
            "ad",
        ],
    )
    # Debug output on failure
    print(result.stdout)
    assert result.exit_code == 0
    # since/until should be None and date_preset None (default handled inside sync)
    assert called.get("level").value == "ad"
    assert called.get("date_preset") is None
    assert called.get("since") is None
    assert called.get("until") is None
