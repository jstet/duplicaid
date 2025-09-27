from unittest.mock import Mock

import pytest

from duplicaid.backup import LogicalBackupManager, WALGBackupManager
from duplicaid.config import Config


@pytest.fixture
def test_config():
    config = Config()
    config._data = {
        "execution_mode": "local",
        "containers": {"postgres": "postgres", "backup": "db-backup"},
        "paths": {"docker_compose": "/test/docker-compose.yml"},
        "databases": ["testdb1", "testdb2"],
    }
    return config


@pytest.fixture
def mock_executor():
    executor = Mock()
    executor.docker_exec.return_value = ("", "", 0)
    executor.check_container_running.return_value = True
    return executor


def test_walg_backup_creation(test_config, mock_executor):
    manager = WALGBackupManager(test_config)
    mock_executor.docker_exec.return_value = ("backup_20240101_120000", "", 0)

    manager.create_backup(mock_executor)
    mock_executor.docker_exec.assert_called()


def test_logical_backup_all_databases(test_config, mock_executor):
    manager = LogicalBackupManager(test_config)

    manager.create_backup(mock_executor)
    mock_executor.docker_exec.assert_called()


def test_logical_backup_specific_database(test_config, mock_executor):
    manager = LogicalBackupManager(test_config)

    manager.create_backup(mock_executor, "testdb1")
    mock_executor.docker_exec.assert_called()


def test_walg_backup_list(test_config, mock_executor):
    manager = WALGBackupManager(test_config)
    mock_executor.docker_exec.return_value = ("backup1\nbackup2", "", 0)

    manager.list_backups(mock_executor)
    mock_executor.docker_exec.assert_called()


def test_logical_backup_list(test_config, mock_executor):
    manager = LogicalBackupManager(test_config)
    mock_executor.docker_exec.return_value = ("file1.sql.gz\nfile2.sql.gz", "", 0)

    manager.list_backups(mock_executor)
    mock_executor.docker_exec.assert_called()


def test_walg_restore_latest(test_config, mock_executor):
    manager = WALGBackupManager(test_config)
    mock_executor.execute.return_value = ("", "", 0)

    manager.restore_backup(mock_executor)
    mock_executor.execute.assert_called()


def test_walg_restore_specific_backup(test_config, mock_executor):
    manager = WALGBackupManager(test_config)
    mock_executor.execute.return_value = ("", "", 0)

    manager.restore_backup(mock_executor, backup_name="backup_20240101")
    mock_executor.execute.assert_called()


def test_logical_restore(test_config, mock_executor):
    manager = LogicalBackupManager(test_config)

    manager.restore_backup(mock_executor, "testdb1", "/path/to/backup.sql.gz")
    mock_executor.docker_exec.assert_called()


def test_backup_manager_initialization(test_config):
    walg_manager = WALGBackupManager(test_config)
    logical_manager = LogicalBackupManager(test_config)

    assert walg_manager.config == test_config
    assert logical_manager.config == test_config


def test_container_status_check(test_config, mock_executor):
    manager = WALGBackupManager(test_config)
    mock_executor.check_container_running.return_value = False

    manager.create_backup(mock_executor)
    mock_executor.check_container_running.assert_called()
