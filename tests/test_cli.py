from typer.testing import CliRunner

from duplicaid.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "PostgreSQL backup management CLI tool" in result.stdout


def test_config_commands():
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    assert "Configuration management" in result.stdout


def test_backup_commands():
    result = runner.invoke(app, ["backup", "--help"])
    assert result.exit_code == 0
    assert "Create backups" in result.stdout


def test_status_without_config():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1
    assert "Configuration not found" in result.stdout


def test_config_show_empty():
    result = runner.invoke(app, ["config", "show"])
    assert (
        "No configuration found" in result.stdout
        or "DuplicAid Configuration" in result.stdout
    )
