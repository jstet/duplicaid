import pytest

from duplicaid.backup import LogicalBackupManager, WALGBackupManager
from duplicaid.discovery import DatabaseDiscovery


@pytest.mark.integration
def test_database_discovery(test_services, local_executor, postgres_ready):
    discovery = DatabaseDiscovery(local_executor.config)
    databases = discovery.get_databases(local_executor)

    db_names = [db["name"] for db in databases]
    assert "testdb1" in db_names or "testdb2" in db_names


@pytest.mark.integration
def test_container_status_check(test_services, local_executor):
    assert local_executor.check_container_running("postgres")
    assert not local_executor.check_container_running("nonexistent")

    status = local_executor.get_container_status("postgres")
    assert status is not None
    assert "Up" in status


@pytest.mark.integration
def test_walg_backup_manager_init(test_services, local_executor, postgres_ready):
    walg_manager = WALGBackupManager(local_executor.config)
    assert walg_manager.config == local_executor.config


@pytest.mark.integration
def test_logical_backup_manager_init(test_services, local_executor, postgres_ready):
    logical_manager = LogicalBackupManager(local_executor.config)
    assert logical_manager.config == local_executor.config


@pytest.mark.integration
def test_postgres_connectivity(test_services, local_executor, postgres_ready):
    stdout, stderr, exit_code = local_executor.docker_exec(
        "postgres", "psql -U postgres -d postgres -c 'SELECT 1;'"
    )
    assert exit_code == 0


@pytest.mark.integration
def test_database_creation(test_services, local_executor, postgres_ready):
    stdout, stderr, exit_code = local_executor.docker_exec(
        "postgres", "psql -U postgres -c 'CREATE DATABASE test_integration;'"
    )
    assert exit_code == 0

    stdout, stderr, exit_code = local_executor.docker_exec(
        "postgres", "psql -U postgres -c 'DROP DATABASE test_integration;'"
    )
    assert exit_code == 0
