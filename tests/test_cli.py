from unittest.mock import Mock, patch

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


@patch("duplicaid.cli.get_executor")
@patch("duplicaid.cli.Config.load")
def test_backup_walg_command(mock_load, mock_get_executor):
    mock_config = Mock()
    mock_load.return_value = mock_config
    mock_executor = Mock()
    mock_get_executor.return_value = mock_executor

    runner.invoke(app, ["backup", "walg"])
    mock_get_executor.assert_called()


@patch("duplicaid.cli.get_executor")
@patch("duplicaid.cli.Config.load")
def test_backup_logical_command(mock_load, mock_get_executor):
    mock_config = Mock()
    mock_load.return_value = mock_config
    mock_executor = Mock()
    mock_get_executor.return_value = mock_executor

    runner.invoke(app, ["backup", "logical"])
    mock_get_executor.assert_called()


@patch("duplicaid.cli.get_executor")
@patch("duplicaid.cli.Config.load")
def test_list_walg_command(mock_load, mock_get_executor):
    mock_config = Mock()
    mock_load.return_value = mock_config
    mock_executor = Mock()
    mock_get_executor.return_value = mock_executor

    runner.invoke(app, ["list", "walg"])
    mock_get_executor.assert_called()


@patch("duplicaid.cli.get_executor")
@patch("duplicaid.cli.Config.load")
def test_status_command_with_config(mock_load, mock_get_executor):
    mock_config = Mock()
    mock_load.return_value = mock_config
    mock_executor = Mock()
    mock_get_executor.return_value = mock_executor
    mock_executor.check_container_running.return_value = True
    mock_executor.get_container_status.return_value = "Up 2 hours"

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_discover_command():
    result = runner.invoke(app, ["discover", "--help"])
    assert result.exit_code == 0
    assert "Discover databases" in result.stdout
