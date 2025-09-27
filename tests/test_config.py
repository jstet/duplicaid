from duplicaid.config import Config


def test_config_default_values():
    config = Config()
    assert config.execution_mode == "remote"
    assert config.postgres_container == "postgres"
    assert config.backup_container == "db-backup"


def test_config_local_mode():
    config = Config()
    config._data = {
        "execution_mode": "local",
        "containers": {"postgres": "test-postgres", "backup": "test-backup"},
        "paths": {"docker_compose": "./test.yml"},
        "databases": ["testdb"],
    }

    assert config.execution_mode == "local"
    assert config.postgres_container == "test-postgres"
    assert config.backup_container == "test-backup"
    assert config.docker_compose_path == "./test.yml"
    assert config.databases == ["testdb"]


def test_config_remote_mode():
    config = Config()
    config._data = {
        "execution_mode": "remote",
        "remote": {
            "host": "test.example.com",
            "user": "testuser",
            "port": 2222,
            "ssh_key_path": "/test/key",
        },
        "containers": {"postgres": "postgres", "backup": "db-backup"},
        "paths": {"docker_compose": "/remote/compose.yml"},
        "databases": ["db1", "db2"],
    }

    assert config.execution_mode == "remote"
    assert config.remote_host == "test.example.com"
    assert config.remote_user == "testuser"
    assert config.remote_port == 2222
    assert config.ssh_key_path == "/test/key"


def test_config_validation_local():
    config = Config()
    config._data = {
        "execution_mode": "local",
        "containers": {"postgres": "postgres", "backup": "db-backup"},
        "paths": {"docker_compose": "./test.yml"},
    }

    assert config.validate()


def test_config_validation_remote_missing_host():
    config = Config()
    config._data = {
        "execution_mode": "remote",
        "containers": {"postgres": "postgres", "backup": "db-backup"},
    }

    assert not config.validate()


def test_add_remove_database():
    config = Config()
    config._data = {"databases": ["existing_db"]}

    config.add_database("new_db")
    assert "new_db" in config.databases

    config.remove_database("new_db")
    assert "new_db" not in config.databases
