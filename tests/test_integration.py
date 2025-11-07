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


@pytest.mark.integration
def test_logical_backup_list(test_services, local_executor):
    logical_manager = LogicalBackupManager(local_executor.config)
    backups = logical_manager.list_backups(local_executor)
    assert isinstance(backups, list)


@pytest.mark.integration
def test_s3_backup_listing(test_services, local_executor):
    from minio import Minio

    client = Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False,
    )

    test_content = b"test backup content"
    test_filename = "postgres_20241107_120000.sql.bz2"
    test_path = f"test/logical/{test_filename}"

    from io import BytesIO

    client.put_object(
        "test-bucket",
        test_path,
        BytesIO(test_content),
        len(test_content),
    )

    logical_manager = LogicalBackupManager(local_executor.config)
    backups = logical_manager.list_backups(local_executor)

    assert isinstance(backups, list)
    assert len(backups) >= 1

    backup_names = [b.name for b in backups]
    assert test_filename in backup_names

    client.remove_object("test-bucket", test_path)
