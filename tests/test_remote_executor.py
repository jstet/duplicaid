from unittest.mock import Mock, patch

import pytest

from duplicaid.config import Config
from duplicaid.ssh import RemoteExecutor, SSHError


@pytest.fixture
def remote_config():
    config = Config()
    config._data = {
        "execution_mode": "remote",
        "remote": {
            "host": "test.example.com",
            "user": "testuser",
            "port": 22,
            "ssh_key_path": "/path/to/key",
        },
        "containers": {"postgres": "postgres", "backup": "db-backup"},
        "paths": {"docker_compose": "/test/docker-compose.yml"},
        "databases": ["testdb"],
    }
    yield config


@pytest.fixture
def mock_ssh_client():
    with patch("paramiko.SSHClient") as mock:
        yield mock


@patch("os.path.exists", return_value=True)
def test_remote_executor_connect(mock_exists, mock_ssh_client, remote_config):
    executor = RemoteExecutor(remote_config)
    with executor:
        mock_ssh_client.return_value.connect.assert_called_once()


@patch("os.path.exists", return_value=True)
def test_remote_executor_command_execution(mock_exists, mock_ssh_client, remote_config):
    mock_stdout = Mock()
    mock_stdout.read.return_value = b"test output"
    mock_stderr = Mock()
    mock_stderr.read.return_value = b""
    mock_ssh_client.return_value.exec_command.return_value = (
        None,
        mock_stdout,
        mock_stderr,
    )

    executor = RemoteExecutor(remote_config)
    with executor:
        stdout, stderr, code = executor.execute("test command")
        assert stdout == "test output"
        mock_ssh_client.return_value.exec_command.assert_called_with("test command")


def test_remote_executor_connection_error(mock_ssh_client, remote_config):
    mock_ssh_client.return_value.connect.side_effect = Exception("Connection failed")

    executor = RemoteExecutor(remote_config)
    with pytest.raises(SSHError):
        executor.connect()


@patch("os.path.exists", return_value=True)
def test_remote_executor_file_exists(mock_exists, mock_ssh_client, remote_config):
    executor = RemoteExecutor(remote_config)

    # Mock the execute method directly to return success
    with patch.object(executor, "execute", return_value=("", "", 0)):
        with executor:
            assert executor.file_exists("/test/path")


@patch("os.path.exists", return_value=True)
def test_remote_executor_file_not_exists(mock_exists, mock_ssh_client, remote_config):
    executor = RemoteExecutor(remote_config)

    # Mock the execute method directly to return failure
    with patch.object(executor, "execute", return_value=("", "", 1)):
        with executor:
            assert not executor.file_exists("/nonexistent/path")
